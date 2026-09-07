# Meeting routes: presigned-upload request, listing, detail, and delete.

import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.api.deps import get_workspace_membership
from app.core.rate_limit import increment_rate_limit
from app.models.meeting import Meeting
from app.models.workspace import WorkspaceMember
from app.schemas.meeting import (
    UploadRequest, UploadResponse, MeetingSummary, MeetingDetail,
)
from app.services.s3 import (
    generate_upload_key,
    create_presigned_upload,
    generate_download_url,
    delete_object,
)
from app.core.config import settings
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/workspaces/{workspace_id}/meetings", tags=["meetings"])

UPLOAD_REQUEST_RATE_LIMIT_MAX = 60
UPLOAD_REQUEST_RATE_LIMIT_WINDOW_SECONDS = 900


def _meeting_for(meeting_id, workspace_id, db: Session) -> Meeting:
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.workspace_id == workspace_id)
        .first()
    )
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


@router.post("", response_model=UploadResponse)
def request_upload(
    workspace_id: uuid.UUID,
    data: UploadRequest,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    is_limited, retry_after = increment_rate_limit(
        key=f"upload_request:{membership.user_id}",
        max_attempts=UPLOAD_REQUEST_RATE_LIMIT_MAX,
        window_seconds=UPLOAD_REQUEST_RATE_LIMIT_WINDOW_SECONDS,
    )
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many upload requests, slow down",
            headers={"Retry-After": str(retry_after)},
        )

    is_video = data.content_type in settings.ALLOWED_VIDEO_MIME_TYPES
    is_audio = data.content_type in settings.ALLOWED_AUDIO_MIME_TYPES

    if not is_audio and not is_video:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload an audio recording or a video file.",
        )

    max_size_mb = (
        settings.MAX_VIDEO_UPLOAD_SIZE_MB if is_video else settings.MAX_UPLOAD_SIZE_MB
    )
    max_bytes = max_size_mb * 1024 * 1024
    if data.file_size_bytes > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

    existing = (
        db.query(Meeting)
        .filter(
            Meeting.workspace_id == workspace_id,
            Meeting.owner_id == membership.user_id,
            Meeting.title == data.title,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A meeting with title '{data.title}' already exists in this workspace",
        )

    storage_key = generate_upload_key()

    meeting = Meeting(
        workspace_id=workspace_id,
        owner_id=membership.user_id,
        title=data.title,
        storage_key=storage_key,
        original_filename=data.title,
        file_size_bytes=data.file_size_bytes,
        content_type=data.content_type,
        source_media_type="video" if is_video else "audio",
        status="pending",
    )
    db.add(meeting)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A meeting with title '{data.title}' already exists in this workspace",
        )
    db.refresh(meeting)

    try:
        presigned = create_presigned_upload(storage_key, max_size_mb=max_size_mb)
    except Exception:
        logger.exception(
            "create_presigned_upload failed for meeting_id=%s workspace_id=%s "
            "content_type=%r max_size_mb=%s",
            meeting.id, workspace_id, data.content_type, max_size_mb,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to obtain upload credentials. Please try again.",
        )

    return UploadResponse(
        meeting_id=meeting.id,
        upload_url=presigned["url"],
        upload_fields=presigned["fields"],
    )


@router.post("/{meeting_id}/confirm-upload", response_model=MeetingSummary)
def confirm_upload(
    workspace_id: uuid.UUID,
    meeting_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    meeting = _meeting_for(meeting_id, workspace_id, db)

    if meeting.status != "pending":
        return meeting

    celery_app.send_task("transcribe_meeting", args=[str(meeting.id)])

    return meeting


@router.get("", response_model=list[MeetingSummary])
def list_meetings(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    meetings = db.query(Meeting).filter(Meeting.workspace_id == workspace_id).all()
    return meetings


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(
    workspace_id: uuid.UUID,
    meeting_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    return _meeting_for(meeting_id, workspace_id, db)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    workspace_id: uuid.UUID,
    meeting_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    meeting = _meeting_for(meeting_id, workspace_id, db)

    if membership.user_id != meeting.owner_id and membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting owner or workspace admin/owner can delete this meeting",
        )

    delete_object(meeting.storage_key)

    db.delete(meeting)
    db.commit()

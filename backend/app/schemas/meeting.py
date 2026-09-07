# Pydantic schemas for meeting and action-item request/response bodies.

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

class UploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    file_size_bytes: int
    content_type: str

class UploadResponse(BaseModel):
    meeting_id: uuid.UUID
    upload_url: str
    upload_fields: dict

class MeetingSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    source_media_type: str = "audio"
    summary_text: str | None = None

    class Config:
        from_attributes = True

class ActionItemOut(BaseModel):
    id: uuid.UUID
    description: str
    owner: str | None
    due_date: str | None

    class Config:
        from_attributes = True

class MeetingDetail(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    transcript_text: str | None
    summary_text: str | None
    error_message: str | None = None
    action_items: list[ActionItemOut] = []
    created_at: datetime
    source_media_type: str = "audio"

    class Config:
        from_attributes = True

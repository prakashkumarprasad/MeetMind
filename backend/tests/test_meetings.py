# Tests for meeting upload authorization, validation, and deletion.

"""
Covers app/api/v1/meetings.py:
- Unique title per user per workspace (409 conflict)
- Delete meeting (owner/admin only, 403 for member, 404 for non-existent)
- Empty title rejected (min_length=1)
"""
import uuid

from app.models.meeting import Meeting

def test_upload_duplicate_title_same_user_same_workspace_rejected(client, make_user):
    """Same user cannot create two meetings with the same title in the same workspace."""
    _, workspace, headers = make_user("dupeuser@example.com")

    first = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "My Meeting", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "My Meeting", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]

def test_upload_same_title_different_user_same_workspace_allowed(client, make_user, db_session):
    """Different users CAN have the same title in the same workspace."""
    _, workspace, headers_a = make_user("usera@example.com")
    user_b, _, headers_b = make_user("userb@example.com")

    from app.models.workspace import WorkspaceMember

    membership_b = WorkspaceMember(workspace_id=workspace.id, user_id=user_b.id, role="member")
    db_session.add(membership_b)
    db_session.flush()

    first = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Shared Title", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers_a,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Shared Title", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers_b,
    )
    assert second.status_code == 200

def test_upload_same_title_different_workspace_allowed(client, make_user, db_session):
    """Same user CAN have the same title in different workspaces."""

    user, workspace_a, headers = make_user("multiws@example.com")

    from app.models.workspace import Workspace, WorkspaceMember

    workspace_b = Workspace(name=f"second workspace")
    db_session.add(workspace_b)
    db_session.flush()

    membership_b = WorkspaceMember(workspace_id=workspace_b.id, user_id=user.id, role="owner")
    db_session.add(membership_b)
    db_session.flush()

    first = client.post(
        f"/api/v1/workspaces/{workspace_a.id}/meetings",
        json={"title": "Same Title", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/workspaces/{workspace_b.id}/meetings",
        json={"title": "Same Title", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert second.status_code == 200

def test_upload_empty_title_rejected(client, make_user):
    """Empty title should be rejected with 422."""
    _, workspace, headers = make_user("emptytitle@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert response.status_code == 422

def test_delete_meeting_owner_can_delete(client, make_user, db_session):
    """Meeting owner can delete their own meeting."""
    _, workspace, headers = make_user("ownerdelete@example.com")

    create_resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "To Delete", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    meeting_id = create_resp.json()["meeting_id"]

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace.id}/meetings/{meeting_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is None

def test_delete_meeting_admin_can_delete(client, make_user, db_session):
    """Workspace admin can delete any meeting in the workspace."""
    _, workspace, headers_owner = make_user("adminowner@example.com")
    user_member, _, headers_member = make_user("adminmember@example.com")

    from app.models.workspace import WorkspaceMember

    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user_member.id, role="admin")
    db_session.add(membership)
    db_session.flush()

    create_resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Admin Delete Test", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers_owner,
    )
    meeting_id = create_resp.json()["meeting_id"]

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace.id}/meetings/{meeting_id}",
        headers=headers_member,
    )
    assert delete_resp.status_code == 204

def test_delete_meeting_member_cannot_delete(client, make_user, db_session):
    """Regular member cannot delete another user's meeting."""
    _, workspace, headers_owner = make_user("memberowner@example.com")
    user_member, _, headers_member = make_user("membermember@example.com")

    from app.models.workspace import WorkspaceMember

    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user_member.id, role="member")
    db_session.add(membership)
    db_session.flush()

    create_resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Member Cannot Delete", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers_owner,
    )
    meeting_id = create_resp.json()["meeting_id"]

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace.id}/meetings/{meeting_id}",
        headers=headers_member,
    )
    assert delete_resp.status_code == 403

def test_delete_meeting_nonexistent_returns_404(client, make_user):
    """Deleting a non-existent meeting returns 404."""
    _, workspace, headers = make_user("nonexistdelete@example.com")
    fake_meeting_id = uuid.uuid4()

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace.id}/meetings/{fake_meeting_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 404
    assert delete_resp.json()["detail"] == "Meeting not found"

def test_delete_meeting_cascades_transcript_chunks(client, make_user, db_session):
    """
    Deleting a meeting must also delete its transcript chunks. Before the
    Meeting.transcript_chunks ORM relationship was added, deleting a processed
    meeting raised an IntegrityError (no ondelete on the FK, no DB-level
    cascade), so this guards the fix.
    """
    user, workspace, headers = make_user("cascade@example.com")

    meeting = Meeting(
        workspace_id=workspace.id,
        owner_id=user.id,
        title="Cascade Delete",
        storage_key="audio/test-key",
        original_filename="Cascade Delete",
        file_size_bytes=1024,
        content_type="audio/mpeg",
        status="ready",
    )
    db_session.add(meeting)
    db_session.flush()

    from app.models.transcript_chunk import TranscriptChunk

    db_session.add(
        TranscriptChunk(
            meeting_id=meeting.id,
            workspace_id=workspace.id,
            chunk_text="chunk one",
            chunk_index=0,
            embedding=[0.0] * 384,
        )
    )
    db_session.add(
        TranscriptChunk(
            meeting_id=meeting.id,
            workspace_id=workspace.id,
            chunk_text="chunk two",
            chunk_index=1,
            embedding=[0.0] * 384,
        )
    )
    db_session.flush()

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace.id}/meetings/{meeting.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    assert db_session.query(Meeting).filter(Meeting.id == meeting.id).first() is None
    remaining = (
        db_session.query(TranscriptChunk).filter(TranscriptChunk.meeting_id == meeting.id).count()
    )
    assert remaining == 0

def test_upload_video_accepted_and_flags_source_media_type(client, make_user, db_session):
    """
    Video containers are now accepted for upload (they get converted to audio
    by the worker before transcription). The meeting row must be flagged
    source_media_type="video" so the worker knows to run ffmpeg.
    """
    _, workspace, headers = make_user("videouploader@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Team Call Recording", "file_size_bytes": 2048, "content_type": "video/mp4"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert "upload_url" in response.json()

    meeting_id = response.json()["meeting_id"]
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).one()
    assert meeting.source_media_type == "video"

def test_upload_video_within_video_size_cap_allowed(client, make_user):
    """A large-but-allowed video passes the video-specific size check."""
    _, workspace, headers = make_user("largevideo@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Big Video", "file_size_bytes": 1000 * 1024 * 1024, "content_type": "video/webm"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

def test_upload_unsupported_type_rejected(client, make_user):
    """Content types that are neither audio nor video are rejected with 400."""
    _, workspace, headers = make_user("unsupported@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Bad File", "file_size_bytes": 1024, "content_type": "application/pdf"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
def test_upload_passes_video_size_cap_to_presign(monkeypatch, client, make_user, db_session):
    """
    Regression test for the A1 video-upload 500. `create_presigned_upload` takes
    a `max_size_mb` that is chosen per content type (video uses the higher video
    cap). This asserts the endpoint actually forwards *its* chosen value, so a
    future refactor that changes the call signature but forgets one call site
    (the original bug) is caught instead of surfacing as a runtime 500.
    """
    calls: list[dict] = []

    def _fake_create_presigned_upload(storage_key, max_size_mb=None, **kwargs):
        calls.append({"storage_key": storage_key, "max_size_mb": max_size_mb})
        return {"url": "https://s3.example.com/upload", "fields": {"k": "v"}}

    monkeypatch.setattr(
        "app.api.v1.meetings.create_presigned_upload", _fake_create_presigned_upload
    )

    _, workspace, headers = make_user("presigncheck@example.com")

    video = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Video Upload", "file_size_bytes": 2048, "content_type": "video/mp4"},
        headers=headers,
    )
    assert video.status_code == 200, video.text
    assert calls[-1]["max_size_mb"] == 2048

    audio = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Audio Upload", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert audio.status_code == 200, audio.text
    assert calls[-1]["max_size_mb"] == 500

def test_upload_presign_failure_logged_and_500(monkeypatch, caplog, client, make_user):
    """
    If S3 presigning genuinely fails (real env, network/credentials), the request
    must return 500 (not crash the worker/connection) and log enough context to
    debug without guessing. This is the hardening added for A1.
    """
    monkeypatch.setattr(
        "app.api.v1.meetings.create_presigned_upload",
        lambda storage_key, max_size_mb=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    _, workspace, headers = make_user("presignfail@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "Failing Upload", "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert response.status_code == 500
    assert "create_presigned_upload failed" in caplog.text

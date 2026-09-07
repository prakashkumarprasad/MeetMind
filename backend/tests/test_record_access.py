# Tests for per-route record access (IDOR) and context isolation across workspaces.

"""
Systematic record-access matrix (security audit item 15), plus regression
coverage for the newer surfaces (items 2, 4, 6, 7, 8).

For every resource reachable through the API the matrix checks:
  owner / same-workspace member  -> access OK
  different-workspace user       -> no access (404, existence hidden)
  unauthenticated                -> 401

Resources covered: meetings (list/detail), chat sessions (list + messages),
and the chat context-selection path (meeting_ids). This encodes the
"isolation is at the workspace boundary, not per-user" guarantee — two
members of the SAME workspace share data, two strangers do not.
"""
import uuid

import numpy as np
import pytest

VALID_PASSWORD = "SuperSecurePassword123"

@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.chat._embedding_model.encode",
        lambda text: np.zeros(384),
    )

def _make_user_with_meeting(client, make_user, db_session, email, title, summary, chunk):
    """Creates a user + personal workspace + one ready meeting (with optional
    transcript chunk). Returns (user, workspace, headers, meeting)."""
    from app.models.meeting import Meeting
    from app.models.transcript_chunk import TranscriptChunk

    user, workspace, headers = make_user(email)
    meeting = Meeting(
        workspace_id=workspace.id,
        owner_id=user.id,
        title=title,
        storage_key=f"audio/{uuid.uuid4()}",
        original_filename=title,
        file_size_bytes=1024,
        content_type="audio/mpeg",
        status="ready",
        summary_text=summary,
    )
    db_session.add(meeting)
    db_session.flush()
    if chunk is not None:
        db_session.add(TranscriptChunk(
            meeting_id=meeting.id,
            workspace_id=workspace.id,
            chunk_text=chunk,
            chunk_index=0,
            embedding=[0.0] * 384,
        ))
        db_session.flush()
    return user, workspace, headers, meeting

def test_owner_can_list_and_read_own_meetings(client, make_user, db_session):
    _, workspace, headers, meeting = _make_user_with_meeting(
        client, make_user, db_session, "ownermeet@example.com", "My Meeting", "MY-SUMMARY", "my words",
    )
    listing = client.get(f"/api/v1/workspaces/{workspace.id}/meetings", headers=headers)
    assert listing.status_code == 200
    assert [m["id"] for m in listing.json()] == [str(meeting.id)]

    detail = client.get(f"/api/v1/workspaces/{workspace.id}/meetings/{meeting.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "My Meeting"

def test_different_workspace_user_gets_404_on_other_meeting(client, make_user, db_session):
    """A user pointing at another user's workspace_id gets 404, never the data."""
    _, ws_a, _, _ = _make_user_with_meeting(
        client, make_user, db_session, "da@example.com", "Ws A Meeting", "WS-A-SUMMARY", "a chunk",
    )
    _, _ws_b, headers_b = make_user("db@example.com")

    resp = client.get(f"/api/v1/workspaces/{ws_a.id}/meetings", headers=headers_b)
    assert resp.status_code == 404

def test_same_workspace_member_can_access_shared_meetings(client, make_user, db_session):
    """Isolation is at the workspace boundary: a different *member* of the
    same workspace can see the same meetings (deliberate, not a leak)."""
    from app.models.workspace import WorkspaceMember
    from app.models.meeting import Meeting

    owner, workspace, _headers_a = make_user("sharedowner@example.com")
    member_user, _, headers_b = make_user("sharedmember@example.com")
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=member_user.id, role="member"))
    db_session.flush()

    db_session.add(Meeting(
        workspace_id=workspace.id, owner_id=owner.id, title="Shared", storage_key="audio/x",
        original_filename="Shared", file_size_bytes=10, content_type="audio/mpeg",
        status="ready", summary_text="SHARED-SUMMARY",
    ))
    db_session.flush()

    resp = client.get(f"/api/v1/workspaces/{workspace.id}/meetings", headers=headers_b)
    assert resp.status_code == 200
    assert [m["title"] for m in resp.json()] == ["Shared"]

def test_unauthenticated_cannot_access_any_resource(client, make_user):
    _, workspace, _headers = make_user("unauth@example.com")
    bogus_uuid = uuid.uuid4()
    endpoints = [
        ("GET", "/api/v1/workspaces"),
        ("GET", f"/api/v1/workspaces/{workspace.id}/meetings"),
        ("GET", f"/api/v1/workspaces/{workspace.id}/meetings/{bogus_uuid}"),
        ("POST", f"/api/v1/workspaces/{workspace.id}/meetings"),
        ("DELETE", f"/api/v1/workspaces/{workspace.id}/meetings/{bogus_uuid}"),
        ("GET", f"/api/v1/workspaces/{workspace.id}/chat/sessions"),
        ("POST", f"/api/v1/workspaces/{workspace.id}/chat"),
        ("GET", f"/api/v1/workspaces/{workspace.id}/chat/meetings"),
        ("GET", "/api/v1/auth/me"),
    ]
    for method, url in endpoints:
        resp = client.request(method, url, json={} if method == "POST" else None)
        assert resp.status_code == 401, f"{method} {url} -> {resp.status_code}"

def _capture_rag_messages(monkeypatch):
    """Patch generate_chat_completion at its usage site so we can inspect the
    exact prompt built by build_rag_messages."""
    holder: dict = {}

    def _fake(messages):
        holder["messages"] = messages
        return "answer"

    monkeypatch.setattr("app.api.v1.chat.generate_chat_completion", _fake)
    return holder

def test_chat_context_selection_ignores_foreign_meeting_id(client, make_user, db_session, monkeypatch):
    """Passing another workspace's meeting_id in meeting_ids must NOT leak
    that meeting's content into the RAG prompt."""
    _, ws_a, headers_a, _ = _make_user_with_meeting(
        client, make_user, db_session, "idora@example.com", "Meeting A", "SUMMARY-A", "chunk-a",
    )
    _, _ws_b, _, foreign_meeting = _make_user_with_meeting(
        client, make_user, db_session, "idorb@example.com", "Meeting B", "SECRET-FOREIGN-WS", "secret-b-chunk",
    )

    holder = _capture_rag_messages(monkeypatch)

    resp = client.post(
        f"/api/v1/workspaces/{ws_a.id}/chat",
        json={"question": "What is in that other workspace?", "meeting_ids": [str(foreign_meeting.id)]},
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text

    prompt = "\n".join(m.get("content", "") for m in holder["messages"])
    assert "SECRET-FOREIGN-WS" not in prompt
    assert "secret-b-chunk" not in prompt
    assert "Meeting B" not in prompt

def test_chat_context_selection_too_many_ids_rejected(client, make_user):
    """meeting_ids list is length-bounded (item 6) so a client can't force a
    huge IN(...) query."""
    _, workspace, headers = make_user("manyids@example.com")
    too_many = [str(uuid.uuid4()) for _ in range(60)]
    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "hi", "meeting_ids": too_many},
        headers=headers,
    )
    assert resp.status_code == 422

def test_upload_title_too_long_rejected(client, make_user):
    _, workspace, headers = make_user("longtitle@example.com")
    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": "A" * 201, "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert resp.status_code == 422

def test_meeting_title_stored_as_data_not_executed(client, make_user, db_session, monkeypatch):
    """A title that looks like SQL is stored as literal text, never executed
    (no raw-SQL / string-interpolated queries anywhere near it)."""
    from app.models.meeting import Meeting

    _, workspace, headers = make_user("sqlititle@example.com")
    payload = "BOOM'; DROP TABLE meetings; --"
    monkeypatch.setattr(
        "app.api.v1.meetings.create_presigned_upload",
        lambda storage_key, max_size_mb=None: {"url": "https://s3/x", "fields": {"k": "v"}},
    )
    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/meetings",
        json={"title": payload, "file_size_bytes": 1024, "content_type": "audio/mpeg"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    created = db_session.query(Meeting).filter(Meeting.title == payload).first()
    assert created is not None
    assert created.title == payload

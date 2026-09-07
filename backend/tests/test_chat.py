# Tests for chat sessions and workspace-scoped RAG context retrieval.

"""
Covers app/api/v1/chat.py: session creation/reuse, the deeper
session-ownership IDOR check (distinct from the workspace-membership
check in test_workspace_membership.py — this one guards against a
member of workspace A passing in a session_id that belongs to
workspace B), and rate limiting.

The embedding model's .encode() is mocked per-test to avoid real CPU
inference on every call — note this does NOT avoid the one-time model
download/load that happens at import time when chat.py is first
imported (see conftest.py's _mock_llm docstring for the equivalent
note on the LLM call).
"""
import pytest
import numpy as np

from app.api.v1.chat import CHAT_RATE_LIMIT_MAX

@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.chat._embedding_model.encode",
        lambda text: np.zeros(384),
    )

def test_first_message_creates_new_session(client, make_user):
    _, workspace, headers = make_user("chatuser1@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Hello"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] is not None
    assert body["answer"] == "mocked answer"
    assert body["sources"] is None

def test_second_message_reuses_provided_session_id(client, make_user):
    _, workspace, headers = make_user("chatuser2@example.com")

    first = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Hello"},
        headers=headers,
    )
    session_id = first.json()["session_id"]

    second = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Follow-up question", "session_id": session_id},
        headers=headers,
    )

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id

def test_history_persisted_across_turns(client, make_user, db_session):
    from app.models.chat import ChatMessage

    _, workspace, headers = make_user("chatuser3@example.com")

    first = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "First message"},
        headers=headers,
    )
    session_id = first.json()["session_id"]

    client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Second message", "session_id": session_id},
        headers=headers,
    )

    messages = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )

    assert len(messages) == 4
    assert messages[0].role == "user"
    assert messages[0].content == "First message"
    assert messages[2].role == "user"
    assert messages[2].content == "Second message"

def test_empty_question_rejected(client, make_user):
    _, workspace, headers = make_user("chatuser4@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "   "},
        headers=headers,
    )

    assert response.status_code == 422

def test_session_id_from_another_workspace_returns_404(client, make_user):
    """
    User A is a legitimate member of workspace A. If they pass a
    session_id that actually belongs to workspace B (even one they're
    also a member of, or especially one they aren't), the chat query
    filters on BOTH session_id AND workspace_id AND user_id — so this
    must 404, not silently return workspace B's chat history mixed
    into workspace A's context.
    """
    _, workspace_a, headers_a = make_user("workspaceowner_a@example.com")
    _, workspace_b, headers_b = make_user("workspaceowner_b@example.com")

    b_response = client.post(
        f"/api/v1/workspaces/{workspace_b.id}/chat",
        json={"question": "Secret question in workspace B"},
        headers=headers_b,
    )
    session_id_from_b = b_response.json()["session_id"]

    cross_response = client.post(
        f"/api/v1/workspaces/{workspace_a.id}/chat",
        json={"question": "trying to reuse someone else's session", "session_id": session_id_from_b},
        headers=headers_a,
    )

    assert cross_response.status_code == 404
    assert cross_response.json()["detail"] == "Chat session not found"

def test_own_session_id_used_in_wrong_workspace_returns_404(client, make_user):
    """
    Same user, two workspaces they legitimately belong to (not
    applicable here since make_user only creates one workspace per
    user, but the equivalent single-workspace-mismatch case): a
    session created under workspace A cannot be reused against a
    request URL for workspace B, even for the session's own owner.
    """
    user, workspace_a, headers = make_user("multiworkspace@example.com")

    a_response = client.post(
        f"/api/v1/workspaces/{workspace_a.id}/chat",
        json={"question": "hello from workspace A"},
        headers=headers,
    )
    session_id = a_response.json()["session_id"]

    _, workspace_c, headers_c = make_user("otherowner@example.com")

    third_user_workspace_response = client.post(
        f"/api/v1/workspaces/{workspace_c.id}/chat",
        json={"question": "wrong workspace for this session_id", "session_id": session_id},
        headers=headers,
    )

    assert third_user_workspace_response.status_code == 404

def test_rate_limit_blocks_after_max_messages(client, make_user):
    _, workspace, headers = make_user("ratelimituser@example.com")

    statuses = []
    for i in range(CHAT_RATE_LIMIT_MAX + 2):
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/chat",
            json={"question": f"message {i}"},
            headers=headers,
        )
        statuses.append(response.status_code)

    successes = statuses[:CHAT_RATE_LIMIT_MAX]
    overflow = statuses[CHAT_RATE_LIMIT_MAX:]

    assert all(s == 200 for s in successes)
    assert all(s == 429 for s in overflow)

def test_list_chat_sessions_empty(client, make_user):
    """List sessions returns empty list when none exist."""
    _, workspace, headers = make_user("historyuser1@example.com")

    response = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []

def test_list_chat_sessions_returns_user_sessions_only(client, make_user, db_session):
    """List sessions returns only current user's sessions, not other users' sessions."""
    _, workspace, headers_a = make_user("historyusera@example.com")
    user_b, _, headers_b = make_user("historyuserb@example.com")

    from app.models.workspace import WorkspaceMember
    membership_b = WorkspaceMember(workspace_id=workspace.id, user_id=user_b.id, role="member")
    db_session.add(membership_b)
    db_session.flush()

    resp_a = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Hello from A"},
        headers=headers_a,
    )
    session_a_id = resp_a.json()["session_id"]

    resp_b = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Hello from B"},
        headers=headers_b,
    )
    session_b_id = resp_b.json()["session_id"]

    list_a = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions",
        headers=headers_a,
    )
    assert list_a.status_code == 200
    sessions_a = list_a.json()
    assert len(sessions_a) == 1
    assert sessions_a[0]["id"] == session_a_id

    list_b = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions",
        headers=headers_b,
    )
    assert list_b.status_code == 200
    sessions_b = list_b.json()
    assert len(sessions_b) == 1
    assert sessions_b[0]["id"] == session_b_id

def test_list_chat_sessions_ordered_most_recent_first(client, make_user):
    """Sessions are ordered by updated_at descending (most recent first)."""
    _, workspace, headers = make_user("historyorder@example.com")

    resp1 = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "First session"},
        headers=headers,
    )
    session1_id = resp1.json()["session_id"]

    resp2 = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Second session"},
        headers=headers,
    )
    session2_id = resp2.json()["session_id"]

    list_resp = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions",
        headers=headers,
    )
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 2
    assert sessions[0]["id"] == session2_id
    assert sessions[1]["id"] == session1_id

def test_get_chat_session_messages(client, make_user):
    """Get messages for a specific session."""
    _, workspace, headers = make_user("getmessages@example.com")

    resp1 = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "First question"},
        headers=headers,
    )
    session_id = resp1.json()["session_id"]

    client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Follow-up question", "session_id": session_id},
        headers=headers,
    )

    msg_resp = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions/{session_id}/messages",
        headers=headers,
    )
    assert msg_resp.status_code == 200
    messages = msg_resp.json()
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "First question"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Follow-up question"
    assert messages[3]["role"] == "assistant"

def test_get_chat_session_messages_wrong_user_returns_404(client, make_user, db_session):
    """Cannot access another user's session messages."""
    _, workspace, headers_a = make_user("msga@example.com")
    user_b, _, headers_b = make_user("msgb@example.com")

    from app.models.workspace import WorkspaceMember
    membership_b = WorkspaceMember(workspace_id=workspace.id, user_id=user_b.id, role="member")
    db_session.add(membership_b)
    db_session.flush()

    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "Secret"},
        headers=headers_a,
    )
    session_id = resp.json()["session_id"]

    msg_resp = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions/{session_id}/messages",
        headers=headers_b,
    )
    assert msg_resp.status_code == 404
    assert msg_resp.json()["detail"] == "Chat session not found"

def test_get_chat_session_messages_nonexistent_returns_404(client, make_user):
    """Non-existent session returns 404."""
    _, workspace, headers = make_user("msgnonexist@example.com")
    fake_session_id = "00000000-0000-0000-0000-000000000000"

    msg_resp = client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/sessions/{fake_session_id}/messages",
        headers=headers,
    )
    assert msg_resp.status_code == 404
    assert msg_resp.json()["detail"] == "Chat session not found"

def test_get_chat_session_messages_wrong_workspace_returns_404(client, make_user):
    """Session from different workspace returns 404 (or Workspace not found at membership layer)."""
    _, workspace_a, headers = make_user("msgwsa@example.com")
    _, workspace_b, _ = make_user("msgwsb@example.com")

    resp = client.post(
        f"/api/v1/workspaces/{workspace_a.id}/chat",
        json={"question": "In workspace A"},
        headers=headers,
    )
    session_id = resp.json()["session_id"]

    msg_resp = client.get(
        f"/api/v1/workspaces/{workspace_b.id}/chat/sessions/{session_id}/messages",
        headers=headers,
    )
    assert msg_resp.status_code == 404

    assert msg_resp.json()["detail"] in ("Chat session not found", "Workspace not found")

def _capture_rag_messages(monkeypatch):
    """Patch generate_chat_completion at its usage site so we can inspect the
    exact prompt/context that build_rag_messages assembled, instead of only
    the final (mocked) answer. Returns a holder dict populated with
    {'messages': [...]} after the request completes."""
    holder: dict = {}

    def _fake(messages):
        holder["messages"] = messages
        return "answer"

    monkeypatch.setattr("app.api.v1.chat.generate_chat_completion", _fake)
    return holder

def _make_meeting(db_session, user, workspace, title, *, status="ready", summary=None, chunk=None):
    from app.models.meeting import Meeting
    from app.models.transcript_chunk import TranscriptChunk

    meeting = Meeting(
        workspace_id=workspace.id,
        owner_id=user.id,
        title=title,
        storage_key=f"audio/{title}",
        original_filename=title,
        file_size_bytes=1024,
        content_type="audio/mpeg",
        status=status,
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

    return meeting

def test_aggregate_summary_uses_all_selected_meetings(client, make_user, db_session, monkeypatch):
    """
    Regression test for the "summarize all N selected meetings returns only
    one" bug. Explicitly-selected meetings must ALL contribute content to the
    prompt — not just the single meeting whose transcript happens to embed
    closest to the question.

    Pre-fix, every request was routed through the semantic-similarity fallback
    (a distance threshold plus one global top-k), which silently dropped every
    selected meeting except the closest-matching one. We assert on the
    CONSTRUCTED PROMPT (not the final answer) so a wrong-but-plausible answer
    can't mask the partial-context bug.
    """
    user, workspace, headers = make_user("aggsummary@example.com")

    meetings = [
        _make_meeting(
            db_session, user, workspace, f"Aggregate {i}",
            summary=f"UNIQUE-SUMMARY-{i}: content for meeting {i}",
            chunk=f"transcript words for meeting {i}",
        )
        for i in range(3)
    ]

    holder = _capture_rag_messages(monkeypatch)

    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={
            "question": "Summarize all the selected meetings",
            "meeting_ids": [str(m.id) for m in meetings],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    prompt = "\n".join(m["content"] for m in holder["messages"])
    for i in range(3):
        assert f"UNIQUE-SUMMARY-{i}" in prompt, f"meeting {i} missing from prompt content"

def test_processing_meeting_with_no_content_is_surfaced_by_status(client, make_user, db_session, monkeypatch):
    """
    A selected meeting that is still processing (no summary, no chunks) must
    be listed in the prompt by name with its status, so the model acknowledges
    it instead of pretending it was never provided.
    """
    user, workspace, headers = make_user("nocontent@example.com")

    ready = _make_meeting(
        db_session, user, workspace, "Ready One",
        summary="READY-ONE-SUMMARY: closed the deal",
    )
    processing = _make_meeting(
        db_session, user, workspace, "Still Processing",
        status="transcribing", summary=None, chunk=None,
    )

    holder = _capture_rag_messages(monkeypatch)

    resp = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={
            "question": "What do these meetings cover?",
            "meeting_ids": [str(ready.id), str(processing.id)],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    prompt = "\n".join(m["content"] for m in holder["messages"])
    assert "READY-ONE-SUMMARY" in prompt
    assert processing.title in prompt
    assert "transcribing" in prompt
    assert (
        "<no_content>" in prompt
        or "no transcript or summary is available" in prompt.lower()
    )

# Chat routes: multi-meeting RAG queries, chat sessions/messages, and meeting context selection.

import uuid
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.db.session import get_db
from app.api.deps import get_workspace_membership, get_current_user
from app.core.rate_limit import is_rate_limited, increment_rate_limit
from app.models.workspace import WorkspaceMember
from app.models.user import User
from app.models.transcript_chunk import TranscriptChunk
from app.models.meeting import Meeting
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource, ChatSessionOut, ChatMessageOut
from app.services.llm import build_rag_messages, generate_chat_completion, MAX_HISTORY_MESSAGES
from app.schemas.meeting import MeetingSummary

router = APIRouter(prefix="/workspaces/{workspace_id}/chat", tags=["chat"])

_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
TOP_K_CHUNKS = 8
CHAT_RATE_LIMIT_MAX = 20
CHAT_RATE_LIMIT_WINDOW_SECONDS = 900

MAX_RELEVANT_DISTANCE = 0.8

CANDIDATE_POOL_SIZE = TOP_K_CHUNKS * 3

RECENCY_HALF_LIFE_DAYS = 30
RECENCY_MAX_BONUS = 0.15

EXCERPT_MAX_CHARS = 300

def _make_excerpt(text: str) -> str:
    text = text.strip()
    if len(text) <= EXCERPT_MAX_CHARS:
        return text
    return text[:EXCERPT_MAX_CHARS].rsplit(" ", 1)[0] + "..."

def _recency_bonus(meeting_created_at: datetime) -> float:
    """
    Returns a value in (0, RECENCY_MAX_BONUS], higher for more recent meetings,
    decaying by half every RECENCY_HALF_LIFE_DAYS. Subtracted from a chunk's
    distance so recent chunks rank slightly better without letting recency
    alone override real semantic relevance.
    """
    age_days = (datetime.now(timezone.utc) - meeting_created_at).total_seconds() / 86400
    age_days = max(age_days, 0)
    decay = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
    return RECENCY_MAX_BONUS * decay

def _find_title_matched_meetings(db: Session, workspace_id: uuid.UUID, question: str) -> list[Meeting]:
    """
    Word-boundary match: if a meeting's title appears as a whole word in the
    question (case-insensitive), treat that meeting as explicitly referenced.
    This lets questions like "what's in the new3 summary" work even though
    the title "new3" never appears in the spoken transcript content itself —
    pure semantic search over transcript_text has no way to make that link.
    
    Uses word boundaries to avoid false positives like "new" matching "new5" or "neweww".
    """
    question_lower = question.lower()
    meetings = db.query(Meeting).filter(
        Meeting.workspace_id == workspace_id,
        Meeting.status == "ready",
    ).all()

    matched = []
    for m in meetings:
        if not m.title:
            continue

        pattern = r'\b' + re.escape(m.title.lower()) + r'\b'
        if re.search(pattern, question_lower):
            matched.append(m)
    return matched

@router.get("/sessions", response_model=list[ChatSessionOut])
def list_chat_sessions(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    """List all chat sessions for the current user in this workspace, most recent first."""
    sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.workspace_id == workspace_id,
            ChatSession.user_id == membership.user_id,
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return sessions

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def get_chat_session_messages(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: Session = Depends(get_db),
):
    """Get all messages for a specific chat session (with ownership check)."""
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.workspace_id == workspace_id,
            ChatSession.user_id == membership.user_id,
        )
        .first()
    )

    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return messages

@router.post("", response_model=ChatResponse)
def chat(
    workspace_id: uuid.UUID,
    data: ChatRequest,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_limited, retry_after = increment_rate_limit(
        key=f"chat:{current_user.id}",
        max_attempts=CHAT_RATE_LIMIT_MAX,
        window_seconds=CHAT_RATE_LIMIT_WINDOW_SECONDS,
    )
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={"message": "Too many chat messages, slow down.", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question cannot be empty")

    meeting_ids = data.meeting_ids or None

    try:
        if data.session_id:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.id == data.session_id,
                    ChatSession.workspace_id == workspace_id,
                    ChatSession.user_id == current_user.id,
                )
                .first()
            )
            if session is None:
                raise HTTPException(status_code=404, detail="Chat session not found")
        else:
            session = ChatSession(
                workspace_id=workspace_id,
                user_id=current_user.id,
                title=question[:40],
            )
            db.add(session)
            db.flush()

        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id, ChatMessage.workspace_id == workspace_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
            .all()
        )
        history.reverse()

        question_embedding = _embedding_model.encode(question).tolist()
        distance_col = TranscriptChunk.embedding.cosine_distance(question_embedding)

        title_matched_meetings = _find_title_matched_meetings(db, workspace_id, question)

        excerpts_for_prompt: list[dict] = []
        sources: list[ChatSource] = []
        seen_meeting_ids: set = set()

        def _add_source(meeting: Meeting, excerpt_text: str):
            if meeting.id not in seen_meeting_ids:
                seen_meeting_ids.add(meeting.id)
                sources.append(ChatSource(
                    meeting_id=meeting.id,
                    meeting_title=meeting.title,
                    excerpt=_make_excerpt(excerpt_text),
                ))

        in_scope: list[Meeting] = list(title_matched_meetings)
        if meeting_ids:
            selected = (
                db.query(Meeting)
                .filter(Meeting.id.in_(meeting_ids), Meeting.workspace_id == workspace_id)
                .all()
            )
            by_id = {m.id: m for m in selected}
            for mid in meeting_ids:
                if mid in by_id and by_id[mid] not in in_scope:
                    in_scope.append(by_id[mid])

        selected_for_prompt: list[dict] = []

        no_content_meetings: list[dict] = []

        if in_scope:
            for meeting in in_scope:
                meeting_date = meeting.created_at.strftime("%Y-%m-%d")
                selected_for_prompt.append({
                    "meeting_title": meeting.title,
                    "meeting_date": meeting_date,
                    "status": meeting.status,
                })

                contributed = False

                if meeting.summary_text:
                    excerpts_for_prompt.append({
                        "kind": "summary",
                        "text": meeting.summary_text,
                        "meeting_title": meeting.title,
                        "meeting_date": meeting_date,
                    })
                    _add_source(meeting, meeting.summary_text)
                    contributed = True

                matched_chunks = (
                    db.query(TranscriptChunk)
                    .filter(
                        TranscriptChunk.workspace_id == workspace_id,
                        TranscriptChunk.meeting_id == meeting.id,
                    )
                    .order_by(distance_col)
                    .limit(TOP_K_CHUNKS)
                    .all()
                )
                for chunk in matched_chunks:
                    excerpts_for_prompt.append({
                        "kind": "transcript",
                        "text": chunk.chunk_text,
                        "meeting_title": meeting.title,
                        "meeting_date": meeting_date,
                    })
                    _add_source(meeting, chunk.chunk_text)
                    contributed = True

                if not contributed:
                    no_content_meetings.append({
                        "meeting_title": meeting.title,
                        "meeting_date": meeting_date,
                        "status": meeting.status,
                    })
        else:

            candidate_query = (
                db.query(TranscriptChunk, distance_col.label("distance"))
                .filter(TranscriptChunk.workspace_id == workspace_id)
            )
            candidate_results = (
                candidate_query.order_by(distance_col).limit(CANDIDATE_POOL_SIZE).all()
            )
            candidates = [(chunk, distance) for chunk, distance in candidate_results if distance <= MAX_RELEVANT_DISTANCE]

            if candidates:
                meeting_ids_set = {chunk.meeting_id for chunk, _ in candidates}
                meetings = (
                    db.query(Meeting)
                    .filter(Meeting.id.in_(meeting_ids_set), Meeting.workspace_id == workspace_id)
                    .all()
                )
                meetings_by_id = {m.id: m for m in meetings}

                ranked = []
                for chunk, distance in candidates:
                    meeting = meetings_by_id.get(chunk.meeting_id)
                    if meeting is None:
                        continue
                    adjusted_distance = distance - _recency_bonus(meeting.created_at)
                    ranked.append((adjusted_distance, chunk, meeting))

                ranked.sort(key=lambda r: r[0])
                top_ranked = ranked[:TOP_K_CHUNKS]

                for _, chunk, meeting in top_ranked:
                    meeting_date = meeting.created_at.strftime("%Y-%m-%d")
                    excerpts_for_prompt.append({
                        "kind": "transcript",
                        "text": chunk.chunk_text,
                        "meeting_title": meeting.title,
                        "meeting_date": meeting_date,
                    })
                    _add_source(meeting, chunk.chunk_text)

        messages = build_rag_messages(
            history,
            excerpts_for_prompt,
            question,
            selected_meetings=selected_for_prompt or None,
            no_content_meetings=no_content_meetings or None,
        )
        answer = generate_chat_completion(messages)

        db.add(ChatMessage(session_id=session.id, workspace_id=workspace_id, role="user", content=question))
        db.add(ChatMessage(
            session_id=session.id, workspace_id=workspace_id,
            role="assistant", content=answer,
            sources=[s.model_dump(mode="json") for s in sources] if sources else None,
        ))

        session.updated_at = datetime.now(timezone.utc)
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return ChatResponse(session_id=session.id, answer=answer, sources=sources or None)

@router.get(
    "/meetings",
    response_model=list[MeetingSummary],
    summary="List meetings available for chat in this workspace",
    description="Returns all 'ready' meetings in the workspace with their title, date, and summary for the chat UI meeting catalog.",
)
async def list_chat_meetings(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: WorkspaceMember = Depends(get_workspace_membership),
):
    """
    Get a catalog of all completed meetings in this workspace.
    Used by the chat frontend to show users what meetings are available to ask about.
    """
    meetings = (
        db.query(Meeting)
        .filter(
            Meeting.workspace_id == workspace_id,
            Meeting.status == "ready",
        )
        .order_by(Meeting.created_at.desc())
        .all()
    )

    return [
        MeetingSummary(
            id=m.id,
            title=m.title,
            status=m.status,
            created_at=m.created_at,
            summary_text=m.summary_text,
        )
        for m in meetings
    ]

@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingSummary,
    summary="Get a specific meeting for chat",
    description="Returns a single meeting's details for the chat UI.",
)
async def get_chat_meeting(
    workspace_id: uuid.UUID,
    meeting_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: WorkspaceMember = Depends(get_workspace_membership),
):
    """
    Get a single meeting's details for chat context.
    """
    meeting = (
        db.query(Meeting)
        .filter(
            Meeting.id == meeting_id,
            Meeting.workspace_id == workspace_id,
            Meeting.status == "ready",
        )
        .first()
    )

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return MeetingSummary(
        id=meeting.id,
        title=meeting.title,
        status=meeting.status,
        created_at=meeting.created_at,
        summary_text=meeting.summary_text,
    )

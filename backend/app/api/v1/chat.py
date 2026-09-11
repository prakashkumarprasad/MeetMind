# Chat routes: multi-meeting RAG queries, chat sessions/messages, and meeting context selection.

import uuid
import re
from datetime import datetime, timezone

import numpy as np

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

_STOP_WORDS = frozenset({
    "what", "was", "are", "were", "the", "a", "an", "in", "on", "at",
    "to", "for", "of", "and", "or", "its", "this", "that", "about",
    "from", "by", "with", "did", "does", "have", "has", "can", "could",
    "should", "would", "will", "tell", "me", "how", "when", "where",
    "why", "who", "which", "is", "it", "my", "do", "not", "but", "if",
    "so", "no", "yes", "been", "being", "be", "just", "also", "than",
    "then", "into", "over", "only", "some", "any", "all", "your",
})


def _tokenize_for_overlap(text: str) -> set[str]:
    """Lowercase, split on non-alphanumeric, filter stopwords and short tokens."""
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return {t for t in tokens if len(t) >= 5 and t not in _STOP_WORDS}


def _find_title_matched_meetings(db: Session, workspace_id: uuid.UUID, question: str) -> list[Meeting]:
    """
    Match meetings whose title is referenced in the question.

    Uses two strategies (OR'd together):
      1. Full-title word-boundary match (preserves exact-match behavior for
         queries like "what's in the new3 summary").
      2. Token-overlap: at least one non-stopword token with len >= 5 that
         appears in both the question and the title.  This catches semantic
         partial matches like "computing" matching a title about
         "Soft Computing".

    All queries filter by workspace_id to prevent cross-workspace leakage.
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

        title_lower = m.title.lower()
        # Strategy 1: full title word-boundary match
        pattern = r'\b' + re.escape(title_lower) + r'\b'
        if re.search(pattern, question_lower):
            matched.append(m)
            continue

        # Strategy 2: token overlap with minimum-length guard
        question_tokens = _tokenize_for_overlap(question)
        title_tokens = _tokenize_for_overlap(m.title)
        if question_tokens & title_tokens:
            matched.append(m)
    return matched

_METADATA_PATTERNS = [
    (re.compile(r"(?:when|what\s+date).*(?:upload|add|creat|record|submit)", re.I), "upload_date"),
    (re.compile(r"(?:when|what\s+date).*(?:transcri|process|ready|finish|complet)", re.I), "processing_date"),
    (re.compile(
        r"(?:what(?:'s|\s+is|\s+was)\s+)?(?:the\s+|this\s+|that\s+|my\s+)?"
        r"(?:title|name)\s+(?:of|for)\s+(?:the\s+|this\s+|that\s+|my\s+)?"
        r"(?:meeting|recording|upload)",
        re.I,
    ), "title"),
    (re.compile(r"(?:^|\b)(?:list|show|name)\s+(?:all\s+|my\s+|the\s+)?(?:meetings?|recordings?|uploads?)\b", re.I), "list"),
    (re.compile(r"(?:what|which)\s+(?:meetings?|recordings?|uploads?)\s+(?:have\s+I|did\s+I|do\s+I|are\s+there|is\s+there|exist)\b", re.I), "list"),
    (re.compile(r"(?:how\s+many)\s+(?:meetings?|recordings?|uploads?)\b", re.I), "count"),
]


def _detect_metadata_intent(question: str) -> str | None:
    """Return a metadata intent key if the question is purely about meeting
    logistics (upload date, title, list, count), or None if it is a content
    question that should go through RAG.  Pattern 4 (list) requires explicit
    enumeration verbs or noun-phrase construction to avoid false positives on
    ordinary content questions like 'What was discussed in the meeting?'."""
    for pattern, intent in _METADATA_PATTERNS:
        if pattern.search(question):
            return intent
    return None


def _resolve_referenced_meeting(
    question: str,
    history: list,
    meeting_ids: list[uuid.UUID] | None,
    workspace_id: uuid.UUID,
    db: Session,
) -> Meeting | None:
    """Resolve conversational references like 'this meeting', 'it', 'that
    meeting', 'my last meeting' to a concrete Meeting.

    Resolution priority:
      1. Explicit meeting_ids from the current request (already selected).
      2. Sources from the most recent assistant message in history.
      3. Sources from the most recent user message that had sources.
      4. Most recently created ready meeting in the workspace (fallback).
    """
    if meeting_ids:
        first_id = meeting_ids[0]
        meeting = db.query(Meeting).filter(
            Meeting.id == first_id,
            Meeting.workspace_id == workspace_id,
        ).first()
        if meeting:
            return meeting

    for msg in reversed(history):
        if msg.role == "assistant" and msg.sources:
            for src in msg.sources:
                mid = src.get("meeting_id") if isinstance(src, dict) else None
                if mid:
                    meeting = db.query(Meeting).filter(
                        Meeting.id == mid,
                        Meeting.workspace_id == workspace_id,
                    ).first()
                    if meeting:
                        return meeting

    return db.query(Meeting).filter(
        Meeting.workspace_id == workspace_id,
        Meeting.status == "ready",
    ).order_by(Meeting.created_at.desc()).first()


def _resolve_metadata_intent(
    question: str,
    history: list,
    meeting_ids: list[uuid.UUID] | None,
    workspace_id: uuid.UUID,
    db: Session,
) -> dict | None:
    """Detect metadata intent and produce a deterministic answer from the DB.
    Returns None if the question is not a metadata question (caller should
    proceed with the normal RAG pipeline).

    Known limitation: mixed content+metadata questions (e.g. "When was the
    meeting uploaded and what did they discuss?") will receive only the
    metadata answer, because this path bypasses RAG entirely on a match.
    """
    intent = _detect_metadata_intent(question)
    if intent is None:
        return None

    if intent == "list":
        meetings = (
            db.query(Meeting)
            .filter(Meeting.workspace_id == workspace_id, Meeting.status == "ready")
            .order_by(Meeting.created_at.desc())
            .limit(20)
            .all()
        )
        if not meetings:
            return {"answer": "You don't have any completed meetings in this workspace yet."}
        lines = []
        for m in meetings:
            date_str = m.created_at.strftime("%Y-%m-%d")
            lines.append(f"- \"{m.title}\" (uploaded {date_str})")
        answer = "Here are your meetings:\n" + "\n".join(lines)
        return {"answer": answer}

    if intent == "count":
        count = db.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.status == "ready",
        ).count()
        word = "meeting" if count == 1 else "meetings"
        return {"answer": f"You have {count} {word} in this workspace."}

    referenced = _resolve_referenced_meeting(question, history, meeting_ids, workspace_id, db)

    if referenced is None:
        return {"answer": "I don't see any meetings in this workspace to reference. Upload a meeting first, then ask about it."}

    date_str = referenced.created_at.strftime("%Y-%m-%d")

    if intent == "upload_date":
        return {
            "answer": f"The meeting \"{referenced.title}\" was uploaded on {date_str}.",
            "meeting_ids": [str(referenced.id)],
        }

    if intent == "processing_date":
        return {
            "answer": f"The meeting \"{referenced.title}\" is currently \"{referenced.status}\".",
            "meeting_ids": [str(referenced.id)],
        }

    if intent == "title":
        return {
            "answer": f"The meeting you're referring to is titled \"{referenced.title}\".",
            "meeting_ids": [str(referenced.id)],
        }

    return None


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

        # --- Dedicated metadata-intent path (upload date, title, list, count) ---
        metadata_result = _resolve_metadata_intent(question, history, meeting_ids, workspace_id, db)
        if metadata_result is not None:
            db.add(ChatMessage(session_id=session.id, workspace_id=workspace_id, role="user", content=question))
            db.add(ChatMessage(
                session_id=session.id, workspace_id=workspace_id,
                role="assistant", content=metadata_result["answer"],
            ))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            meta_sources = None
            if metadata_result.get("meeting_ids"):
                mid = uuid.UUID(metadata_result["meeting_ids"][0])
                m = db.query(Meeting).filter(Meeting.id == mid, Meeting.workspace_id == workspace_id).first()
                if m:
                    meta_sources = [ChatSource(
                        meeting_id=m.id,
                        meeting_title=m.title,
                        excerpt=_make_excerpt(metadata_result["answer"]),
                    )]
            return ChatResponse(session_id=session.id, answer=metadata_result["answer"], sources=meta_sources)

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
            # Global semantic search: rank transcript chunks and meeting
            # summaries together against the question embedding, then pull
            # the closest items. Including summaries means a meeting whose
            # only recorded content is a summary can still be found, and it
            # populates the <selected_meetings> metadata block (title/date).
            def _cosine_distance(v1: list[float], v2: list[float]) -> float:
                a = np.asarray(v1, dtype=float)
                b = np.asarray(v2, dtype=float)
                denom = float(np.linalg.norm(a) * np.linalg.norm(b))
                if denom == 0.0:
                    return 1.0
                return 1.0 - float(np.dot(a, b) / denom)

            candidate_results = (
                db.query(TranscriptChunk, distance_col.label("distance"))
                .filter(TranscriptChunk.workspace_id == workspace_id)
                .order_by(distance_col)
                .limit(CANDIDATE_POOL_SIZE)
                .all()
            )

            ranked_pool: list[tuple[float, str, TranscriptChunk | None, Meeting | None]] = []
            for chunk, distance in candidate_results:
                if distance > MAX_RELEVANT_DISTANCE:
                    continue
                meeting = (
                    db.query(Meeting)
                    .filter(Meeting.id == chunk.meeting_id, Meeting.workspace_id == workspace_id)
                    .first()
                )
                if meeting is not None:
                    adjusted_distance = distance - _recency_bonus(meeting.created_at)
                    ranked_pool.append((adjusted_distance, "transcript", chunk, meeting))

            summary_meetings = (
                db.query(Meeting)
                .filter(
                    Meeting.workspace_id == workspace_id,
                    Meeting.status == "ready",
                    Meeting.summary_text.isnot(None),
                )
                .all()
            )
            # Batch-encode all summaries in one forward pass instead of
            # one call per meeting — SentenceTransformer handles lists natively.
            if summary_meetings:
                summary_texts = [m.summary_text for m in summary_meetings]
                summary_embeddings = _embedding_model.encode(summary_texts)
                for meeting, summary_emb in zip(summary_meetings, summary_embeddings):
                    summary_distance = _cosine_distance(question_embedding, summary_emb.tolist())
                    # The distance gate runs BEFORE the ranking bonus.
                    # A summary with distance > MAX_RELEVANT_DISTANCE is
                    # rejected here; the −0.05 bonus only determines rank
                    # among summaries that already pass the gate.
                    if summary_distance <= MAX_RELEVANT_DISTANCE:
                        adjusted_distance = summary_distance - 0.05 - _recency_bonus(meeting.created_at)
                        ranked_pool.append((adjusted_distance, "summary", None, meeting))

            ranked_pool.sort(key=lambda item: item[0])

            for _, kind, chunk, meeting in ranked_pool[: TOP_K_CHUNKS * 2]:
                if meeting is None:
                    continue
                meeting_date = meeting.created_at.strftime("%Y-%m-%d")
                if kind == "summary":
                    if meeting.summary_text:
                        excerpts_for_prompt.append({
                            "kind": "summary",
                            "text": meeting.summary_text,
                            "meeting_title": meeting.title,
                            "meeting_date": meeting_date,
                        })
                        _add_source(meeting, meeting.summary_text)
                        selected_for_prompt.append({
                            "meeting_title": meeting.title,
                            "meeting_date": meeting_date,
                            "status": meeting.status,
                        })
                elif chunk is not None:
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

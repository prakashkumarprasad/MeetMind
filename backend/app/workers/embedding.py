# Celery task that chunks and embeds a raw transcript into pgvector.

from sentence_transformers import SentenceTransformer

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.transcript_chunk import TranscriptChunk

_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

CHUNK_SIZE_WORDS = 200
CHUNK_OVERLAP_WORDS = 30

if CHUNK_OVERLAP_WORDS >= CHUNK_SIZE_WORDS:
    raise ValueError("CHUNK_OVERLAP_WORDS must be smaller than CHUNK_SIZE_WORDS, or chunking will never finish.")

def _split_into_chunks(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE_WORDS
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start = end - CHUNK_OVERLAP_WORDS

    return chunks

@celery_app.task(name="embed_meeting")
def embed_meeting(meeting_id: str):
    db = SessionLocal()
    meeting = None
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None or not meeting.transcript_text:
            return

        chunks = _split_into_chunks(meeting.transcript_text)
        embeddings = _embedding_model.encode(chunks)

        for index, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(TranscriptChunk(
                meeting_id=meeting.id,
                workspace_id=meeting.workspace_id,
                chunk_text=chunk_text,
                chunk_index=index,
                embedding=embedding.tolist(),
            ))

        meeting.status = "summarizing"
        db.commit()

        from app.workers.summarization import summarize_meeting
        summarize_meeting.delay(str(meeting.id))

    except Exception:
        if meeting is not None:
            meeting.status = "failed"
            db.commit()
        raise
    finally:
        db.close()

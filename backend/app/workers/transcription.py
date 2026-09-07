# Celery task that downloads media, converts video to audio, and transcribes with Whisper.

import os
import subprocess
import sys
import tempfile

if sys.platform == "win32":
    import nvidia.cublas
    import nvidia.cudnn
    import nvidia.cuda_runtime
    import nvidia.nvjitlink

    _dll_dirs = [
        os.path.join(nvidia.cublas.__path__[0], "bin"),
        os.path.join(nvidia.cudnn.__path__[0], "bin"),
        os.path.join(nvidia.cuda_runtime.__path__[0], "bin"),
        os.path.join(nvidia.nvjitlink.__path__[0], "bin"),
    ]
    os.environ["PATH"] = os.pathsep.join(_dll_dirs) + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.services.s3 import s3_client
from app.core.config import settings

_model = WhisperModel("medium", device="cuda", compute_type="float16")

EXTENSION_BY_MIME = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

def convert_video_to_audio(input_path: str, output_path: str) -> None:
    """
    Extract the audio track from a video file with ffmpeg, downsampled to
    16 kHz mono WAV — the format faster-whisper likes best. Raises
    subprocess.CalledProcessError if ffmpeg can't handle the file (e.g. a
    video with no audio stream), which the caller translates into a "failed"
    meeting with a helpful error message.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            output_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

@celery_app.task(name="transcribe_meeting")
def transcribe_meeting(meeting_id: str):
    db = SessionLocal()
    meeting = None
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return

        meeting.status = "transcribing"
        db.commit()

        extension = EXTENSION_BY_MIME.get(meeting.content_type, ".bin")

        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, f"media_file{extension}")
            s3_client.download_file(settings.S3_BUCKET_NAME, meeting.storage_key, source_path)

            if meeting.source_media_type == "video":
                meeting.status = "converting"
                db.commit()

                wav_path = os.path.join(tmp_dir, "converted_audio.wav")
                convert_video_to_audio(source_path, wav_path)
                transcribe_path = wav_path
            else:
                transcribe_path = source_path

            segments, _info = _model.transcribe(transcribe_path, task="translate")
            full_text = " ".join(segment.text.strip() for segment in segments)

        meeting.transcript_text = full_text
        meeting.status = "validating"
        db.commit()

        from app.workers.embedding import embed_meeting
        embed_meeting.delay(str(meeting.id))

    except Exception as exc:
        if meeting is not None:
            meeting.status = "failed"
            meeting.error_message = _friendly_error(exc)
            db.commit()
        raise
    finally:
        db.close()

def _friendly_error(exc: Exception) -> str:
    """Map low-level pipeline failures to a human-readable reason."""
    if isinstance(exc, subprocess.CalledProcessError):
        return (
            "We couldn't process this video — it may not contain an audio track "
            "or may use an unsupported codec."
        )
    text = str(exc)
    if "download" in text.lower():
        return "The uploaded file couldn't be downloaded from storage."
    return "An unexpected error occurred while processing this meeting."

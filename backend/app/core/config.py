# Application settings loaded from environment variables via pydantic-settings.

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    APP_NAME: str = "MeetMind"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Refresh-token rotation is guarded by reuse detection: replaying an
    # already-rotated token revokes the whole family. However, multiple open
    # tabs / parallel requests legitimately present the *same* token at once,
    # which the old code mistook for theft and revoked -> users were randomly
    # logged out. This grace window lets concurrent rotations through while
    # still catching a genuinely stolen token replayed after the window.
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/api/auth/callback/google"

    DATABASE_URL: str

    REDIS_URL: str

    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "openai/gpt-oss-20b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    S3_ENDPOINT_URL: str = ""
    S3_BUCKET_NAME: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"

    MAX_UPLOAD_SIZE_MB: int = 500

    MAX_VIDEO_UPLOAD_SIZE_MB: int = 2048

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ALLOWED_AUDIO_MIME_TYPES: set[str] = {
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/x-m4a",
        "audio/ogg",
        "audio/webm",
    }

    ALLOWED_VIDEO_MIME_TYPES: set[str] = {
        "video/mp4",
        "video/webm",
        "video/quicktime",
    }

    SENTRY_DSN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    """Cached so we parse .env once, not on every request."""
    return Settings()

settings = get_settings()

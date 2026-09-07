# Celery application config for the transcribe/embed/summarize task chain.

from celery import Celery

from app.core.config import settings

import app.models  # noqa: F401

celery_app = Celery(
    "meetmind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.transcription",
        "app.workers.embedding",
        "app.workers.summarization",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    broker_use_ssl={"ssl_cert_reqs": "required"},
    redis_backend_use_ssl={"ssl_cert_reqs": "required"},
)

# S3-compatible storage client and presigned URL generation for uploads/downloads.

import uuid

import boto3

from app.core.config import settings

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT_URL or None,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

UPLOAD_URL_EXPIRY_SECONDS = 3600
DOWNLOAD_URL_EXPIRY_SECONDS = 3600


def generate_upload_key() -> str:
    """
    Always generate our own internal filename - never use anything
    from the user (original filename, extension, etc). This is what
    goes into S3 and later gets passed to ffmpeg.
    """
    return f"audio/{uuid.uuid4()}"


def create_presigned_upload(storage_key: str, max_size_mb: int | None = None) -> dict:
    """
    Returns a presigned POST: a URL plus a set of form fields the
    frontend must send along with the file. The size condition here
    is enforced by S3 itself, not just our own backend code.
    """
    default_max = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    max_bytes = (max_size_mb * 1024 * 1024) if max_size_mb else default_max

    presigned = s3_client.generate_presigned_post(
        Bucket=settings.S3_BUCKET_NAME,
        Key=storage_key,
        Conditions=[["content-length-range", 1, max_bytes]],
        ExpiresIn=UPLOAD_URL_EXPIRY_SECONDS,
    )

    return presigned


def generate_download_url(storage_key: str) -> str:
    """
    Short-lived URL to let the frontend play back the audio file.
    Never expose the bucket publicly - always go through this.
    """
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": storage_key},
        ExpiresIn=DOWNLOAD_URL_EXPIRY_SECONDS,
    )


def delete_object(storage_key: str) -> None:
    s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key)

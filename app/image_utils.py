"""Profile image processing and S3 upload/delete helpers.

Pillow does the CPU-heavy image work; boto3 talks to S3 (or the local moto
server when ``aws_endpoint_url`` is set). The boto3 calls are synchronous, so
the public async functions run them in a threadpool to avoid blocking the
event loop.
"""

import uuid
from io import BytesIO

import boto3
from mypy_boto3_s3 import S3Client
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from app.config import settings


def _get_s3_client() -> S3Client:
    client_kwargs: dict[str, object] = {
        "region_name": settings.aws_default_region,
        "aws_access_key_id": settings.aws_access_key_id.get_secret_value()
        if settings.aws_access_key_id
        else None,
        "aws_secret_access_key": settings.aws_secret_access_key.get_secret_value()
        if settings.aws_secret_access_key
        else None,
    }
    # Only pass endpoint_url when one is configured. Empty string (unset env
    # var) must mean "use AWS defaults / whichever patched provider is active"
    # -- botocore raises ``ValueError: Invalid endpoint`` on empty string.
    if settings.aws_endpoint_url:
        client_kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **client_kwargs)


def process_profile_image(content: bytes) -> tuple[bytes, str]:
    """Normalize an uploaded image and return (jpeg_bytes, unique_filename).

    Fixes camera orientation from EXIF data, crops to a square 300x300 with
    Lanczos resampling, and flattens alpha modes to RGB so JPEG is safe.
    """
    with Image.open(BytesIO(content)) as image_content:
        img_orientation_fix = ImageOps.exif_transpose(image_content)
        img_cropped = ImageOps.fit(
            img_orientation_fix, (300, 300), method=Image.Resampling.LANCZOS
        )

        if img_cropped.mode in ["RGBA", "LA", "P"]:
            img_cropped = img_cropped.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg"

        byte_object = BytesIO()
        img_cropped.save(byte_object, "JPEG", quality=85, optimize=True)
        byte_object.seek(0)

        return byte_object.read(), filename


def _upload_to_s3(file_bytes: bytes, object_key: str) -> None:
    """Upload raw bytes to the configured bucket under ``object_key``."""
    s3 = _get_s3_client()
    s3.upload_fileobj(
        BytesIO(file_bytes),
        settings.aws_bucket_name,
        object_key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )


def _delete_from_s3(object_key: str) -> None:
    """Delete ``object_key`` from the configured bucket."""
    s3 = _get_s3_client()
    s3.delete_object(Bucket=settings.aws_bucket_name, Key=object_key)


def generate_presigned_url(object_key: str) -> str:
    """Build an expiring GET URL for ``object_key``; the bucket stays private.

    Presigning is pure request signing (no network), so it works against both
    real AWS and the local moto server. The URL is only valid for
    ``aws_presign_expiry_seconds`` (default 15 minutes).
    """
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.aws_bucket_name, "Key": object_key},
        ExpiresIn=settings.aws_presign_expiry_seconds,
    )


async def upload_profile_image(file_bytes: bytes, filename: str) -> None:
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_upload_to_s3, file_bytes, key)


async def delete_profile_image(filename: str | None) -> None:
    if filename is None:
        return
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_delete_from_s3, key)
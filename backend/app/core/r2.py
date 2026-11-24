"""Cloudflare R2 client (S3-compatible, via boto3).

Kept separate from route handlers and from the storage service. Credentials come ONLY from
environment-based settings and are never sent to the frontend or logged. boto3 clients are
thread-safe, so one cached client is shared by all request threads.
"""
from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import Settings


class StorageNotConfiguredError(RuntimeError):
    pass


@lru_cache(maxsize=4)
def _build_client(endpoint_url: str, access_key_id: str, secret_access_key: str, region: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(
            region_name=region,                 # R2 uses "auto"
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
            # Recent boto3 versions add checksum headers by default, which R2 had trouble with.
            # Only send/validate them when an operation requires it.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def get_r2_client(settings: Settings):
    if not settings.r2_configured:
        raise StorageNotConfiguredError("Cloudflare R2 is not configured.")
    return _build_client(settings.r2_endpoint_url, settings.r2_access_key_id,
                         settings.r2_secret_access_key, settings.r2_region)

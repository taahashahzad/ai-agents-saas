"""Object storage service on top of Cloudflare R2.

Services depend on this small interface (upload_bytes / download_bytes / delete), not on boto3,
so tests can swap in a fake and a different mechanism (e.g. direct browser-to-R2 presigned
uploads) can later be added next to it without touching routes or business logic.
Raw boto3 exceptions never leave this module: callers only see StorageError. Only the S3 error
CODE is logged (never messages, keys, credentials or document content).
"""
import logging

from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}
_MAX_KEY_LENGTH = 1024


class StorageError(Exception):
    """Storage operation failed (details are logged without secrets, never sent to clients)."""


class StorageObjectNotFound(StorageError):
    pass


def _code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code", "unknown"))
    return type(exc).__name__


def _check_key(key: str) -> None:
    """Defense in depth: keys are built by the server, but never let a bad one reach R2."""
    if not key or key.startswith("/") or ".." in key or len(key) > _MAX_KEY_LENGTH:
        raise StorageError("invalid object key")


class R2Storage:
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def upload_bytes(self, path: str, data: bytes, content_type: str) -> None:
        _check_key(path)
        try:
            self._client.put_object(Bucket=self._bucket, Key=path, Body=data, ContentType=content_type)
        except (ClientError, BotoCoreError) as exc:
            logger.error("R2 upload failed (%s)", _code(exc))
            raise StorageError("upload failed") from exc

    def download_bytes(self, path: str) -> bytes:
        _check_key(path)
        try:
            body = self._client.get_object(Bucket=self._bucket, Key=path)["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except ClientError as exc:
            if _code(exc) in _NOT_FOUND_CODES:
                raise StorageObjectNotFound("object not found") from exc
            logger.error("R2 download failed (%s)", _code(exc))
            raise StorageError("download failed") from exc
        except BotoCoreError as exc:
            logger.error("R2 download failed (%s)", _code(exc))
            raise StorageError("download failed") from exc

    def delete(self, path: str) -> None:
        """Idempotent: S3/R2 report success when the object is already gone."""
        _check_key(path)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=path)
        except (ClientError, BotoCoreError) as exc:
            if _code(exc) in _NOT_FOUND_CODES:
                return
            logger.error("R2 delete failed (%s)", _code(exc))
            raise StorageError("delete failed") from exc

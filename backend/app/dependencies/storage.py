from fastapi import Depends

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.core.r2 import StorageNotConfiguredError, get_r2_client
from app.core.storage import R2Storage
from app.dependencies.settings import get_app_settings


def get_storage(settings: Settings = Depends(get_app_settings)) -> R2Storage:
    """Object storage dependency (overridden with a fake in tests). Only routes that touch files
    depend on it, so metadata-only routes work even if R2 is not configured."""
    try:
        return R2Storage(get_r2_client(settings), settings.r2_bucket_name)
    except StorageNotConfiguredError:
        raise ServiceUnavailableError("File storage is not configured on the server.",
                                      code="storage_not_configured")

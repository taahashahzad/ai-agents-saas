"""Firebase Admin SDK initialisation (idempotent, lazy)."""
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

from app.core.config import get_settings


def init_firebase() -> firebase_admin.App:
    """Initialise the default Firebase app once.

    * FIREBASE_CREDENTIALS_PATH set  -> service-account JSON file (local development)
    * otherwise                      -> Application Default Credentials
                                        (Cloud Run / GCE / GOOGLE_APPLICATION_CREDENTIALS)
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    settings = get_settings()
    options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None

    if settings.firebase_credentials_path:
        path = Path(settings.firebase_credentials_path).expanduser()
        if not path.is_file():
            # Message intentionally excludes file contents.
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_PATH is set but does not point to an existing file."
            )
        cred = credentials.Certificate(str(path))
    else:
        cred = credentials.ApplicationDefault()

    return firebase_admin.initialize_app(cred, options)


@lru_cache
def get_firestore() -> Client:
    init_firebase()
    return firestore.client()

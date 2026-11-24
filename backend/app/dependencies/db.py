from google.cloud.firestore import Client

from app.core.firebase import get_firestore


def get_db() -> Client:
    """Firestore client dependency (overridden with a fake in tests)."""
    return get_firestore()

from datetime import datetime, timezone

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore import Client

from app.core.security import AuthenticatedUser
from app.schemas.user import UserOut, UserUpsert

USERS = "users"


def _out(data: dict, user: AuthenticatedUser) -> UserOut:
    # platform_role is taken from the verified token, never from Firestore or the client.
    return UserOut.model_validate({**data, "platform_role": user.platform_role})


def get_profile(db: Client, user: AuthenticatedUser) -> UserOut | None:
    snap = db.collection(USERS).document(user.uid).get()
    if not snap.exists:
        return None
    return _out(snap.to_dict(), user)


def upsert_profile(db: Client, user: AuthenticatedUser, payload: UserUpsert) -> tuple[UserOut, bool]:
    """Create the caller's profile, or refresh it if it already exists.

    Returns (profile, created). Document ID, uid and email come from the verified token.
    `create()` is atomic: it fails with AlreadyExists instead of overwriting, so
    created_at can never be reset by a second call.
    """
    ref = db.collection(USERS).document(user.uid)
    now = datetime.now(timezone.utc)
    data = {
        "uid": user.uid,
        "email": user.email,
        "display_name": payload.display_name or user.name,
        "created_at": now,
        "updated_at": now,
    }
    try:
        ref.create(data)
        return _out(data, user), True
    except AlreadyExists:
        updates: dict = {"email": user.email, "updated_at": now}
        if payload.display_name is not None:
            updates["display_name"] = payload.display_name
        ref.update(updates)
        return _out(ref.get().to_dict(), user), False

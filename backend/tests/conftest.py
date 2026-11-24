from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth

from app.core import security, transactions
from app.core.config import Settings
from app.dependencies.db import get_db
from app.dependencies.storage import get_storage
from app.main import create_app
from tests.fake_firestore import FakeFirestore
from tests.fake_storage import FakeStorage

ALLOWED_ORIGIN = "http://localhost:5173"

# token string -> verified claims (what Firebase would return for a valid ID token)
TOKENS = {
    "token-alice": {"uid": "alice-uid", "email": "alice@example.com", "name": "Alice A", "email_verified": True},
    "token-bob": {"uid": "bob-uid", "email": "bob@example.com", "email_verified": True},
    "token-carol": {"uid": "carol-uid", "email": "carol@example.com", "email_verified": True},
    "token-dave": {"uid": "dave-uid", "email": "Dave@Example.com", "email_verified": True},  # mixed case
    "token-eve": {"uid": "eve-uid", "email": "eve@example.com", "email_verified": False},
    "token-root": {"uid": "root-uid", "email": "root@example.com", "email_verified": True,
                   "platform_role": "system_admin"},
    # A client-forged-looking claim value must NOT grant anything:
    "token-fake": {"uid": "fake-uid", "email": "fake@example.com", "email_verified": True,
                   "platform_role": "superuser"},
}

EMAILS = {"alice": "alice@example.com", "bob": "bob@example.com", "carol": "carol@example.com",
          "dave": "dave@example.com"}


def fake_verify_id_token(token, check_revoked=False, **_):
    if token in TOKENS:
        return dict(TOKENS[token])
    if token == "expired":
        raise auth.ExpiredIdTokenError("expired", None)
    if token == "revoked":
        raise auth.RevokedIdTokenError("revoked")
    if token == "disabled":
        raise auth.UserDisabledError("disabled")
    if token == "certs-down":
        raise auth.CertificateFetchError("down", None)
    raise auth.InvalidIdTokenError("garbage")


def bearer(user: str) -> dict:
    return {"Authorization": f"Bearer token-{user}"}


def add_member(fake_db, business_id, user, role="member"):
    """Seed a membership directly (bypassing the API) for `user` e.g. "bob"."""
    uid = f"{user}-uid"
    fake_db.docs[f"businesses/{business_id}/members/{uid}"] = {
        "uid": uid, "role": role, "joined_at": datetime.now(timezone.utc), "email": EMAILS.get(user)}


@pytest.fixture
def fake_db():
    return FakeFirestore()


@pytest.fixture
def fake_storage():
    return FakeStorage()


@pytest.fixture
def client(fake_db, fake_storage, monkeypatch):
    monkeypatch.setattr(security, "init_firebase", lambda: None)
    monkeypatch.setattr(security.auth, "verify_id_token", fake_verify_id_token)
    # Real Firestore transactions need a live backend; tests run the same function against the fake.
    monkeypatch.setattr(transactions, "run_in_transaction", lambda db, fn: fn(db.transaction()))
    settings = Settings(app_env="test", cors_origins=[ALLOWED_ORIGIN], firebase_credentials_path=None,
                        firebase_project_id=None, check_token_revoked=False, log_level="WARNING",
                        require_verified_email=True, invitation_ttl_days=7,
                        max_upload_bytes=200_000)  # no R2 credentials: tests never touch real storage
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_storage] = lambda: fake_storage
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_business(client):
    """Create a business as `user` through the API; returns the response JSON."""
    def _make(user="alice", **overrides):
        body = {"name": "Chez Alice", "business_type": "restaurant", "description": "Bistro", **overrides}
        r = client.post("/api/v1/businesses", json=body, headers=bearer(user))
        assert r.status_code == 201, r.text
        return r.json()
    return _make

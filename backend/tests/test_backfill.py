from datetime import datetime, timezone

from scripts.backfill_phase2 import backfill
from tests.fake_firestore import FakeFirestore

NOW = datetime.now(timezone.utc)


def seed():
    db = FakeFirestore()
    db.docs["users/u1"] = {"uid": "u1", "email": "U1@Example.com", "created_at": NOW}
    db.docs["users/u2"] = {"uid": "u2", "email": "u2@example.com", "created_at": NOW, "updated_at": NOW}
    db.docs["businesses/b1/members/u1"] = {"uid": "u1", "role": "owner", "joined_at": NOW}
    db.docs["businesses/b1/members/u2"] = {"uid": "u2", "role": "member", "joined_at": NOW, "email": "keep@x.com"}
    db.docs["businesses/b1/members/u3"] = {"uid": "u3", "role": "member", "joined_at": NOW}
    db.docs["teams/t1/members/u1"] = {"uid": "u1", "role": "x"}  # unrelated collection: untouched
    return db


def test_dry_run_changes_nothing():
    db = seed()
    before = {k: dict(v) for k, v in db.docs.items()}
    stats = backfill(db, lambda uid: None, apply=False)
    assert stats == {"users_updated": 1, "members_updated": 1, "members_without_email": 1}
    assert db.docs == before


def test_apply_is_correct_and_idempotent():
    db = seed()
    backfill(db, lambda uid: {"u3": "U3@Example.com"}.get(uid), apply=True)
    assert db.docs["users/u1"]["updated_at"] == NOW
    assert db.docs["businesses/b1/members/u1"]["email"] == "u1@example.com"   # from users doc, normalized
    assert db.docs["businesses/b1/members/u2"]["email"] == "keep@x.com"       # existing value kept
    assert db.docs["businesses/b1/members/u3"]["email"] == "u3@example.com"   # from Firebase Auth fallback
    assert "email" not in db.docs["teams/t1/members/u1"]
    assert backfill(db, lambda uid: None, apply=True) == {
        "users_updated": 0, "members_updated": 0, "members_without_email": 0}

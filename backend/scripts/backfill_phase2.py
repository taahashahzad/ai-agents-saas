"""One-off, idempotent migration for data created before Phase 2.

* users/{uid}                    -> add `updated_at` (copied from `created_at`) if missing
* businesses/*/members/{uid}     -> add normalized `email` if missing

Optional but recommended: the API works without it (it falls back to the users/ document),
but the "already a member" invitation check can only see members that have an `email`.

Run from backend/ (same .env as the API). Dry run by default:

    python -m scripts.backfill_phase2            # show what would change
    python -m scripts.backfill_phase2 --apply    # write changes
"""
import argparse
from typing import Callable

from app.core.emails import normalize_email


def backfill(db, get_auth_email: Callable[[str], str | None] | None = None, apply: bool = False) -> dict:
    stats = {"users_updated": 0, "members_updated": 0, "members_without_email": 0}

    emails: dict[str, str | None] = {}
    for snap in db.collection("users").stream():
        data = snap.to_dict()
        emails[snap.id] = normalize_email(data.get("email"))
        if "updated_at" not in data and data.get("created_at") is not None:
            stats["users_updated"] += 1
            if apply:
                snap.reference.update({"updated_at": data["created_at"]})

    for snap in db.collection_group("members").stream():
        business_ref = snap.reference.parent.parent
        if business_ref is None or business_ref.parent.id != "businesses":
            continue
        data = snap.to_dict()
        if data.get("email"):
            continue
        email = emails.get(snap.id) or (normalize_email(get_auth_email(snap.id)) if get_auth_email else None)
        if not email:
            stats["members_without_email"] += 1
            continue
        stats["members_updated"] += 1
        if apply:
            snap.reference.update({"email": email})
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    from firebase_admin import auth

    from app.core.firebase import get_firestore

    def auth_email(uid: str) -> str | None:
        try:
            return auth.get_user(uid).email
        except Exception:
            return None

    stats = backfill(get_firestore(), auth_email, apply=args.apply)
    print(("APPLIED" if args.apply else "DRY RUN"), stats)


if __name__ == "__main__":
    main()

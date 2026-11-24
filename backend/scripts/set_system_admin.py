"""Grant or revoke the platform-level System Admin role. Server-side ONLY.

The role is stored as a Firebase custom claim (platform_role="system_admin") and is
read from the verified ID token. There is deliberately no API endpoint for this.

Run from backend/ with credentials configured (same .env as the API):

    python -m scripts.set_system_admin <firebase-uid>            # grant
    python -m scripts.set_system_admin <firebase-uid> --revoke   # revoke

The user must sign out/in (or call getIdToken(true)) to receive the new claim.
"""
import argparse

from firebase_admin import auth

from app.core.firebase import init_firebase
from app.core.security import SYSTEM_ADMIN


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("uid")
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()

    init_firebase()
    user = auth.get_user(args.uid)
    claims = dict(user.custom_claims or {})  # keep any other claims
    if args.revoke:
        claims.pop("platform_role", None)
    else:
        claims["platform_role"] = SYSTEM_ADMIN
    auth.set_custom_user_claims(args.uid, claims or None)
    print(f"{'Revoked' if args.revoke else 'Granted'} {SYSTEM_ADMIN} for uid={args.uid} ({user.email})")


if __name__ == "__main__":
    main()

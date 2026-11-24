"""Firebase ID token verification."""
import logging
from dataclasses import dataclass

from firebase_admin import auth

from app.core.errors import AuthenticationError, ServiceUnavailableError
from app.core.firebase import init_firebase

logger = logging.getLogger(__name__)

SYSTEM_ADMIN = "system_admin"


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity taken ONLY from a verified Firebase ID token."""
    uid: str
    email: str | None
    name: str | None = None
    email_verified: bool = False
    # Platform-level role. Comes ONLY from a Firebase custom claim set server-side
    # (see scripts/set_system_admin.py). It is never read from the request body or Firestore.
    platform_role: str | None = None


@dataclass(frozen=True)
class InviteeIdentity:
    """Identity used to match invitations: UID + normalized, (optionally) verified email."""
    uid: str
    email: str


def verify_firebase_token(token: str, check_revoked: bool = False) -> AuthenticatedUser:
    init_firebase()
    try:
        decoded = auth.verify_id_token(token, check_revoked=check_revoked)
    except auth.ExpiredIdTokenError:
        raise AuthenticationError("The authentication token has expired.", code="token_expired")
    except auth.RevokedIdTokenError:
        raise AuthenticationError("The authentication token has been revoked.", code="token_revoked")
    except auth.UserDisabledError:
        raise AuthenticationError("This user account is disabled.", code="user_disabled")
    except (auth.InvalidIdTokenError, ValueError):
        raise AuthenticationError("The authentication token is invalid.", code="invalid_token")
    except auth.CertificateFetchError:
        logger.error("Could not fetch Firebase public certificates")
        raise ServiceUnavailableError("Unable to verify credentials right now. Try again shortly.")

    uid = decoded.get("uid") or decoded.get("sub")
    if not uid:
        raise AuthenticationError("The authentication token is invalid.", code="invalid_token")
    return AuthenticatedUser(
        uid=uid,
        email=decoded.get("email"),
        name=decoded.get("name"),
        email_verified=bool(decoded.get("email_verified", False)),
        platform_role=SYSTEM_ADMIN if decoded.get("platform_role") == SYSTEM_ADMIN else None,
    )

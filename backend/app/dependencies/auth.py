from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.emails import normalize_email
from app.core.errors import AuthenticationError, ForbiddenError
from app.core.security import (
    SYSTEM_ADMIN,
    AuthenticatedUser,
    InviteeIdentity,
    verify_firebase_token,
)

# auto_error=False so that we control the error body (consistent 401 format).
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    """Protects a route. Sync on purpose: token verification may do blocking I/O,
    so FastAPI runs it in a worker thread."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing or malformed Authorization header. Expected 'Bearer <token>'.")
    return verify_firebase_token(
        credentials.credentials,
        check_revoked=request.app.state.settings.check_token_revoked,
    )


def get_invitee(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> InviteeIdentity:
    """Identity for invitation endpoints.

    Invitations are matched by email, so the token must carry an email and (by default)
    Firebase must have verified it; otherwise anyone could register someone else's email
    address and accept their invitations.
    """
    email = normalize_email(user.email)
    if not email:
        raise ForbiddenError("Your account has no email address.", code="email_required")
    if request.app.state.settings.require_verified_email and not user.email_verified:
        raise ForbiddenError("Verify your email address before using invitations.",
                             code="email_not_verified")
    return InviteeIdentity(uid=user.uid, email=email)


def require_platform_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """For future platform-level endpoints only. Grants no access to any business."""
    if user.platform_role != SYSTEM_ADMIN:
        raise ForbiddenError("Platform administrator access required.", code="platform_admin_required")
    return user

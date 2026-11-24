"""Reusable business-scope authorization.

    ctx = Depends(get_business_membership)                      # any member
    ctx = Depends(require_permission(Permission.MEMBERS_VIEW))  # permission-based (preferred)
    ctx = Depends(require_business_role(BusinessRole.owner))    # role-based

Every future business-scoped resource (documents, agents, conversations, integrations...)
should hang off /businesses/{business_id}/... and use one of these dependencies.
"""
from fastapi import Depends
from google.cloud.firestore import Client

from app.core.errors import ForbiddenError
from app.core.permissions import Permission, has_permission
from app.core.security import AuthenticatedUser
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.schemas.business import BusinessRole
from app.services import membership_service
from app.services.membership_service import BusinessContext


def get_business_membership(
    business_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> BusinessContext:
    """Token -> UID -> membership doc. 404 if the caller is not a member."""
    return membership_service.load_context(db, user, business_id)


def require_permission(permission: Permission):
    def dependency(ctx: BusinessContext = Depends(get_business_membership)) -> BusinessContext:
        if not has_permission(ctx.role, permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return ctx
    return dependency


def require_business_role(*roles: BusinessRole):
    allowed = set(roles)

    def dependency(ctx: BusinessContext = Depends(get_business_membership)) -> BusinessContext:
        if ctx.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action.")
        return ctx
    return dependency

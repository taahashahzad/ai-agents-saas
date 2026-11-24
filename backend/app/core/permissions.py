"""Single source of truth for RBAC.

Business roles (owner / admin / member) live on businesses/{id}/members/{uid}.
The platform role (system_admin) is separate: it comes from a Firebase custom claim and
grants NO business access by itself.
"""
from enum import Enum

from app.schemas.business import BusinessRole


class Permission(str, Enum):
    BUSINESS_VIEW = "business:view"
    BUSINESS_EDIT = "business:edit"                    # name, description
    BUSINESS_EDIT_SETTINGS = "business:edit_settings"  # owner-controlled settings (business_type)
    BUSINESS_ARCHIVE = "business:archive"
    MEMBERS_VIEW = "members:view"
    MEMBERS_REMOVE = "members:remove"
    MEMBERS_CHANGE_ROLE = "members:change_role"
    INVITATIONS_VIEW = "invitations:view"
    INVITATIONS_CREATE = "invitations:create"
    # Reserved for upcoming features: new business-scoped routes just declare one of these.
    DOCUMENTS_VIEW = "documents:view"      # list / read / download knowledge-base files
    DOCUMENTS_MANAGE = "documents:manage"  # upload / delete / retry processing
    KNOWLEDGE_VIEW = "knowledge:view"      # read structured knowledge entries
    KNOWLEDGE_MANAGE = "knowledge:manage"  # create / edit / delete structured knowledge entries
    AGENTS_MANAGE = "agents:manage"
    INTEGRATIONS_MANAGE = "integrations:manage"
    BILLING_MANAGE = "billing:manage"


P = Permission
ROLE_PERMISSIONS: dict[BusinessRole, frozenset[Permission]] = {
    BusinessRole.owner: frozenset(Permission),
    BusinessRole.admin: frozenset({
        P.BUSINESS_VIEW, P.BUSINESS_EDIT,
        P.MEMBERS_VIEW, P.MEMBERS_REMOVE,
        P.INVITATIONS_VIEW, P.INVITATIONS_CREATE,
        P.DOCUMENTS_VIEW, P.DOCUMENTS_MANAGE, P.KNOWLEDGE_VIEW, P.KNOWLEDGE_MANAGE,
        P.AGENTS_MANAGE, P.INTEGRATIONS_MANAGE,
    }),
    BusinessRole.member: frozenset({P.BUSINESS_VIEW, P.DOCUMENTS_VIEW, P.KNOWLEDGE_VIEW}),
}

# Which target roles an actor may invite / remove. Owners are never in these sets:
# an owner cannot be removed, demoted or invited through the API.
_MANAGEABLE_ROLES: dict[BusinessRole, frozenset[BusinessRole]] = {
    BusinessRole.owner: frozenset({BusinessRole.admin, BusinessRole.member}),
    BusinessRole.admin: frozenset({BusinessRole.member}),
}


def has_permission(role: BusinessRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def can_manage_member(actor_role: BusinessRole, target_role: BusinessRole) -> bool:
    """May `actor_role` remove a member who currently has `target_role`?"""
    return target_role in _MANAGEABLE_ROLES.get(actor_role, frozenset())


def can_invite_role(actor_role: BusinessRole, invited_role: BusinessRole) -> bool:
    """Owner may invite admin/member; admin may invite member only."""
    return invited_role in _MANAGEABLE_ROLES.get(actor_role, frozenset())

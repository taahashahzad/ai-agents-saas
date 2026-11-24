"""Membership = source of truth for business-level authorization.

`load_context` is the ONE place a request is tied to a business. Everything else
(permission checks, member management) builds on the BusinessContext it returns.
Member mutations re-read the actor's membership inside a transaction, so a demoted or
removed actor cannot complete a stale operation.
"""
import re
from dataclasses import dataclass

from google.cloud.firestore import Client

from app.core import transactions
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import Permission, can_manage_member, has_permission
from app.core.security import AuthenticatedUser
from app.schemas.business import BusinessRole, BusinessStatus
from app.schemas.member import MemberOut

BUSINESSES = "businesses"
MEMBERS = "members"
USERS = "users"

# Firestore auto-IDs are 20 alphanumerics. Reject anything else (and reserved "__x__" IDs,
# which make the Firestore client raise) as "not found".
BUSINESS_ID_RE = re.compile(r"^(?!__)[A-Za-z0-9_-]{1,128}$")
UID_RE = re.compile(r"^(?!__)(?!\.+$)[^/\x00-\x1f\s]{1,128}$")

_ROLE_ORDER = {BusinessRole.owner: 0, BusinessRole.admin: 1, BusinessRole.member: 2}


@dataclass(frozen=True)
class BusinessContext:
    user: AuthenticatedUser
    business_id: str
    business: dict
    role: BusinessRole


def parse_role(value) -> BusinessRole | None:
    try:
        return BusinessRole(value)
    except ValueError:
        return None


def load_context(db: Client, user: AuthenticatedUser, business_id: str) -> BusinessContext:
    """Verify the caller has a membership in the business. Non-members get 404 (not 403),
    identical to a business that does not exist, so IDs cannot be probed."""
    if not BUSINESS_ID_RE.match(business_id):
        raise NotFoundError("Business not found.")
    business_ref = db.collection(BUSINESSES).document(business_id)
    member = business_ref.collection(MEMBERS).document(user.uid).get()
    role = parse_role((member.to_dict() or {}).get("role")) if member.exists else None
    if role is None:
        raise NotFoundError("Business not found.")
    business = business_ref.get()
    if not business.exists:
        raise NotFoundError("Business not found.")
    return BusinessContext(user=user, business_id=business_id, business=business.to_dict(), role=role)


def _member_out(uid: str, data: dict, user_doc: dict | None) -> MemberOut:
    user_doc = user_doc or {}
    return MemberOut(
        uid=uid,
        email=data.get("email") or user_doc.get("email"),  # fallback for pre-Phase-2 members
        display_name=user_doc.get("display_name"),
        role=data["role"],
        joined_at=data.get("joined_at"),
    )


def list_members(db: Client, ctx: BusinessContext) -> list[MemberOut]:
    snaps = list(db.collection(BUSINESSES).document(ctx.business_id).collection(MEMBERS).stream())
    user_refs = [db.collection(USERS).document(s.id) for s in snaps]
    users = {s.id: s.to_dict() for s in db.get_all(user_refs) if s.exists} if user_refs else {}
    members = []
    for s in snaps:
        data = s.to_dict()
        if parse_role(data.get("role")) is None:
            continue
        members.append(_member_out(s.id, data, users.get(s.id)))
    members.sort(key=lambda m: (_ROLE_ORDER[m.role], str(m.joined_at or "")))
    return members


def _check_uid(uid: str) -> None:
    if not UID_RE.match(uid):
        raise NotFoundError("Member not found.", code="member_not_found")


def change_role(db: Client, ctx: BusinessContext, target_uid: str, new_role: BusinessRole) -> MemberOut:
    """Owner-only. Only member <-> admin. Ownership can never be assigned or changed here."""
    _check_uid(target_uid)
    business_ref = db.collection(BUSINESSES).document(ctx.business_id)
    actor_ref = business_ref.collection(MEMBERS).document(ctx.user.uid)
    target_ref = business_ref.collection(MEMBERS).document(target_uid)

    def fn(txn):
        actor, business, target = (actor_ref.get(transaction=txn),
                                   business_ref.get(transaction=txn),
                                   target_ref.get(transaction=txn))
        actor_role = parse_role((actor.to_dict() or {}).get("role")) if actor.exists else None
        if actor_role is None or not business.exists:
            raise NotFoundError("Business not found.")
        if not has_permission(actor_role, Permission.MEMBERS_CHANGE_ROLE):
            raise ForbiddenError("Only an owner can change member roles.")
        if business.to_dict().get("status") == BusinessStatus.archived.value:
            raise ConflictError("Archived businesses cannot be modified.", code="business_archived")
        if not target.exists:
            raise NotFoundError("Member not found.", code="member_not_found")
        data = target.to_dict()
        target_role = parse_role(data.get("role"))
        if target_role == BusinessRole.owner:
            raise ForbiddenError("The owner's role cannot be changed.", code="cannot_modify_owner")
        if new_role == BusinessRole.owner:
            raise BadRequestError("Ownership cannot be assigned through this endpoint.",
                                  code="ownership_transfer_unsupported")
        if target_role != new_role:
            txn.update(target_ref, {"role": new_role.value})
            data["role"] = new_role.value
        return data

    data = transactions.run_in_transaction(db, fn)
    user_doc = db.collection(USERS).document(target_uid).get()
    return _member_out(target_uid, data, user_doc.to_dict() if user_doc.exists else None)


def remove_member(db: Client, ctx: BusinessContext, target_uid: str) -> None:
    """Owner: may remove admins and members. Admin: may remove members only.
    The owner can never be removed; admins cannot remove admins or themselves."""
    _check_uid(target_uid)
    business_ref = db.collection(BUSINESSES).document(ctx.business_id)
    actor_ref = business_ref.collection(MEMBERS).document(ctx.user.uid)
    target_ref = business_ref.collection(MEMBERS).document(target_uid)

    def fn(txn):
        actor, business, target = (actor_ref.get(transaction=txn),
                                   business_ref.get(transaction=txn),
                                   target_ref.get(transaction=txn))
        actor_role = parse_role((actor.to_dict() or {}).get("role")) if actor.exists else None
        if actor_role is None or not business.exists:
            raise NotFoundError("Business not found.")
        if not has_permission(actor_role, Permission.MEMBERS_REMOVE):
            raise ForbiddenError("You do not have permission to remove members.")
        if business.to_dict().get("status") == BusinessStatus.archived.value:
            raise ConflictError("Archived businesses cannot be modified.", code="business_archived")
        if not target.exists:
            raise NotFoundError("Member not found.", code="member_not_found")
        target_role = parse_role(target.to_dict().get("role"))
        if target_role == BusinessRole.owner:
            raise ForbiddenError("The owner cannot be removed.", code="cannot_modify_owner")
        if target_role is None or not can_manage_member(actor_role, target_role):
            raise ForbiddenError("You cannot remove a member with this role.", code="insufficient_role")
        txn.delete(target_ref)

    transactions.run_in_transaction(db, fn)

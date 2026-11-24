"""Invitation workflow.

* One invitation document per (business, email): its ID is a hash of both. That makes
  "no duplicate pending invitation" race-free inside a transaction (the slot is a single
  document). Re-inviting after accept/decline/expiry replaces the old record.
* Accept/decline: the invitation is located via a collection-group query on `invitation_id`,
  then verified inside a transaction. A caller whose email differs gets 404 (not 403) so
  invitations cannot be probed.
* Expiry is derived at read time (pending + past expires_at => "expired").
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core import transactions
from app.core.emails import normalize_email
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import Permission, can_invite_role, has_permission
from app.core.security import InviteeIdentity
from app.schemas.business import BusinessRole, BusinessStatus
from app.schemas.invitation import InvitationCreate, InvitationOut, InvitationStatus
from app.services.membership_service import BusinessContext, parse_role

BUSINESSES = "businesses"
MEMBERS = "members"
INVITATIONS = "invitations"

_INVITATION_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_invitation_id(business_id: str, email: str) -> str:
    return hashlib.sha256(f"{business_id}:{email}".encode()).hexdigest()[:32]


def effective_status(data: dict, now: datetime) -> str:
    status = data.get("status")
    if status == InvitationStatus.pending.value and data["expires_at"] <= now:
        return InvitationStatus.expired.value
    return status


def _out(data: dict, now: datetime, business_name: str | None = None) -> InvitationOut:
    return InvitationOut.model_validate(
        {**data, "status": effective_status(data, now), "business_name": business_name})


def _is_business_child(ref) -> bool:
    biz = ref.parent.parent
    return biz is not None and biz.parent.id == BUSINESSES


# ---------------------------------------------------------------- inviter side

def create_invitation(db: Client, ctx: BusinessContext, payload: InvitationCreate,
                      ttl_days: int) -> InvitationOut:
    email = payload.email  # already normalized by the schema
    role = BusinessRole(payload.role.value)
    now = _now()
    business_ref = db.collection(BUSINESSES).document(ctx.business_id)
    members = business_ref.collection(MEMBERS)
    actor_ref = members.document(ctx.user.uid)
    invitation_id = make_invitation_id(ctx.business_id, email)
    invitation_ref = business_ref.collection(INVITATIONS).document(invitation_id)

    def fn(txn):
        actor = actor_ref.get(transaction=txn)
        business = business_ref.get(transaction=txn)
        existing = invitation_ref.get(transaction=txn)
        same_email_members = list(
            members.where(filter=FieldFilter("email", "==", email)).get(transaction=txn))

        actor_role = parse_role((actor.to_dict() or {}).get("role")) if actor.exists else None
        if actor_role is None or not business.exists:
            raise NotFoundError("Business not found.")
        if not has_permission(actor_role, Permission.INVITATIONS_CREATE):
            raise ForbiddenError("You do not have permission to invite people.")
        if business.to_dict().get("status") == BusinessStatus.archived.value:
            raise ConflictError("Archived businesses cannot be modified.", code="business_archived")
        if not can_invite_role(actor_role, role):
            raise ForbiddenError(f"You cannot invite someone as {role.value}.", code="insufficient_role")
        if same_email_members or email == normalize_email(ctx.user.email):
            raise ConflictError("This person is already a member of the business.", code="already_member")
        if existing.exists and effective_status(existing.to_dict(), now) == InvitationStatus.pending.value:
            raise ConflictError("A pending invitation already exists for this email.",
                                code="invitation_exists")

        invitation = {
            "invitation_id": invitation_id,
            "business_id": ctx.business_id,
            "email": email,
            "role": role.value,
            "invited_by": ctx.user.uid,  # from the verified token
            "status": InvitationStatus.pending.value,
            "created_at": now,
            "expires_at": now + timedelta(days=ttl_days),
            "accepted_at": None,
        }
        txn.set(invitation_ref, invitation)
        return invitation

    invitation = transactions.run_in_transaction(db, fn)
    return _out(invitation, now, ctx.business.get("name"))


def list_business_invitations(db: Client, ctx: BusinessContext) -> list[InvitationOut]:
    now = _now()
    snaps = db.collection(BUSINESSES).document(ctx.business_id).collection(INVITATIONS).stream()
    items = [_out(s.to_dict(), now, ctx.business.get("name")) for s in snaps]
    items.sort(key=lambda i: i.created_at, reverse=True)
    return items


# ---------------------------------------------------------------- invitee side

def list_my_invitations(db: Client, invitee: InviteeIdentity) -> list[InvitationOut]:
    """Pending, unexpired invitations addressed to the caller's (verified) email."""
    now = _now()
    query = db.collection_group(INVITATIONS).where(filter=FieldFilter("email", "==", invitee.email))
    pending, business_refs = [], {}
    for snap in query.stream():
        if not _is_business_child(snap.reference):
            continue
        data = snap.to_dict()
        if effective_status(data, now) != InvitationStatus.pending.value:
            continue
        business_ref = snap.reference.parent.parent
        business_refs[business_ref.id] = business_ref
        pending.append({**data, "business_id": business_ref.id})
    if not pending:
        return []

    businesses = {s.id: s.to_dict() for s in db.get_all(list(business_refs.values())) if s.exists}
    items = []
    for data in pending:
        business = businesses.get(data["business_id"])
        if business is None or business.get("status") == BusinessStatus.archived.value:
            continue
        items.append(_out(data, now, business.get("name")))
    items.sort(key=lambda i: i.created_at, reverse=True)
    return items


def _find_invitation_ref(db: Client, invitation_id: str):
    if not _INVITATION_ID_RE.match(invitation_id):
        raise NotFoundError("Invitation not found.", code="invitation_not_found")
    query = db.collection_group(INVITATIONS).where(filter=FieldFilter("invitation_id", "==", invitation_id))
    for snap in query.stream():
        if _is_business_child(snap.reference):
            return snap.reference
    raise NotFoundError("Invitation not found.", code="invitation_not_found")


def _check_actionable(data: dict, invitee: InviteeIdentity, now: datetime) -> None:
    if data.get("email") != invitee.email:
        # Someone else's invitation: indistinguishable from a missing one.
        raise NotFoundError("Invitation not found.", code="invitation_not_found")
    status = data.get("status")
    if status == InvitationStatus.accepted.value:
        raise ConflictError("This invitation has already been accepted.", code="invitation_already_accepted")
    if status == InvitationStatus.declined.value:
        raise ConflictError("This invitation has already been declined.", code="invitation_already_declined")
    if effective_status(data, now) == InvitationStatus.expired.value:
        raise ConflictError("This invitation has expired.", code="invitation_expired")


def accept_invitation(db: Client, invitee: InviteeIdentity, invitation_id: str) -> InvitationOut:
    ref = _find_invitation_ref(db, invitation_id)
    business_ref = ref.parent.parent
    member_ref = business_ref.collection(MEMBERS).document(invitee.uid)
    now = _now()

    def fn(txn):
        snap = ref.get(transaction=txn)
        business = business_ref.get(transaction=txn)
        member = member_ref.get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Invitation not found.", code="invitation_not_found")
        data = snap.to_dict()
        _check_actionable(data, invitee, now)
        role = parse_role(data.get("role"))
        if role is None or role == BusinessRole.owner:  # defensive: never mint owners
            raise ConflictError("This invitation is invalid.", code="invitation_invalid")
        if not business.exists:
            raise NotFoundError("Invitation not found.", code="invitation_not_found")
        if business.to_dict().get("status") == BusinessStatus.archived.value:
            raise ConflictError("This business has been archived.", code="business_archived")
        if member.exists:
            raise ConflictError("You are already a member of this business.", code="already_member")

        txn.create(member_ref, {"uid": invitee.uid, "role": role.value, "joined_at": now,
                                "email": invitee.email})
        txn.update(ref, {"status": InvitationStatus.accepted.value, "accepted_at": now})
        return {**data, "status": InvitationStatus.accepted.value, "accepted_at": now}, \
            business.to_dict().get("name")

    data, business_name = transactions.run_in_transaction(db, fn)
    return _out(data, now, business_name)


def decline_invitation(db: Client, invitee: InviteeIdentity, invitation_id: str) -> InvitationOut:
    ref = _find_invitation_ref(db, invitation_id)
    business_ref = ref.parent.parent
    now = _now()

    def fn(txn):
        snap = ref.get(transaction=txn)
        business = business_ref.get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Invitation not found.", code="invitation_not_found")
        data = snap.to_dict()
        _check_actionable(data, invitee, now)
        txn.update(ref, {"status": InvitationStatus.declined.value})
        return {**data, "status": InvitationStatus.declined.value}, \
            (business.to_dict() or {}).get("name")

    data, business_name = transactions.run_in_transaction(db, fn)
    return _out(data, now, business_name)

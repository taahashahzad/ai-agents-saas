"""Business CRUD. Authorization is done by the dependencies in app/dependencies/business.py
(membership lookup + permission check); this module only holds the business logic.
"""
from datetime import datetime, timezone

from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.emails import normalize_email
from app.core.errors import ConflictError, ForbiddenError
from app.core.permissions import Permission, has_permission
from app.core.security import AuthenticatedUser
from app.schemas.business import (
    BusinessCreate,
    BusinessOut,
    BusinessRole,
    BusinessStatus,
    BusinessUpdate,
)

from app.services.membership_service import BusinessContext

BUSINESSES = "businesses"
MEMBERS = "members"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(business_id: str, data: dict, role: str) -> BusinessOut:
    return BusinessOut.model_validate({**data, "id": business_id, "role": role})


def create_business(db: Client, user: AuthenticatedUser, payload: BusinessCreate) -> BusinessOut:
    now = _now()
    business_ref = db.collection(BUSINESSES).document()  # server-side generated ID
    business = {
        "name": payload.name,
        "business_type": payload.business_type.value,
        "description": payload.description,
        "owner_id": user.uid,  # from the verified token, never from the client
        "status": BusinessStatus.active.value,
        "created_at": now,
        "updated_at": now,
    }
    membership = {"uid": user.uid, "role": BusinessRole.owner.value, "joined_at": now,
                  "email": normalize_email(user.email)}

    # Atomic: either both documents are written or neither is.
    batch = db.batch()
    batch.set(business_ref, business)
    batch.set(business_ref.collection(MEMBERS).document(user.uid), membership)
    batch.commit()

    return _out(business_ref.id, business, BusinessRole.owner.value)


def list_businesses(db: Client, user: AuthenticatedUser) -> list[BusinessOut]:
    """Active businesses the caller is a member of, newest first."""
    query = db.collection_group(MEMBERS).where(filter=FieldFilter("uid", "==", user.uid))
    roles: dict[str, str] = {}
    refs = {}
    for snap in query.stream():
        business_ref = snap.reference.parent.parent
        # Guard against unrelated "members" subcollections and mismatched docs.
        if business_ref is None or business_ref.parent.id != BUSINESSES or snap.id != user.uid:
            continue
        refs[business_ref.id] = business_ref
        roles[business_ref.id] = snap.to_dict().get("role")

    if not refs:
        return []

    results = []
    for snap in db.get_all(list(refs.values())):
        if not snap.exists:
            continue
        data = snap.to_dict()
        if data.get("status") == BusinessStatus.archived.value:
            continue
        results.append(_out(snap.id, data, roles[snap.id]))
    results.sort(key=lambda b: b.created_at, reverse=True)
    return results


def get_business(ctx: BusinessContext) -> BusinessOut:
    return _out(ctx.business_id, ctx.business, ctx.role.value)


def update_business(db: Client, ctx: BusinessContext, payload: BusinessUpdate) -> BusinessOut:
    """Route guarantees BUSINESS_EDIT (owner/admin). business_type is owner-only."""
    changes = payload.model_dump(exclude_unset=True, mode="json")  # enums -> plain strings
    if "business_type" in changes and not has_permission(ctx.role, Permission.BUSINESS_EDIT_SETTINGS):
        raise ForbiddenError("Only an owner can change the business type.")
    if ctx.business.get("status") == BusinessStatus.archived.value:
        raise ConflictError("Archived businesses cannot be modified.", code="business_archived")

    changes["updated_at"] = _now()
    db.collection(BUSINESSES).document(ctx.business_id).update(changes)
    return _out(ctx.business_id, {**ctx.business, **changes}, ctx.role.value)


def archive_business(db: Client, ctx: BusinessContext) -> BusinessOut:
    """Soft delete: sets status=archived. No data is removed. Route guarantees
    BUSINESS_ARCHIVE (owner only). Idempotent."""
    if ctx.business.get("status") == BusinessStatus.archived.value:
        return _out(ctx.business_id, ctx.business, ctx.role.value)

    changes = {"status": BusinessStatus.archived.value, "updated_at": _now()}
    db.collection(BUSINESSES).document(ctx.business_id).update(changes)
    return _out(ctx.business_id, {**ctx.business, **changes}, ctx.role.value)

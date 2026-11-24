"""Manually entered business knowledge: businesses/{business_id}/knowledge_entries/{entry_id}.

Plain Firestore documents (content is capped at 20k characters, far below the 1 MB document
limit). Authorization is done by the route dependencies before these functions run.
"""
from datetime import datetime, timezone

from google.cloud import firestore
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import NotFoundError, UnprocessableEntityError
from app.schemas.knowledge import KnowledgeCreate, KnowledgeListOut, KnowledgeOut, KnowledgeUpdate
from app.services.guards import require_active_business
from app.services.membership_service import BUSINESS_ID_RE, BusinessContext

BUSINESSES = "businesses"
ENTRIES = "knowledge_entries"
DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE = 25, 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _collection(db: Client, business_id: str):
    return db.collection(BUSINESSES).document(business_id).collection(ENTRIES)


def _load(db: Client, ctx: BusinessContext, entry_id: str):
    if not BUSINESS_ID_RE.match(entry_id):
        raise NotFoundError("Knowledge entry not found.", code="entry_not_found")
    ref = _collection(db, ctx.business_id).document(entry_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("business_id") != ctx.business_id:
        raise NotFoundError("Knowledge entry not found.", code="entry_not_found")
    return ref, snap.to_dict()


def create_entry(db: Client, ctx: BusinessContext, payload: KnowledgeCreate) -> KnowledgeOut:
    require_active_business(ctx)
    ref = _collection(db, ctx.business_id).document()
    now = _now()
    entry = {
        "entry_id": ref.id,
        "business_id": ctx.business_id,
        "title": payload.title,
        "category": payload.category,
        "content": payload.content,
        "created_by": ctx.user.uid,  # from the verified token, never from the client
        "created_at": now,
        "updated_at": now,
    }
    ref.create(entry)
    return KnowledgeOut.model_validate(entry)


def list_entries(db: Client, ctx: BusinessContext, limit: int | None, cursor: str | None,
                 category: str | None) -> KnowledgeListOut:
    limit = min(max(limit or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    collection = _collection(db, ctx.business_id)
    query = collection
    if category and category.strip():
        query = query.where(filter=FieldFilter("category", "==", category.strip().lower()))
    query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
    if cursor:
        anchor = collection.document(cursor).get() if BUSINESS_ID_RE.match(cursor) else None
        if anchor is None or not anchor.exists:
            raise UnprocessableEntityError("Invalid cursor.", code="invalid_cursor")
        query = query.start_after(anchor)
    snaps = list(query.limit(limit + 1).stream())
    page = snaps[:limit]
    return KnowledgeListOut(
        items=[KnowledgeOut.model_validate(s.to_dict()) for s in page],
        next_cursor=page[-1].id if len(snaps) > limit else None,
    )


def update_entry(db: Client, ctx: BusinessContext, entry_id: str, payload: KnowledgeUpdate) -> KnowledgeOut:
    require_active_business(ctx)
    ref, data = _load(db, ctx, entry_id)
    changes = {**payload.model_dump(exclude_unset=True), "updated_at": _now()}
    ref.update(changes)
    return KnowledgeOut.model_validate({**data, **changes})


def delete_entry(db: Client, ctx: BusinessContext, entry_id: str) -> None:
    """Hard delete: entries are small, user-authored notes (documents use soft delete)."""
    require_active_business(ctx)
    ref, _ = _load(db, ctx, entry_id)
    ref.delete()

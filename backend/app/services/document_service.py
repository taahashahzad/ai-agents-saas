"""Knowledge-base documents: upload, list, read, download, delete, retry.

Authorization (membership + role) is done by the route dependencies before any function
here runs. Every Firestore path is built from ctx.business_id, which comes from the verified
membership, so a document ID from another business can never resolve.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from google.cloud import firestore
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import BadGatewayError, ConflictError, NotFoundError, UnprocessableEntityError
from app.core.storage import StorageError, StorageObjectNotFound
from app.schemas.document import DocumentListOut, DocumentOut, DocumentStatus, DocumentType
from app.services import document_processing, file_validation
from app.services.guards import require_active_business
from app.services.membership_service import BUSINESS_ID_RE, BusinessContext

logger = logging.getLogger(__name__)

BUSINESSES = "businesses"
DOCUMENTS = "documents"
DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE = 25, 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _collection(db: Client, business_id: str):
    return db.collection(BUSINESSES).document(business_id).collection(DOCUMENTS)


def _out(data: dict) -> DocumentOut:
    return DocumentOut.model_validate(data)


def _load(db: Client, ctx: BusinessContext, document_id: str):
    """Return (ref, data) for a live document of THIS business, else 404."""
    if not BUSINESS_ID_RE.match(document_id):
        raise NotFoundError("Document not found.", code="document_not_found")
    ref = _collection(db, ctx.business_id).document(document_id)
    snap = ref.get()
    if not snap.exists:
        raise NotFoundError("Document not found.", code="document_not_found")
    data = snap.to_dict()
    if data.get("is_deleted") or data.get("business_id") != ctx.business_id:
        raise NotFoundError("Document not found.", code="document_not_found")
    return ref, data


# ------------------------------------------------------------------ upload

def upload_document(db: Client, storage, ctx: BusinessContext, *, filename: str | None,
                    content_type: str | None, stream: BinaryIO, max_bytes: int) -> DocumentOut:
    require_active_business(ctx)
    name = file_validation.sanitize_filename(filename)                    # 415 on bad name/extension
    mime = file_validation.check_mime_type(name.file_type, content_type)  # 415 on MIME mismatch
    data = file_validation.read_limited(stream, max_bytes)                # 413 if too large
    file_validation.validate_content(name.file_type, data)                # 422 if bytes don't match

    doc_ref = _collection(db, ctx.business_id).document()                 # server-generated ID
    document_id = doc_ref.id
    path = document_processing.original_path(ctx.business_id, document_id, name.file_type)
    now = _now()

    try:
        storage.upload_bytes(path, data, file_validation.CANONICAL_MIME[name.file_type])
    except StorageError:
        raise BadGatewayError()

    record = {
        "document_id": document_id,
        "business_id": ctx.business_id,
        "filename": name.safe,
        "original_filename": name.original,
        "file_type": name.file_type.value,
        "mime_type": mime,
        "file_size": len(data),
        "storage_path": path,
        "uploaded_by": ctx.user.uid,          # from the verified token
        "uploaded_at": now,
        "updated_at": now,
        "status": DocumentStatus.uploaded.value,
        "processing_error": None,
        "extracted_text_path": None,
        "extracted_character_count": None,
        "is_deleted": False,
    }
    try:
        doc_ref.create(record)
    except Exception:
        _best_effort_delete(storage, path)    # don't leave an unreferenced file behind
        raise

    # Phase 3: synchronous. Later this call can be replaced by enqueueing a background task.
    document_processing.process_document(db, storage, ctx.business_id, document_id)
    return _out(doc_ref.get().to_dict())


# ------------------------------------------------------------------ read

def list_documents(db: Client, ctx: BusinessContext, limit: int | None, cursor: str | None) -> DocumentListOut:
    limit = min(max(limit or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    collection = _collection(db, ctx.business_id)
    query = (collection.where(filter=FieldFilter("is_deleted", "==", False))
             .order_by("uploaded_at", direction=firestore.Query.DESCENDING))
    if cursor:
        if not BUSINESS_ID_RE.match(cursor):
            raise UnprocessableEntityError("Invalid cursor.", code="invalid_cursor")
        anchor = collection.document(cursor).get()   # always inside THIS business's collection
        if not anchor.exists:
            raise UnprocessableEntityError("Invalid cursor.", code="invalid_cursor")
        query = query.start_after(anchor)
    snaps = list(query.limit(limit + 1).stream())
    page = snaps[:limit]
    return DocumentListOut(
        items=[_out(s.to_dict()) for s in page],
        next_cursor=page[-1].id if len(snaps) > limit else None,
    )


def get_document(db: Client, ctx: BusinessContext, document_id: str) -> DocumentOut:
    return _out(_load(db, ctx, document_id)[1])


def download_document(db: Client, storage, ctx: BusinessContext, document_id: str) -> tuple[bytes, dict]:
    _, data = _load(db, ctx, document_id)
    path = data.get("storage_path")
    if not document_processing.is_safe_path(path, ctx.business_id, document_id):
        raise NotFoundError("The file is no longer available.", code="file_not_found")
    try:
        return storage.download_bytes(path), data
    except StorageObjectNotFound:
        raise NotFoundError("The file is no longer available.", code="file_not_found")
    except StorageError:
        raise BadGatewayError()


# ------------------------------------------------------------------ delete

def _best_effort_delete(storage, path: str) -> None:
    try:
        storage.delete(path)
    except StorageError:
        pass


def delete_document(db: Client, storage, ctx: BusinessContext, document_id: str) -> None:
    """1) hide the document (is_deleted=true)  2) delete both Storage objects  3) clear the paths.
    Step 1 happens first, so access stops immediately. If step 2 fails the call returns 502 and
    the SAME request can simply be repeated to finish the cleanup."""
    require_active_business(ctx)
    if not BUSINESS_ID_RE.match(document_id):
        raise NotFoundError("Document not found.", code="document_not_found")
    ref = _collection(db, ctx.business_id).document(document_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("business_id") != ctx.business_id:
        raise NotFoundError("Document not found.", code="document_not_found")
    data = snap.to_dict()

    cleanup_pending = bool(data.get("storage_path") or data.get("extracted_text_path"))
    if data.get("is_deleted") and not cleanup_pending:
        raise NotFoundError("Document not found.", code="document_not_found")

    if not data.get("is_deleted"):
        ref.update({"is_deleted": True, "deleted_at": _now(), "deleted_by": ctx.user.uid,
                    "updated_at": _now()})

    try:
        for key in ("storage_path", "extracted_text_path"):
            path = data.get(key)
            if path and document_processing.is_safe_path(path, ctx.business_id, document_id):
                storage.delete(path)
        # Also remove an extracted file a concurrent processing run may have just written.
        storage.delete(document_processing.extracted_path(ctx.business_id, document_id))
    except StorageError:
        raise BadGatewayError("Could not remove the stored files. Please repeat the request.")
    ref.update({"storage_path": None, "extracted_text_path": None})


# ------------------------------------------------------------------ retry

def retry_document(db: Client, storage, ctx: BusinessContext, document_id: str) -> DocumentOut:
    require_active_business(ctx)
    ref, _ = _load(db, ctx, document_id)
    document_processing.process_document(db, storage, ctx.business_id, document_id)
    return _out(ref.get().to_dict())

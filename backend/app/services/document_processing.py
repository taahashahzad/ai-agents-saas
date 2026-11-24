"""Document processing pipeline (Phase 3: synchronous, called from the request).

    download original -> extract + normalize text -> save extracted.txt in Storage
    -> record status / character count / error in Firestore

`process_document` only needs (db, storage, business_id, document_id). It has no HTTP or
request-context dependency, so it can later be called from a Cloud Tasks / Pub/Sub / Celery
worker without changes. The status document is the single source of truth, and the claim
step is a transaction so two workers cannot process the same document at once.
"""
import logging
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import Client

from app.core import transactions
from app.core.errors import ConflictError, NotFoundError
from app.core.storage import StorageError
from app.schemas.document import DocumentStatus, DocumentType
from app.services.text_extraction import ExtractionError, extract_text

logger = logging.getLogger(__name__)

BUSINESSES = "businesses"
DOCUMENTS = "documents"
# A document stuck in "processing" longer than this (server crashed mid-way) may be retried.
STALE_PROCESSING_AFTER = timedelta(minutes=10)


def storage_dir(business_id: str, document_id: str) -> str:
    return f"businesses/{business_id}/knowledge/{document_id}"


def original_path(business_id: str, document_id: str, file_type: DocumentType) -> str:
    return f"{storage_dir(business_id, document_id)}/original.{file_type.value}"


def extracted_path(business_id: str, document_id: str) -> str:
    return f"{storage_dir(business_id, document_id)}/extracted.txt"


def is_safe_path(path: str | None, business_id: str, document_id: str) -> bool:
    """Defense in depth: a stored path must live under THIS document's folder."""
    return bool(path) and path.startswith(storage_dir(business_id, document_id) + "/") and ".." not in path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def process_document(db: Client, storage, business_id: str, document_id: str) -> None:
    """Run the pipeline. Never raises for processing problems: they are recorded on the
    document (status=failed + a user-safe processing_error). Raises ConflictError/NotFoundError
    only if the document cannot be claimed."""
    ref = db.collection(BUSINESSES).document(business_id).collection(DOCUMENTS).document(document_id)

    def claim(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists or snap.to_dict().get("is_deleted"):
            raise NotFoundError("Document not found.", code="document_not_found")
        data = snap.to_dict()
        status, now = data.get("status"), _now()
        if status == DocumentStatus.processed.value:
            raise ConflictError("This document has already been processed.", code="already_processed")
        if status == DocumentStatus.processing.value and now - data["updated_at"] < STALE_PROCESSING_AFTER:
            raise ConflictError("This document is already being processed.", code="already_processing")
        txn.update(ref, {"status": DocumentStatus.processing.value, "processing_error": None,
                         "updated_at": now})
        return data

    data = transactions.run_in_transaction(db, claim)

    result: dict
    out_path = extracted_path(business_id, document_id)
    try:
        if not is_safe_path(data.get("storage_path"), business_id, document_id):
            raise ExtractionError("The stored file reference is invalid.")
        raw = storage.download_bytes(data["storage_path"])
        text = extract_text(DocumentType(data["file_type"]), raw)
        storage.upload_bytes(out_path, text.encode("utf-8"), "text/plain; charset=utf-8")
        result = {"status": DocumentStatus.processed.value, "processing_error": None,
                  "extracted_text_path": out_path, "extracted_character_count": len(text)}
    except ExtractionError as exc:
        result = {"status": DocumentStatus.failed.value, "processing_error": exc.user_message}
    except StorageError:
        result = {"status": DocumentStatus.failed.value,
                  "processing_error": "A temporary storage error occurred. Please retry."}
    except Exception as exc:  # never let one bad file crash the request/worker
        logger.error("Unexpected processing error (%s)", type(exc).__name__)
        result = {"status": DocumentStatus.failed.value,
                  "processing_error": "An unexpected error occurred while processing the document."}

    def finalize(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists or snap.to_dict().get("is_deleted"):
            return False  # deleted while we were working: write nothing
        txn.update(ref, {**result, "updated_at": _now()})
        return True

    kept = transactions.run_in_transaction(db, finalize)
    if not kept and result.get("extracted_text_path"):
        try:
            storage.delete(out_path)  # don't leave an orphan for a deleted document
        except StorageError:
            pass

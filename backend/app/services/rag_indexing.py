"""Synchronize Firestore document and knowledge records with Qdrant."""
import logging
from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.storage import StorageError
from app.schemas.document import DocumentOut, DocumentStatus, IndexingStatus
from app.schemas.knowledge import KnowledgeOut
from app.services import document_processing
from app.services.membership_service import BusinessContext
from app.services.rag_service import RagService, RagServiceError

logger = logging.getLogger(__name__)
BUSINESSES = "businesses"
DOCUMENTS = "documents"
ENTRIES = "knowledge_entries"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_fields(status: str, *, error: str | None = None, chunks: int = 0,
                   indexed_at: datetime | None = None, model: str | None = None) -> dict:
    return {
        "indexing_status": status,
        "indexed_chunk_count": chunks,
        "indexed_at": indexed_at,
        "indexing_error": error,
        "embedding_model": model,
        "indexing_updated_at": _now(),
    }


def index_document(db: Client, storage, ctx: BusinessContext, document_id: str,
                   rag: RagService) -> DocumentOut:
    ref = db.collection(BUSINESSES).document(ctx.business_id).collection(DOCUMENTS).document(document_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("business_id") != ctx.business_id \
            or snap.to_dict().get("is_deleted"):
        raise NotFoundError("Document not found.", code="document_not_found")
    data = snap.to_dict()
    if data.get("status") != DocumentStatus.processed.value:
        raise ConflictError("The document must be processed before it can be indexed.",
                            code="document_not_processed")
    path = data.get("extracted_text_path")
    if not document_processing.is_safe_path(path, ctx.business_id, document_id):
        raise ConflictError("The extracted text is not available for indexing.",
                            code="extracted_text_missing")

    ref.update(_status_fields(IndexingStatus.processing.value))
    try:
        text = storage.download_bytes(path).decode("utf-8")
        count = rag.index_source(
            business_id=ctx.business_id,
            source_id=document_id,
            source_type="document",
            text=text,
            name=data.get("original_filename") or data["filename"],
            document_id=document_id,
        )
    except (StorageError, UnicodeDecodeError, RagServiceError) as exc:
        message = ("Extracted text could not be read for indexing."
                   if isinstance(exc, (StorageError, UnicodeDecodeError))
                   else str(exc))
        ref.update(_status_fields(IndexingStatus.failed.value, error=message))
        logger.warning("Document indexing failed (%s)", type(exc).__name__)
        raise ServiceUnavailableError(message, code="indexing_failed") from exc

    ref.update(_status_fields(
        IndexingStatus.indexed.value,
        chunks=count,
        indexed_at=_now(),
        model=rag.settings.openai_embedding_model,
    ))
    return DocumentOut.model_validate(ref.get().to_dict())


def document_index_status(db: Client, ctx: BusinessContext, document_id: str) -> DocumentOut:
    ref = db.collection(BUSINESSES).document(ctx.business_id).collection(DOCUMENTS).document(document_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("business_id") != ctx.business_id \
            or snap.to_dict().get("is_deleted"):
        raise NotFoundError("Document not found.", code="document_not_found")
    return DocumentOut.model_validate(snap.to_dict())


def delete_document_vectors(rag: RagService | None, business_id: str, document_id: str) -> None:
    if rag is None:
        return
    try:
        rag.delete_source(business_id, "document", document_id)
    except RagServiceError as exc:
        raise ServiceUnavailableError(str(exc), code="vector_cleanup_failed") from exc


def sync_knowledge_entry(db: Client, ctx: BusinessContext, entry_id: str,
                         rag: RagService | None, *, raise_on_failure: bool = False) -> KnowledgeOut:
    ref = db.collection(BUSINESSES).document(ctx.business_id).collection(ENTRIES).document(entry_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("business_id") != ctx.business_id:
        raise NotFoundError("Knowledge entry not found.", code="entry_not_found")
    data = snap.to_dict()
    if rag is None:
        return KnowledgeOut.model_validate(data)

    ref.update(_status_fields("processing"))
    try:
        count = rag.index_source(
            business_id=ctx.business_id,
            source_id=entry_id,
            source_type="knowledge",
            text=f"{data['title']}\nCategory: {data['category']}\n{data['content']}",
            name=data["title"],
            knowledge_entry_id=entry_id,
        )
    except RagServiceError as exc:
        ref.update(_status_fields("failed", error=str(exc)))
        logger.warning("Knowledge entry indexing failed (%s)", type(exc).__name__)
        if raise_on_failure:
            raise ServiceUnavailableError(str(exc), code="indexing_failed") from exc
        return KnowledgeOut.model_validate(ref.get().to_dict())

    ref.update(_status_fields(
        "indexed",
        chunks=count,
        indexed_at=_now(),
        model=rag.settings.openai_embedding_model,
    ))
    return KnowledgeOut.model_validate(ref.get().to_dict())


def delete_knowledge_vectors(rag: RagService | None, business_id: str, entry_id: str) -> None:
    if rag is None:
        return
    try:
        rag.delete_source(business_id, "knowledge", entry_id)
    except RagServiceError as exc:
        raise ServiceUnavailableError(str(exc), code="vector_cleanup_failed") from exc

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from google.cloud.firestore import Client

from app.core.config import Settings
from app.core.permissions import Permission
from app.core.storage import R2Storage
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.dependencies.settings import get_app_settings
from app.dependencies.storage import get_storage
from app.schemas.document import DocumentListOut, DocumentOut, DocumentType
from app.services import document_service
from app.services.file_validation import CANONICAL_MIME
from app.services.membership_service import BusinessContext

router = APIRouter(prefix="/businesses/{business_id}/documents", tags=["documents"])

_VIEW = require_permission(Permission.DOCUMENTS_VIEW)      # owner, admin, member
_MANAGE = require_permission(Permission.DOCUMENTS_MANAGE)  # owner, admin


@router.get("", response_model=DocumentListOut)
def list_documents(limit: int | None = Query(None, ge=1, le=100), cursor: str | None = Query(None),
                   ctx: BusinessContext = Depends(_VIEW), db: Client = Depends(get_db)):
    return document_service.list_documents(db, ctx, limit, cursor)


@router.post("", response_model=DocumentOut, status_code=201)
def upload_document(file: UploadFile = File(...), ctx: BusinessContext = Depends(_MANAGE),
                    db: Client = Depends(get_db), storage: R2Storage = Depends(get_storage),
                    settings: Settings = Depends(get_app_settings)):
    """multipart/form-data with ONE field named `file`. Processing runs synchronously, so the
    response already shows the final status (`processed` or `failed`)."""
    return document_service.upload_document(
        db, storage, ctx, filename=file.filename, content_type=file.content_type,
        stream=file.file, max_bytes=settings.max_upload_bytes)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, ctx: BusinessContext = Depends(_VIEW), db: Client = Depends(get_db)):
    return document_service.get_document(db, ctx, document_id)


@router.get("/{document_id}/download")
def download_document(document_id: str, ctx: BusinessContext = Depends(_VIEW),
                      db: Client = Depends(get_db), storage: R2Storage = Depends(get_storage)):
    """Streams the original file through the backend (the bucket stays private). Requires the
    Authorization header, so fetch it as a blob; a plain <a href> cannot send the token."""
    content, doc = document_service.download_document(db, storage, ctx, document_id)
    filename = doc["filename"]
    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    return Response(
        content=content,
        media_type=CANONICAL_MIME[DocumentType(doc["file_type"])],
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{document_id}", status_code=204, response_class=Response)
def delete_document(document_id: str, ctx: BusinessContext = Depends(_MANAGE),
                    db: Client = Depends(get_db), storage: R2Storage = Depends(get_storage)):
    document_service.delete_document(db, storage, ctx, document_id)
    return Response(status_code=204)


@router.post("/{document_id}/retry", response_model=DocumentOut)
def retry_document(document_id: str, ctx: BusinessContext = Depends(_MANAGE),
                   db: Client = Depends(get_db), storage: R2Storage = Depends(get_storage)):
    """Re-run processing for a `failed` (or `uploaded`/stuck) document. 409 if already processed."""
    return document_service.retry_document(db, storage, ctx, document_id)

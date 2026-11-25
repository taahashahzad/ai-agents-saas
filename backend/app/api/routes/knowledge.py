from fastapi import APIRouter, Depends, Query, Response
from google.cloud.firestore import Client

from app.core.permissions import Permission
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.dependencies.rag import get_optional_rag_service, get_rag_service
from app.schemas.knowledge import KnowledgeCreate, KnowledgeListOut, KnowledgeOut, KnowledgeUpdate
from app.services import knowledge_service
from app.services.membership_service import BusinessContext
from app.services.rag_indexing import delete_knowledge_vectors, sync_knowledge_entry
from app.services.rag_service import RagService

router = APIRouter(prefix="/businesses/{business_id}/knowledge", tags=["knowledge"])

_VIEW = require_permission(Permission.KNOWLEDGE_VIEW)      # owner, admin, member
_MANAGE = require_permission(Permission.KNOWLEDGE_MANAGE)  # owner, admin


@router.get("", response_model=KnowledgeListOut)
def list_entries(limit: int | None = Query(None, ge=1, le=100), cursor: str | None = Query(None),
                 category: str | None = Query(None, max_length=60),
                 ctx: BusinessContext = Depends(_VIEW), db: Client = Depends(get_db)):
    return knowledge_service.list_entries(db, ctx, limit, cursor, category)


@router.post("", response_model=KnowledgeOut, status_code=201)
def create_entry(payload: KnowledgeCreate, ctx: BusinessContext = Depends(_MANAGE),
                 db: Client = Depends(get_db),
                 rag: RagService | None = Depends(get_optional_rag_service)):
    entry = knowledge_service.create_entry(db, ctx, payload)
    return sync_knowledge_entry(db, ctx, entry.entry_id, rag)


@router.patch("/{entry_id}", response_model=KnowledgeOut)
def update_entry(entry_id: str, payload: KnowledgeUpdate, ctx: BusinessContext = Depends(_MANAGE),
                 db: Client = Depends(get_db),
                 rag: RagService | None = Depends(get_optional_rag_service)):
    updated = knowledge_service.update_entry(db, ctx, entry_id, payload)
    return sync_knowledge_entry(db, ctx, updated.entry_id, rag)


@router.post("/{entry_id}/index", response_model=KnowledgeOut)
def index_entry(entry_id: str, ctx: BusinessContext = Depends(_MANAGE),
                db: Client = Depends(get_db), rag: RagService = Depends(get_rag_service)):
    return sync_knowledge_entry(db, ctx, entry_id, rag, raise_on_failure=True)


@router.delete("/{entry_id}", status_code=204, response_class=Response)
def delete_entry(entry_id: str, ctx: BusinessContext = Depends(_MANAGE), db: Client = Depends(get_db),
                 rag: RagService | None = Depends(get_optional_rag_service)):
    delete_knowledge_vectors(rag, ctx.business_id, entry_id)
    knowledge_service.delete_entry(db, ctx, entry_id)
    return Response(status_code=204)

from fastapi import APIRouter, Depends

from app.core.errors import ServiceUnavailableError
from app.core.permissions import Permission
from app.dependencies.business import require_permission
from app.dependencies.rag import get_rag_service
from app.schemas.rag import RagQueryIn, RagQueryOut
from app.services.membership_service import BusinessContext
from app.services.rag_service import RagService, RagServiceError

router = APIRouter(prefix="/businesses/{business_id}/rag", tags=["rag"])
_QUERY = require_permission(Permission.KNOWLEDGE_VIEW)


@router.post("/query", response_model=RagQueryOut)
def query_business_knowledge(
    payload: RagQueryIn,
    ctx: BusinessContext = Depends(_QUERY),
    rag: RagService = Depends(get_rag_service),
):
    try:
        return rag.query(ctx.business_id, payload.question, payload.top_k)
    except RagServiceError as exc:
        raise ServiceUnavailableError(str(exc), code="rag_unavailable") from exc

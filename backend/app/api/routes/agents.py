from fastapi import APIRouter, Depends, Response
from google.cloud.firestore import Client

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.core.permissions import Permission
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.dependencies.rag import get_rag_service
from app.dependencies.settings import get_app_settings
from app.schemas.agent import AgentCreate, AgentOut, AgentStatusUpdate, AgentUpdate
from app.schemas.conversation import AgentChatIn, AgentChatOut
from app.services import agent_service, agent_runtime
from app.services.membership_service import BusinessContext
from app.services.rag_service import RagService, RagServiceError

router = APIRouter(prefix="/businesses/{business_id}/agents", tags=["agents"])
_MANAGE = require_permission(Permission.AGENTS_MANAGE)


@router.post("", response_model=AgentOut, status_code=201)
def create_agent(
    payload: AgentCreate,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    return agent_service.create_agent(db, ctx, settings, payload)


@router.get("", response_model=list[AgentOut])
def list_agents(ctx: BusinessContext = Depends(_MANAGE), db: Client = Depends(get_db)):
    return agent_service.list_agents(db, ctx)


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, ctx: BusinessContext = Depends(_MANAGE), db: Client = Depends(get_db)):
    return agent_service.get_agent(db, ctx, agent_id)


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    return agent_service.update_agent(db, ctx, settings, agent_id, payload)


@router.patch("/{agent_id}/status", response_model=AgentOut)
def update_agent_status(
    agent_id: str,
    payload: AgentStatusUpdate,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
):
    return agent_service.set_agent_status(db, ctx, agent_id, payload.status)


@router.delete("/{agent_id}", status_code=204, response_class=Response)
def delete_agent(agent_id: str, ctx: BusinessContext = Depends(_MANAGE), db: Client = Depends(get_db)):
    agent_service.delete_agent(db, ctx, agent_id)
    return Response(status_code=204)


@router.post("/{agent_id}/chat", response_model=AgentChatOut)
def chat_with_agent(
    agent_id: str,
    payload: AgentChatIn,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
    rag: RagService = Depends(get_rag_service),
):
    try:
        return agent_runtime.chat_agent(db, ctx, agent_id, payload, rag)
    except RagServiceError as exc:
        raise ServiceUnavailableError(str(exc), code="agent_runtime_unavailable") from exc

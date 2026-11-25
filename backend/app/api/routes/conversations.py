from fastapi import APIRouter, Depends, Response
from google.cloud.firestore import Client

from app.core.permissions import Permission
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.schemas.conversation import ConversationDetailOut, ConversationOut
from app.services import agent_service, conversation_service
from app.services.membership_service import BusinessContext

router = APIRouter(prefix="/businesses/{business_id}", tags=["conversations"])
_MANAGE = require_permission(Permission.AGENTS_MANAGE)


@router.get("/agents/{agent_id}/conversations", response_model=list[ConversationOut])
def list_agent_conversations(
    agent_id: str,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
):
    agent_service.get_agent(db, ctx, agent_id)
    return conversation_service.list_conversations(db, ctx, agent_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
):
    return conversation_service.get_conversation(db, ctx, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204, response_class=Response)
def delete_conversation(
    conversation_id: str,
    ctx: BusinessContext = Depends(_MANAGE),
    db: Client = Depends(get_db),
):
    conversation_service.delete_conversation(db, ctx, conversation_id)
    return Response(status_code=204)

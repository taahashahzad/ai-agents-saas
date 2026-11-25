"""Runs an authorized agent chat and persists successful turns."""
from app.core.errors import ConflictError
from app.schemas.agent import AgentStatus
from app.schemas.conversation import AgentChatIn, AgentChatOut
from app.services import agent_service, conversation_service
from app.services.agent_orchestrator import run_agent
from app.services.membership_service import BusinessContext
from app.services.rag_service import RagService


def chat_agent(
    db,
    ctx: BusinessContext,
    agent_id: str,
    payload: AgentChatIn,
    rag: RagService,
) -> AgentChatOut:
    agent = agent_service.get_agent(db, ctx, agent_id)
    if agent.status != AgentStatus.active:
        raise ConflictError("This agent is inactive.", code="agent_inactive")

    history = (
        conversation_service.runtime_history(db, ctx, payload.conversation_id, agent_id)
        if payload.conversation_id
        else []
    )
    response = run_agent(
        db,
        ctx,
        agent_id,
        payload.message,
        history,
        rag,
    )
    return conversation_service.persist_chat(
        db,
        ctx,
        agent_id,
        payload.message,
        response.answer,
        response.sources,
        payload.conversation_id,
    )

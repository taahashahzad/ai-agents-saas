"""Business-scoped AI agent configuration stored in Firestore."""
from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.core.errors import NotFoundError, UnprocessableEntityError
from app.core.config import Settings
from app.schemas.agent import AgentCreate, AgentOut, AgentStatus, AgentUpdate
from app.services.guards import require_active_business
from app.services.membership_service import BUSINESS_ID_RE, BusinessContext

BUSINESSES = "businesses"
AGENTS = "agents"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _collection(db: Client, business_id: str):
    return db.collection(BUSINESSES).document(business_id).collection(AGENTS)


def _validate_model(model: str, settings: Settings) -> str:
    if model == "default":
        return settings.openai_chat_model
    if model != settings.openai_chat_model:
        raise UnprocessableEntityError(
            "The requested model is not enabled by the backend.",
            code="unsupported_agent_model",
        )
    return model


def load_agent(db: Client, ctx: BusinessContext, agent_id: str):
    if not BUSINESS_ID_RE.fullmatch(agent_id):
        raise NotFoundError("Agent not found.", code="agent_not_found")
    ref = _collection(db, ctx.business_id).document(agent_id)
    snap = ref.get()
    data = snap.to_dict() if snap.exists else None
    if not data or data.get("business_id") != ctx.business_id:
        raise NotFoundError("Agent not found.", code="agent_not_found")
    return ref, data


def get_agent(db: Client, ctx: BusinessContext, agent_id: str) -> AgentOut:
    _, data = load_agent(db, ctx, agent_id)
    return AgentOut.model_validate(data)


def list_agents(db: Client, ctx: BusinessContext) -> list[AgentOut]:
    agents = []
    for snap in _collection(db, ctx.business_id).stream():
        data = snap.to_dict() or {}
        if data.get("business_id") == ctx.business_id:
            agents.append(AgentOut.model_validate(data))
    agents.sort(key=lambda agent: agent.created_at, reverse=True)
    return agents


def create_agent(db: Client, ctx: BusinessContext, settings: Settings, payload: AgentCreate) -> AgentOut:
    require_active_business(ctx)
    now = _now()
    ref = _collection(db, ctx.business_id).document()
    agent = {
        **payload.model_dump(exclude={"model"}),
        "model": _validate_model(payload.model, settings),
        "agent_id": ref.id,
        "business_id": ctx.business_id,
        "status": AgentStatus.active.value,
        "created_by": ctx.user.uid,
        "created_at": now,
        "updated_at": now,
    }
    ref.create(agent)
    return AgentOut.model_validate(agent)


def update_agent(db: Client, ctx: BusinessContext, settings: Settings,
                 agent_id: str, payload: AgentUpdate) -> AgentOut:
    require_active_business(ctx)
    ref, data = load_agent(db, ctx, agent_id)
    changes = payload.model_dump(exclude_unset=True)
    if "model" in changes:
        changes["model"] = _validate_model(changes["model"], settings)
    changes["updated_at"] = _now()
    ref.update(changes)
    return AgentOut.model_validate({**data, **changes})


def set_agent_status(db: Client, ctx: BusinessContext,
                     agent_id: str, status: AgentStatus) -> AgentOut:
    require_active_business(ctx)
    ref, data = load_agent(db, ctx, agent_id)
    changes = {"status": status.value, "updated_at": _now()}
    ref.update(changes)
    return AgentOut.model_validate({**data, **changes})


def delete_agent(db: Client, ctx: BusinessContext, agent_id: str) -> None:
    require_active_business(ctx)
    ref, _ = load_agent(db, ctx, agent_id)
    from app.services.conversation_service import delete_agent_conversations

    delete_agent_conversations(db, ctx.business_id, agent_id)
    ref.delete()

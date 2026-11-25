"""Business- and agent-scoped conversation persistence."""
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import Client, Query

from app.core.errors import NotFoundError
from app.services.guards import require_active_business
from app.schemas.conversation import (
    AgentChatOut,
    ConversationDetailOut,
    ConversationMessageOut,
    ConversationOut,
    MessageRole,
)
from app.services.membership_service import BUSINESS_ID_RE, BusinessContext

BUSINESSES = "businesses"
CONVERSATIONS = "conversations"
MESSAGES = "messages"
MAX_HISTORY_MESSAGES = 100
RUNTIME_HISTORY_MESSAGES = 8
DELETE_BATCH_SIZE = 450


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _collection(db: Client, business_id: str):
    return db.collection(BUSINESSES).document(business_id).collection(CONVERSATIONS)


def load_conversation(db: Client, ctx: BusinessContext, conversation_id: str,
                      agent_id: str | None = None):
    if not BUSINESS_ID_RE.fullmatch(conversation_id):
        raise NotFoundError("Conversation not found.", code="conversation_not_found")
    ref = _collection(db, ctx.business_id).document(conversation_id)
    snap = ref.get()
    data = snap.to_dict() if snap.exists else None
    if (
        not data
        or data.get("business_id") != ctx.business_id
        or (agent_id is not None and data.get("agent_id") != agent_id)
    ):
        raise NotFoundError("Conversation not found.", code="conversation_not_found")
    return ref, data


def _message_docs(ref):
    snapshots = (
        ref.collection(MESSAGES)
        .order_by("created_at", direction=Query.DESCENDING)
        .limit(MAX_HISTORY_MESSAGES)
        .stream()
    )
    messages = [snap.to_dict() or {} for snap in snapshots]
    messages.reverse()
    return messages


def _conversation_out(data: dict) -> ConversationOut:
    return ConversationOut.model_validate(data)


def _message_out(data: dict) -> ConversationMessageOut:
    return ConversationMessageOut.model_validate(data)


def list_conversations(db: Client, ctx: BusinessContext, agent_id: str) -> list[ConversationOut]:
    conversations = []
    for snap in _collection(db, ctx.business_id).stream():
        data = snap.to_dict() or {}
        if data.get("business_id") == ctx.business_id and data.get("agent_id") == agent_id:
            conversations.append(_conversation_out(data))
    conversations.sort(key=lambda conversation: conversation.updated_at, reverse=True)
    return conversations[:100]


def get_conversation(db: Client, ctx: BusinessContext, conversation_id: str) -> ConversationDetailOut:
    from app.services.agent_service import load_agent

    ref, data = load_conversation(db, ctx, conversation_id)
    load_agent(db, ctx, data["agent_id"])
    return ConversationDetailOut(
        conversation=_conversation_out(data),
        messages=[_message_out(message) for message in _message_docs(ref)],
    )


def runtime_history(db: Client, ctx: BusinessContext, conversation_id: str, agent_id: str) -> list[dict]:
    ref, _ = load_conversation(db, ctx, conversation_id, agent_id)
    messages = _message_docs(ref)[-RUNTIME_HISTORY_MESSAGES:]
    return [{"role": message["role"], "content": message["content"]} for message in messages]


def persist_chat(
    db: Client,
    ctx: BusinessContext,
    agent_id: str,
    message: str,
    answer: str,
    sources: list,
    conversation_id: str | None,
) -> AgentChatOut:
    now = _now()
    assistant_created_at = now + timedelta(microseconds=1)
    is_new = conversation_id is None
    ref = (
        _collection(db, ctx.business_id).document()
        if is_new
        else _collection(db, ctx.business_id).document(conversation_id)
    )
    if not is_new:
        _, current = load_conversation(db, ctx, conversation_id, agent_id)
        if current.get("status") != "active":
            raise NotFoundError("Conversation not found.", code="conversation_not_found")
        created_at = current["created_at"]
    else:
        created_at = now

    conversation = {
        "conversation_id": ref.id,
        "business_id": ctx.business_id,
        "agent_id": agent_id,
        "status": "active",
        "created_at": created_at,
        "updated_at": assistant_created_at,
        "last_message_preview": answer[:160],
    }
    user_ref = ref.collection(MESSAGES).document()
    assistant_ref = ref.collection(MESSAGES).document()
    user_message = {
        "message_id": user_ref.id,
        "conversation_id": ref.id,
        "role": MessageRole.user.value,
        "content": message,
        "sources": [],
        "created_at": now,
    }
    assistant_message = {
        "message_id": assistant_ref.id,
        "conversation_id": ref.id,
        "role": MessageRole.assistant.value,
        "content": answer,
        "sources": [source.model_dump(mode="json") for source in sources],
        "created_at": assistant_created_at,
    }

    batch = db.batch()
    batch.set(ref, conversation)
    batch.set(user_ref, user_message)
    batch.set(assistant_ref, assistant_message)
    batch.commit()
    return AgentChatOut(
        conversation_id=ref.id,
        user_message=_message_out(user_message),
        assistant_message=_message_out(assistant_message),
    )


def _delete_references(db: Client, refs) -> None:
    batch = db.batch()
    count = 0
    for ref in refs:
        batch.delete(ref)
        count += 1
        if count == DELETE_BATCH_SIZE:
            batch.commit()
            batch = db.batch()
            count = 0
    if count:
        batch.commit()


def _delete_conversation_tree(db: Client, conversation_ref) -> None:
    def references():
        for snap in conversation_ref.collection(MESSAGES).stream():
            yield snap.reference
        yield conversation_ref

    _delete_references(db, references())


def delete_conversation(db: Client, ctx: BusinessContext, conversation_id: str) -> None:
    from app.services.agent_service import load_agent

    require_active_business(ctx)
    ref, data = load_conversation(db, ctx, conversation_id)
    load_agent(db, ctx, data["agent_id"])
    _delete_conversation_tree(db, ref)


def delete_agent_conversations(db: Client, business_id: str, agent_id: str) -> None:
    def references():
        for snap in _collection(db, business_id).stream():
            data = snap.to_dict() or {}
            if data.get("business_id") != business_id or data.get("agent_id") != agent_id:
                continue
            for message in snap.reference.collection(MESSAGES).stream():
                yield message.reference
            yield snap.reference

    _delete_references(db, references())

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.rag import RagSource

ChatMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class AgentChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ChatMessage
    conversation_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] | None = None


class ConversationMessageOut(BaseModel):
    message_id: str
    conversation_id: str
    role: MessageRole
    content: str
    sources: list[RagSource] = Field(default_factory=list)
    created_at: datetime


class ConversationOut(BaseModel):
    conversation_id: str
    business_id: str
    agent_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: str = ""


class ConversationDetailOut(BaseModel):
    conversation: ConversationOut
    messages: list[ConversationMessageOut]


class AgentChatOut(BaseModel):
    conversation_id: str
    user_message: ConversationMessageOut
    assistant_message: ConversationMessageOut

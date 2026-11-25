from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

AgentName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
AgentDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
AgentInstructions = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]
AgentPersonality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
AgentLanguage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
AgentGreeting = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class AgentStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: AgentName
    description: AgentDescription = ""
    agent_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    instructions: AgentInstructions
    personality: AgentPersonality = "Helpful"
    greeting: AgentGreeting = "Hello! How can I help you?"
    language: AgentLanguage = "English"
    model: str = "default"
    temperature: float = Field(default=0.2, ge=0, le=1)
    response_length: Literal["short", "standard", "long"] = "standard"


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: AgentName | None = None
    description: AgentDescription | None = None
    agent_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None = None
    instructions: AgentInstructions | None = None
    personality: AgentPersonality | None = None
    greeting: AgentGreeting | None = None
    language: AgentLanguage | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=1)
    response_length: Literal["short", "standard", "long"] | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provided agent fields must not be null.")
        return self


class AgentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AgentStatus


class AgentOut(BaseModel):
    agent_id: str
    business_id: str
    name: str
    description: str
    agent_type: str
    instructions: str
    personality: str
    greeting: str
    language: str
    model: str
    temperature: float
    response_length: Literal["short", "standard", "long"]
    status: AgentStatus
    created_by: str
    created_at: datetime
    updated_at: datetime

"""A small registry of explicitly approved, read-only business agent tools."""
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from app.core.errors import ForbiddenError
from app.core.permissions import Permission, has_permission
from app.services.membership_service import BusinessContext
from app.services.rag_service import RagService, RagSource


class SearchKnowledgeInput(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


@dataclass(frozen=True)
class RegisteredAgentTool:
    name: str
    description: str
    input_schema: type[BaseModel]
    required_permission: Permission
    execute: Callable[[BaseModel], list[RagSource]]

    def invoke(self, ctx: BusinessContext, values: dict) -> list[RagSource]:
        if not has_permission(ctx.role, self.required_permission):
            raise ForbiddenError("This agent tool is not permitted for this business user.")
        payload = self.input_schema.model_validate(values)
        return self.execute(payload)


def build_agent_tool_registry(ctx: BusinessContext, rag: RagService) -> dict[str, RegisteredAgentTool]:
    search = RegisteredAgentTool(
        name="search_business_knowledge",
        description="Search only the verified business's indexed knowledge for relevant excerpts.",
        input_schema=SearchKnowledgeInput,
        required_permission=Permission.KNOWLEDGE_VIEW,
        execute=lambda payload: rag.retrieve_sources(
            ctx.business_id,
            payload.question,
            payload.top_k,
        ),
    )
    return {search.name: search}

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=4000)]


class RagQueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagSource(BaseModel):
    source_type: str
    business_id: str
    chunk_id: str
    chunk_index: int
    excerpt: str
    score: float
    document_id: str | None = None
    knowledge_entry_id: str | None = None
    document_name: str | None = None
    title: str | None = None
    page_number: int | None = None


class RagQueryOut(BaseModel):
    answer: str
    sufficient_context: bool
    sources: list[RagSource]

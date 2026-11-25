from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Categories are free-form labels ("menu", "faq", "policies"...). Lowercased so filtering is stable.
Category = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=60)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class KnowledgeIndexingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class KnowledgeCreate(BaseModel):
    # extra="forbid": created_by, business_id, entry_id etc. from a client are rejected (422).
    model_config = ConfigDict(extra="forbid")
    title: Title
    category: Category
    content: Content


class KnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    category: Category | None = None
    content: Content | None = None

    @model_validator(mode="after")
    def _at_least_one_non_null_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' must not be null.")
        return self


class KnowledgeOut(BaseModel):
    entry_id: str
    business_id: str
    title: str
    category: str
    content: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    indexing_status: KnowledgeIndexingStatus = KnowledgeIndexingStatus.pending
    indexed_chunk_count: int = 0
    indexed_at: datetime | None = None
    indexing_error: str | None = None
    embedding_model: str | None = None


class KnowledgeListOut(BaseModel):
    items: list[KnowledgeOut]
    next_cursor: str | None = None

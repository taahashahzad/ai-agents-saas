from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    txt = "txt"
    csv = "csv"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class IndexingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class DocumentOut(BaseModel):
    """Public view of a document. Storage paths are deliberately NOT included."""
    document_id: str
    business_id: str
    filename: str
    original_filename: str
    file_type: DocumentType
    mime_type: str
    file_size: int
    status: DocumentStatus
    processing_error: str | None = None
    extracted_character_count: int | None = None
    indexing_status: IndexingStatus = IndexingStatus.pending
    indexed_chunk_count: int = 0
    indexed_at: datetime | None = None
    indexing_error: str | None = None
    embedding_model: str | None = None
    uploaded_by: str
    uploaded_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None = None

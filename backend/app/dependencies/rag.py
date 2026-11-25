from fastapi import Depends
from openai import OpenAI
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.dependencies.settings import get_app_settings
from app.services.rag_service import RagService


def _create_service(settings: Settings) -> RagService:
    if not settings.rag_configured:
        raise ServiceUnavailableError(
            "RAG is not configured. Set OPENAI_API_KEY and QDRANT_URL on the backend.",
            code="rag_not_configured",
        )
    try:
        return RagService(
            settings,
            OpenAI(api_key=settings.openai_api_key),
            QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key),
        )
    except Exception as exc:
        raise ServiceUnavailableError("RAG providers could not be initialized.",
                                      code="rag_unavailable") from exc


def get_rag_service(settings: Settings = Depends(get_app_settings)) -> RagService:
    return _create_service(settings)


def get_optional_rag_service(settings: Settings = Depends(get_app_settings)) -> RagService | None:
    if not settings.rag_configured:
        return None
    return _create_service(settings)

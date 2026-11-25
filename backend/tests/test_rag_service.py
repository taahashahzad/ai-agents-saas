import json
import logging
from types import SimpleNamespace

from qdrant_client import models

from app.core.config import Settings
from app.services.rag_service import RagService


class FakeOpenAI:
    def __init__(self):
        self.embedding_batch_sizes = []
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "answer": "The restaurant opens at nine.",
                    "sufficient_context": True,
                })))]
            ))
        )

    def _embed(self, *, input, **_):
        self.embedding_batch_sizes.append(len(input))
        return SimpleNamespace(data=[
            SimpleNamespace(index=index, embedding=[float(index + 1)] * 1536)
            for index in range(len(input))
        ])


class FakeQdrant:
    def __init__(self):
        self.points = {}

    def collection_exists(self, _):
        return True

    def create_payload_index(self, **_):
        return None

    @staticmethod
    def _matches(point, query_filter):
        return all(
            point.payload.get(condition.key) == condition.match.value
            for condition in query_filter.must
        )

    def scroll(self, *, scroll_filter, offset=None, limit, **_):
        matches = [
            point for point in self.points.values()
            if self._matches(point, scroll_filter)
        ]
        start = offset or 0
        page = matches[start:start + limit]
        next_offset = start + len(page) if start + len(page) < len(matches) else None
        return page, next_offset

    def upsert(self, *, points, **_):
        self.points.update({str(point.id): point for point in points})

    def delete(self, *, points_selector, **_):
        if isinstance(points_selector, models.PointIdsList):
            for point_id in points_selector.points:
                self.points.pop(str(point_id), None)
            return
        for point_id, point in list(self.points.items()):
            if self._matches(point, points_selector.filter):
                del self.points[point_id]

    def query_points(self, *, query_filter, limit, **_):
        matches = [
            SimpleNamespace(id=point.id, payload=point.payload, score=0.9)
            for point in self.points.values()
            if self._matches(point, query_filter)
        ][:limit]
        return SimpleNamespace(points=matches)


def make_service():
    settings = Settings(
        app_env="test",
        cors_origins=[],
        firebase_credentials_path=None,
        firebase_project_id=None,
        check_token_revoked=False,
        log_level="WARNING",
        rag_chunk_size=32,
        rag_chunk_overlap=8,
    )
    qdrant = FakeQdrant()
    return RagService(settings, FakeOpenAI(), qdrant), qdrant


def test_index_is_repeatable_and_replaces_stale_chunks():
    service, qdrant = make_service()
    common = {
        "business_id": "business-a",
        "source_id": "document-a",
        "source_type": "document",
        "name": "menu.txt",
        "document_id": "document-a",
    }

    first_count = service.index_source(text="A" * 100, **common)
    first_ids = set(qdrant.points)
    assert first_count > 1
    assert len(first_ids) == first_count

    assert service.index_source(text="A" * 100, **common) == first_count
    assert set(qdrant.points) == first_ids

    service.index_source(text="A" * 40, **common)
    assert len(qdrant.points) < first_count


def test_query_filters_at_vector_search_and_returns_only_requested_business_sources():
    service, qdrant = make_service()
    service.index_source(
        business_id="business-a",
        source_id="entry-a",
        source_type="knowledge",
        text="Opening hours: 9 AM.",
        name="Hours",
        knowledge_entry_id="entry-a",
    )
    service.index_source(
        business_id="business-b",
        source_id="entry-b",
        source_type="knowledge",
        text="Opening hours: 11 AM.",
        name="Hours",
        knowledge_entry_id="entry-b",
    )

    result = service.query("business-a", "When does it open?")

    assert result.sufficient_context is True
    assert len(result.sources) == 1
    assert result.sources[0].business_id == "business-a"
    assert "9 AM" in result.sources[0].excerpt


def test_query_with_no_matches_returns_grounded_fallback_without_calling_chat():
    service, _ = make_service()

    result = service.query("empty-business", "What are the opening hours?")

    assert result.sufficient_context is False
    assert result.sources == []
    assert "enough information" in result.answer


def test_large_source_is_embedded_in_bounded_batches():
    service, _ = make_service()

    count = service.index_source(
        business_id="business-a",
        source_id="large-source",
        source_type="knowledge",
        text="restaurant details " * 400,
        name="Large source",
        knowledge_entry_id="large-source",
    )

    assert count > 128
    assert max(service.openai.embedding_batch_sizes) <= 128
    assert sum(service.openai.embedding_batch_sizes) == count


def test_embedding_failure_logs_provider_status_and_code_without_error_message(caplog):
    service, _ = make_service()

    class ProviderError(Exception):
        status_code = 401
        code = "invalid_api_key"

        def __str__(self):
            return "sensitive provider response body"

    def fail_embedding(**_):
        raise ProviderError()

    service.openai.embeddings.create = fail_embedding
    with caplog.at_level(logging.ERROR, logger="app.services.rag_service"):
        try:
            service._embed(["test"])
        except Exception as exc:
            assert exc.__class__.__name__ == "RagServiceError"
        else:
            raise AssertionError("Expected an embedding service error.")

    assert "status=401" in caplog.text
    assert "code=invalid_api_key" in caplog.text
    assert "sensitive provider response body" not in caplog.text

"""Run the fictional restaurant RAG evaluation against configured OpenAI and Qdrant services."""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.services.rag_service import RagService


def main() -> None:
    settings = get_settings()
    if not settings.rag_configured:
        raise SystemExit("Set OPENAI_API_KEY and QDRANT_URL before running this evaluation.")

    dataset_path = Path(__file__).resolve().parents[1] / "evaluation" / "restaurant_rag.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    business_id = f"rag-eval-{uuid.uuid4().hex}"
    rag = RagService(
        settings,
        OpenAI(api_key=settings.openai_api_key),
        QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key),
    )
    indexed_ids = []
    retrieved = 0
    answer_hits = 0

    try:
        for source in dataset["sources"]:
            rag.index_source(
                business_id=business_id,
                source_id=source["source_id"],
                source_type="knowledge",
                text=source["content"],
                name=source["title"],
                knowledge_entry_id=source["source_id"],
            )
            indexed_ids.append(source["source_id"])

        for item in dataset["questions"]:
            result = rag.query(business_id, item["question"])
            if any(source.knowledge_entry_id == item["expected_source_id"] for source in result.sources):
                retrieved += 1
            answer = result.answer.casefold()
            if all(term.casefold() in answer for term in item["required_terms"]):
                answer_hits += 1

        total = len(dataset["questions"])
        print(json.dumps({
            "business": dataset["business_name"],
            "questions": total,
            "retrieval_recall_at_k": round(retrieved / total, 3),
            "answer_required_term_hit_rate": round(answer_hits / total, 3),
            "retrieved_expected_source": retrieved,
            "answers_with_all_required_terms": answer_hits,
        }, indent=2))
    finally:
        for source_id in indexed_ids:
            rag.delete_source(business_id, "knowledge", source_id)


if __name__ == "__main__":
    main()

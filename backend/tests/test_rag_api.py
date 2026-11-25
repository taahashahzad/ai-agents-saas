from app.dependencies.rag import get_rag_service
from app.schemas.rag import RagQueryOut


class FakeRag:
    def __init__(self):
        self.business_ids = []

    def query(self, business_id, question, top_k=None):
        self.business_ids.append(business_id)
        return RagQueryOut(
            answer=f"Answer to: {question}",
            sufficient_context=True,
            sources=[],
        )


def test_rag_query_requires_business_membership_and_uses_verified_business_context(
    client, make_business
):
    business = make_business()
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag
    path = f"/api/v1/businesses/{business['id']}/rag/query"

    response = client.post(
        path,
        json={"question": "When are you open?", "top_k": 3},
        headers={"Authorization": "Bearer token-alice"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == "Answer to: When are you open?"
    assert rag.business_ids == [business["id"]]

    denied = client.post(
        path,
        json={"question": "When are you open?"},
        headers={"Authorization": "Bearer token-bob"},
    )
    assert denied.status_code == 404

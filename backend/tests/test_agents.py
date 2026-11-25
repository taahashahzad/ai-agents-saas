from types import SimpleNamespace

from app.dependencies.rag import get_rag_service
from app.schemas.rag import RagQueryOut, RagSource
from tests.conftest import add_member, bearer


class FakeRag:
    def __init__(self):
        self.settings = SimpleNamespace(rag_top_k=5)
        self.generated = []
        self.searched_businesses = []

    def retrieve_sources(self, business_id, question, top_k):
        self.searched_businesses.append(business_id)
        return [
            RagSource(
                source_type="knowledge",
                business_id=business_id,
                chunk_id="knowledge:hours:0",
                chunk_index=0,
                excerpt="Open daily from 9 AM to 5 PM.",
                score=0.9,
                knowledge_entry_id="hours",
                title="Opening hours",
            )
        ]

    def generate_answer(self, question, sources, **kwargs):
        self.generated.append({"question": question, "sources": sources, **kwargs})
        return RagQueryOut(
            answer="We are open daily from 9 AM to 5 PM.",
            sufficient_context=True,
            sources=sources,
        )


def create_agent(client, business_id, user="alice", **overrides):
    payload = {
        "name": "Helpful Assistant",
        "description": "Answers customer questions.",
        "agent_type": "General Business Assistant",
        "instructions": "Answer politely using the business knowledge.",
        "personality": "Friendly",
        "greeting": "Hello there!",
        "language": "English",
        "temperature": 0.3,
        "response_length": "standard",
        **overrides,
    }
    response = client.post(
        f"/api/v1/businesses/{business_id}/agents",
        json=payload,
        headers=bearer(user),
    )
    return response


def test_agent_crud_and_configuration_are_business_scoped(client, make_business):
    business = make_business()
    business_id = business["id"]

    created = create_agent(client, business_id)
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["business_id"] == business_id
    assert agent["model"] == "gpt-4o-mini"
    assert agent["created_by"] == "alice-uid"

    listed = client.get(
        f"/api/v1/businesses/{business_id}/agents",
        headers=bearer("alice"),
    )
    assert listed.status_code == 200
    assert [item["agent_id"] for item in listed.json()] == [agent["agent_id"]]

    fetched = client.get(
        f"/api/v1/businesses/{business_id}/agents/{agent['agent_id']}",
        headers=bearer("alice"),
    )
    assert fetched.status_code == 200
    assert fetched.json()["instructions"] == "Answer politely using the business knowledge."

    updated = client.patch(
        f"/api/v1/businesses/{business_id}/agents/{agent['agent_id']}",
        json={"personality": "Concise", "temperature": 0.7},
        headers=bearer("alice"),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["personality"] == "Concise"
    assert updated.json()["temperature"] == 0.7

    unsupported_model = client.patch(
        f"/api/v1/businesses/{business_id}/agents/{agent['agent_id']}",
        json={"model": "unapproved-model"},
        headers=bearer("alice"),
    )
    assert unsupported_model.status_code == 422


def test_agent_chat_persists_bounded_history_and_sources(client, make_business):
    business = make_business()
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag
    agent = create_agent(client, business["id"]).json()
    url = f"/api/v1/businesses/{business['id']}/agents/{agent['agent_id']}/chat"

    first = client.post(url, json={"message": "What are your hours?"}, headers=bearer("alice"))
    assert first.status_code == 200, first.text
    first_body = first.json()
    conversation_id = first_body["conversation_id"]
    assert first_body["assistant_message"]["sources"][0]["business_id"] == business["id"]
    assert rag.searched_businesses == [business["id"]]

    second = client.post(
        url,
        json={"message": "And on Sundays?", "conversation_id": conversation_id},
        headers=bearer("alice"),
    )
    assert second.status_code == 200, second.text
    assert [message["role"] for message in rag.generated[-1]["history"]] == [
        "user",
        "assistant",
    ]
    assert "Platform safety rules" in rag.generated[-1]["system_prompt"]
    assert "Return only a JSON object" in rag.generated[-1]["system_prompt"]

    conversations = client.get(
        f"/api/v1/businesses/{business['id']}/agents/{agent['agent_id']}/conversations",
        headers=bearer("alice"),
    )
    assert conversations.status_code == 200
    assert conversations.json()[0]["conversation_id"] == conversation_id

    detail = client.get(
        f"/api/v1/businesses/{business['id']}/conversations/{conversation_id}",
        headers=bearer("alice"),
    )
    assert detail.status_code == 200
    assert [item["role"] for item in detail.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_agent_chat_accepts_single_character_messages(client, make_business):
    business = make_business()
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag
    agent = create_agent(client, business["id"]).json()

    response = client.post(
        f"/api/v1/businesses/{business['id']}/agents/{agent['agent_id']}/chat",
        json={"message": "?"},
        headers=bearer("alice"),
    )

    assert response.status_code == 200, response.text


def test_inactive_agent_cannot_chat_and_can_be_reactivated(client, make_business):
    business = make_business()
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag
    agent = create_agent(client, business["id"]).json()
    base = f"/api/v1/businesses/{business['id']}/agents/{agent['agent_id']}"

    inactive = client.patch(
        f"{base}/status",
        json={"status": "inactive"},
        headers=bearer("alice"),
    )
    assert inactive.status_code == 200
    response = client.post(f"{base}/chat", json={"message": "Hello"}, headers=bearer("alice"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "agent_inactive"
    assert rag.generated == []

    reactivated = client.patch(
        f"{base}/status",
        json={"status": "active"},
        headers=bearer("alice"),
    )
    assert reactivated.status_code == 200


def test_agent_and_conversation_cannot_be_accessed_from_another_business(client, make_business):
    business_a = make_business(user="alice")
    business_b = make_business(user="bob", name="Bob's Business")
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag

    agent = create_agent(client, business_a["id"]).json()
    chat = client.post(
        f"/api/v1/businesses/{business_a['id']}/agents/{agent['agent_id']}/chat",
        json={"message": "What are your hours?"},
        headers=bearer("alice"),
    )
    conversation_id = chat.json()["conversation_id"]

    cross_agent = client.get(
        f"/api/v1/businesses/{business_b['id']}/agents/{agent['agent_id']}",
        headers=bearer("bob"),
    )
    cross_conversation = client.get(
        f"/api/v1/businesses/{business_b['id']}/conversations/{conversation_id}",
        headers=bearer("bob"),
    )
    assert cross_agent.status_code == 404
    assert cross_conversation.status_code == 404
    assert rag.searched_businesses == [business_a["id"]]

    second_agent = create_agent(client, business_a["id"]).json()
    mismatched_conversation = client.post(
        f"/api/v1/businesses/{business_a['id']}/agents/{second_agent['agent_id']}/chat",
        json={"message": "Read another conversation.", "conversation_id": conversation_id},
        headers=bearer("alice"),
    )
    assert mismatched_conversation.status_code == 404


def test_member_cannot_manage_agents_and_delete_cascades_conversations(client, make_business, fake_db):
    business = make_business()
    business_id = business["id"]
    add_member(fake_db, business_id, "bob", role="member")
    agent = create_agent(client, business_id).json()
    rag = FakeRag()
    client.app.dependency_overrides[get_rag_service] = lambda: rag

    denied = client.get(
        f"/api/v1/businesses/{business_id}/agents",
        headers=bearer("bob"),
    )
    assert denied.status_code == 403

    chat = client.post(
        f"/api/v1/businesses/{business_id}/agents/{agent['agent_id']}/chat",
        json={"message": "What are your hours?"},
        headers=bearer("alice"),
    )
    conversation_id = chat.json()["conversation_id"]
    removed = client.delete(
        f"/api/v1/businesses/{business_id}/agents/{agent['agent_id']}",
        headers=bearer("alice"),
    )
    assert removed.status_code == 204
    assert f"businesses/{business_id}/conversations/{conversation_id}" not in fake_db.docs
    assert not any(
        path.startswith(f"businesses/{business_id}/conversations/{conversation_id}/messages/")
        for path in fake_db.docs
    )

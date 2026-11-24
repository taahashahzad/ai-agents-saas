from tests.conftest import bearer


def test_profile_missing_before_creation(client):
    r = client.get("/api/v1/users/me", headers=bearer("alice"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "profile_not_found"


def test_create_profile_uses_token_identity(client, fake_db):
    r = client.post("/api/v1/users/me", json={"display_name": "  Alice  "}, headers=bearer("alice"))
    assert r.status_code == 201
    body = r.json()
    assert body["uid"] == "alice-uid"
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    stored = fake_db.docs["users/alice-uid"]
    assert set(stored) == {"uid", "email", "display_name", "created_at", "updated_at"}
    assert body["platform_role"] is None


def test_create_profile_without_body_defaults_to_token_name(client):
    r = client.post("/api/v1/users/me", headers=bearer("alice"))
    assert r.status_code == 201
    assert r.json()["display_name"] == "Alice A"


def test_client_cannot_supply_uid_or_email(client, fake_db):
    r = client.post("/api/v1/users/me", json={"uid": "bob-uid", "email": "x@y.z"}, headers=bearer("alice"))
    assert r.status_code == 422
    assert "users/bob-uid" not in fake_db.docs


def test_get_profile_returns_own_profile_only(client):
    client.post("/api/v1/users/me", json={"display_name": "Alice"}, headers=bearer("alice"))
    assert client.get("/api/v1/users/me", headers=bearer("alice")).json()["uid"] == "alice-uid"
    assert client.get("/api/v1/users/me", headers=bearer("bob")).status_code == 404


def test_second_post_updates_and_keeps_created_at(client):
    first = client.post("/api/v1/users/me", json={"display_name": "Alice"}, headers=bearer("alice")).json()
    r = client.post("/api/v1/users/me", json={"display_name": "Alicia"}, headers=bearer("alice"))
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alicia"
    assert r.json()["created_at"] == first["created_at"]


def test_display_name_validation(client):
    for bad in ["", "   ", "x" * 101]:
        r = client.post("/api/v1/users/me", json={"display_name": bad}, headers=bearer("alice"))
        assert r.status_code == 422


def test_platform_role_comes_from_token_claim_only(client, fake_db):
    client.post("/api/v1/users/me", headers=bearer("root"))
    me = client.get("/api/v1/users/me", headers=bearer("root")).json()
    assert me["platform_role"] == "system_admin"
    assert "platform_role" not in fake_db.docs["users/root-uid"]  # never persisted


def test_unknown_platform_claim_value_grants_nothing(client):
    client.post("/api/v1/users/me", headers=bearer("fake"))
    assert client.get("/api/v1/users/me", headers=bearer("fake")).json()["platform_role"] is None


def test_user_cannot_promote_self_through_profile_endpoint(client, fake_db):
    for body in ({"platform_role": "system_admin"}, {"role": "system_admin"}):
        assert client.post("/api/v1/users/me", json=body, headers=bearer("alice")).status_code == 422
    assert "users/alice-uid" not in fake_db.docs


def test_second_post_refreshes_updated_at(client):
    first = client.post("/api/v1/users/me", headers=bearer("alice")).json()
    second = client.post("/api/v1/users/me", json={"display_name": "New"}, headers=bearer("alice")).json()
    assert second["updated_at"] >= first["updated_at"]

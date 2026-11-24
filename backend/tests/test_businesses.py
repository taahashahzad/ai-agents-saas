from tests.conftest import add_member, bearer


# ---------- creation ----------

def test_create_business_writes_business_and_owner_membership(client, fake_db):
    r = client.post("/api/v1/businesses",
                    json={"name": " Chez Alice ", "business_type": "restaurant", "description": "Bistro"},
                    headers=bearer("alice"))
    assert r.status_code == 201
    body = r.json()
    bid = body["id"]
    assert body["name"] == "Chez Alice"
    assert body["owner_id"] == "alice-uid"
    assert body["status"] == "active"
    assert body["role"] == "owner"

    business = fake_db.docs[f"businesses/{bid}"]
    assert set(business) == {"name", "business_type", "description", "owner_id",
                             "status", "created_at", "updated_at"}
    assert business["owner_id"] == "alice-uid"
    member = fake_db.docs[f"businesses/{bid}/members/alice-uid"]
    assert set(member) == {"uid", "role", "joined_at", "email"}
    assert member["role"] == "owner"
    assert member["email"] == "alice@example.com"


def test_create_rejects_client_supplied_owner_role_status(client, fake_db):
    for extra in ({"owner_id": "bob-uid"}, {"role": "owner"}, {"status": "archived"}, {"id": "mine"}):
        r = client.post("/api/v1/businesses",
                        json={"name": "X", "business_type": "clinic", **extra}, headers=bearer("alice"))
        assert r.status_code == 422, extra
    assert not any(p.startswith("businesses/") for p in fake_db.docs)


def test_create_validation(client):
    bad_bodies = [
        {"business_type": "clinic"},                      # name missing
        {"name": "   ", "business_type": "clinic"},       # blank name
        {"name": "X", "business_type": "bank"},           # unknown type
        {"name": "X"},                                    # type missing
        {"name": "x" * 121, "business_type": "school"},   # too long
        {"name": "X", "business_type": "school", "description": "d" * 2001},
    ]
    for body in bad_bodies:
        assert client.post("/api/v1/businesses", json=body, headers=bearer("alice")).status_code == 422


def test_all_business_types_accepted(client):
    for t in ("restaurant", "clinic", "school"):
        r = client.post("/api/v1/businesses", json={"name": t, "business_type": t}, headers=bearer("alice"))
        assert r.status_code == 201


# ---------- listing / reading ----------

def test_list_returns_only_callers_businesses(client, make_business):
    a1 = make_business("alice", name="A1")
    a2 = make_business("alice", name="A2", business_type="school")
    b1 = make_business("bob", name="B1", business_type="clinic")

    alice = client.get("/api/v1/businesses", headers=bearer("alice")).json()
    assert {b["id"] for b in alice} == {a1["id"], a2["id"]}
    assert [b["name"] for b in alice] == ["A2", "A1"]  # newest first
    bob = client.get("/api/v1/businesses", headers=bearer("bob")).json()
    assert [b["id"] for b in bob] == [b1["id"]]
    assert client.get("/api/v1/businesses", headers=bearer("carol")).json() == []


def test_list_includes_businesses_where_user_is_member_with_their_role(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    listed = client.get("/api/v1/businesses", headers=bearer("bob")).json()
    assert [(b["id"], b["role"]) for b in listed] == [(biz["id"], "member")]


def test_list_ignores_unrelated_members_subcollections(client, fake_db):
    fake_db.docs["teams/t1/members/alice-uid"] = {"uid": "alice-uid", "role": "owner"}
    assert client.get("/api/v1/businesses", headers=bearer("alice")).json() == []


def test_get_business_as_owner(client, make_business):
    biz = make_business("alice")
    r = client.get(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    assert r.status_code == 200
    assert r.json() == biz


# ---------- updating ----------

def test_owner_can_update_all_editable_fields(client, fake_db, make_business):
    biz = make_business("alice")
    r = client.patch(f"/api/v1/businesses/{biz['id']}",
                     json={"name": "Renamed", "description": "New", "business_type": "school"},
                     headers=bearer("alice"))
    assert r.status_code == 200
    body = r.json()
    assert (body["name"], body["description"], body["business_type"]) == ("Renamed", "New", "school")
    assert body["updated_at"] >= biz["updated_at"]
    assert fake_db.docs[f"businesses/{biz['id']}"]["business_type"] == "school"


def test_patch_cannot_change_protected_fields(client, fake_db, make_business):
    biz = make_business("alice")
    before = dict(fake_db.docs[f"businesses/{biz['id']}"])
    for body in ({"owner_id": "bob-uid"}, {"status": "archived"}, {"created_at": "2000-01-01T00:00:00Z"},
                 {"role": "owner"}, {"name": "ok", "owner_id": "bob-uid"}):
        r = client.patch(f"/api/v1/businesses/{biz['id']}", json=body, headers=bearer("alice"))
        assert r.status_code == 422, body
    assert fake_db.docs[f"businesses/{biz['id']}"] == before


def test_patch_requires_a_non_null_field(client, make_business):
    biz = make_business("alice")
    for body in ({}, {"name": None}, {"name": ""}):
        r = client.patch(f"/api/v1/businesses/{biz['id']}", json=body, headers=bearer("alice"))
        assert r.status_code == 422, body


def test_member_cannot_edit_business(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    before = dict(fake_db.docs[f"businesses/{biz['id']}"])
    for body in ({"name": "By Bob"}, {"business_type": "clinic"}, {"description": "x"}):
        r = client.patch(f"/api/v1/businesses/{biz['id']}", json=body, headers=bearer("bob"))
        assert r.status_code == 403, body
    assert fake_db.docs[f"businesses/{biz['id']}"] == before


def test_admin_can_edit_details_but_not_owner_controlled_settings(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    ok = client.patch(f"/api/v1/businesses/{biz['id']}", json={"name": "By Admin"}, headers=bearer("bob"))
    assert ok.status_code == 200 and ok.json()["role"] == "admin"
    denied = client.patch(f"/api/v1/businesses/{biz['id']}", json={"business_type": "clinic"},
                          headers=bearer("bob"))
    assert denied.status_code == 403
    assert fake_db.docs[f"businesses/{biz['id']}"]["business_type"] == "restaurant"
    assert fake_db.docs[f"businesses/{biz['id']}"]["name"] == "By Admin"


def test_cannot_update_archived_business(client, make_business):
    biz = make_business("alice")
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    r = client.patch(f"/api/v1/businesses/{biz['id']}", json={"name": "Zombie"}, headers=bearer("alice"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "business_archived"


# ---------- archiving ----------

def test_owner_archives_business_without_deleting_data(client, fake_db, make_business):
    biz = make_business("alice")
    r = client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    assert r.status_code == 200
    assert r.json()["status"] == "archived"

    assert fake_db.docs[f"businesses/{biz['id']}"]["status"] == "archived"      # still exists
    assert f"businesses/{biz['id']}/members/alice-uid" in fake_db.docs          # membership kept
    assert client.get(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice")).json()["status"] == "archived"
    assert client.get("/api/v1/businesses", headers=bearer("alice")).json() == []  # hidden from list


def test_archive_is_idempotent(client, make_business):
    biz = make_business("alice")
    assert client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice")).status_code == 200
    assert client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice")).status_code == 200


def test_member_and_admin_cannot_archive(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    add_member(fake_db, biz["id"], "carol", "admin")
    for user in ("bob", "carol"):
        r = client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer(user))
        assert r.status_code == 403, user
    assert fake_db.docs[f"businesses/{biz['id']}"]["status"] == "active"


# ---------- cross-tenant isolation ----------

def test_cross_tenant_access_is_rejected_for_every_operation(client, fake_db, make_business):
    alice_biz = make_business("alice", name="Alice Private")
    bid = alice_biz["id"]
    before = dict(fake_db.docs[f"businesses/{bid}"])
    url = f"/api/v1/businesses/{bid}"

    assert client.get(url, headers=bearer("bob")).status_code == 404
    assert client.patch(url, json={"name": "Hacked"}, headers=bearer("bob")).status_code == 404
    assert client.patch(url, json={"business_type": "clinic"}, headers=bearer("bob")).status_code == 404
    assert client.delete(url, headers=bearer("bob")).status_code == 404

    assert fake_db.docs[f"businesses/{bid}"] == before
    # Same response as a business that does not exist: existence is not leaked.
    missing = client.get("/api/v1/businesses/doesnotexist123", headers=bearer("bob"))
    assert client.get(url, headers=bearer("bob")).json() == missing.json()


def test_creating_a_business_does_not_grant_access_to_others(client, make_business):
    alice_biz = make_business("alice")
    make_business("bob")
    r = client.get(f"/api/v1/businesses/{alice_biz['id']}", headers=bearer("bob"))
    assert r.status_code == 404


def test_membership_without_business_document_is_not_found(client, fake_db):
    add_member(fake_db, "orphan1", "bob-uid", "owner")
    assert client.get("/api/v1/businesses/orphan1", headers=bearer("bob")).status_code == 404


def test_malformed_business_ids_return_404(client):
    for bad in ["__bad__", "a.b", "x" * 200]:
        assert client.get(f"/api/v1/businesses/{bad}", headers=bearer("alice")).status_code == 404


def test_owner_id_in_token_not_body_determines_ownership(client, fake_db, make_business):
    biz = make_business("alice")
    assert fake_db.docs[f"businesses/{biz['id']}"]["owner_id"] == "alice-uid"
    assert fake_db.docs[f"businesses/{biz['id']}/members/alice-uid"]["role"] == "owner"
    assert f"businesses/{biz['id']}/members/bob-uid" not in fake_db.docs

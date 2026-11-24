from tests.conftest import add_member, bearer


def members_url(bid, uid=""):
    return f"/api/v1/businesses/{bid}/members" + (f"/{uid}" if uid else "")


def role_in_db(fake_db, bid, user):
    doc = fake_db.docs.get(f"businesses/{bid}/members/{user}-uid")
    return doc["role"] if doc else None


# ---------- listing ----------

def test_owner_and_admin_can_list_members_ordered_by_role(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "carol", "member")
    add_member(fake_db, biz["id"], "bob", "admin")
    client.post("/api/v1/users/me", json={"display_name": "Bob B"}, headers=bearer("bob"))
    for viewer in ("alice", "bob"):
        r = client.get(members_url(biz["id"]), headers=bearer(viewer))
        assert r.status_code == 200
        assert [(m["uid"], m["role"]) for m in r.json()] == [
            ("alice-uid", "owner"), ("bob-uid", "admin"), ("carol-uid", "member")]
    bob = [m for m in r.json() if m["uid"] == "bob-uid"][0]
    assert bob["email"] == "bob@example.com" and bob["display_name"] == "Bob B"


def test_member_cannot_list_members(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    assert client.get(members_url(biz["id"]), headers=bearer("bob")).status_code == 403


def test_outsider_cannot_list_members(client, make_business):
    biz = make_business("alice")
    assert client.get(members_url(biz["id"]), headers=bearer("bob")).status_code == 404


# ---------- role changes ----------

def test_owner_promotes_member_to_admin_and_demotes_back(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": "admin"},
                     headers=bearer("alice"))
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert role_in_db(fake_db, biz["id"], "bob") == "admin"
    r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": "member"},
                     headers=bearer("alice"))
    assert r.status_code == 200 and role_in_db(fake_db, biz["id"], "bob") == "member"


def test_admin_cannot_promote_self_to_owner(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    for role in ("owner", "admin", "member"):
        r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": role},
                         headers=bearer("bob"))
        assert r.status_code == 403, role
    assert role_in_db(fake_db, biz["id"], "bob") == "admin"
    assert fake_db.docs[f"businesses/{biz['id']}"]["owner_id"] == "alice-uid"


def test_admin_cannot_promote_member_to_admin(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    add_member(fake_db, biz["id"], "carol", "member")
    r = client.patch(members_url(biz["id"], "carol-uid") + "/role", json={"role": "admin"},
                     headers=bearer("bob"))
    assert r.status_code == 403
    assert role_in_db(fake_db, biz["id"], "carol") == "member"


def test_admin_cannot_demote_another_admin(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    add_member(fake_db, biz["id"], "carol", "admin")
    r = client.patch(members_url(biz["id"], "carol-uid") + "/role", json={"role": "member"},
                     headers=bearer("bob"))
    assert r.status_code == 403 and role_in_db(fake_db, biz["id"], "carol") == "admin"


def test_member_cannot_change_roles(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": "admin"},
                     headers=bearer("bob"))
    assert r.status_code == 403 and role_in_db(fake_db, biz["id"], "bob") == "member"


def test_ownership_cannot_be_assigned_or_changed(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": "owner"},
                     headers=bearer("alice"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "ownership_transfer_unsupported"
    r = client.patch(members_url(biz["id"], "alice-uid") + "/role", json={"role": "member"},
                     headers=bearer("alice"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "cannot_modify_owner"
    assert role_in_db(fake_db, biz["id"], "bob") == "admin"
    assert role_in_db(fake_db, biz["id"], "alice") == "owner"


def test_role_change_validation_and_unknown_member(client, make_business):
    biz = make_business("alice")
    url = members_url(biz["id"], "ghost-uid") + "/role"
    assert client.patch(url, json={"role": "admin"}, headers=bearer("alice")).status_code == 404
    assert client.patch(url, json={"role": "god"}, headers=bearer("alice")).status_code == 422
    assert client.patch(url, json={"role": "admin", "uid": "x"}, headers=bearer("alice")).status_code == 422
    assert client.patch(url, json={}, headers=bearer("alice")).status_code == 422


# ---------- removal ----------

def test_owner_removes_admin_and_member(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    add_member(fake_db, biz["id"], "carol", "member")
    for uid, user in (("bob-uid", "bob"), ("carol-uid", "carol")):
        r = client.delete(members_url(biz["id"], uid), headers=bearer("alice"))
        assert r.status_code == 204 and r.content == b""
        assert role_in_db(fake_db, biz["id"], user) is None
    # Removed users lose all access immediately.
    assert client.get(f"/api/v1/businesses/{biz['id']}", headers=bearer("bob")).status_code == 404


def test_admin_removes_member_only(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    add_member(fake_db, biz["id"], "carol", "member")
    add_member(fake_db, biz["id"], "dave", "admin")
    assert client.delete(members_url(biz["id"], "carol-uid"), headers=bearer("bob")).status_code == 204

    r = client.delete(members_url(biz["id"], "dave-uid"), headers=bearer("bob"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "insufficient_role"
    r = client.delete(members_url(biz["id"], "alice-uid"), headers=bearer("bob"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "cannot_modify_owner"
    r = client.delete(members_url(biz["id"], "bob-uid"), headers=bearer("bob"))  # self
    assert r.status_code == 403
    assert role_in_db(fake_db, biz["id"], "dave") == "admin"
    assert role_in_db(fake_db, biz["id"], "alice") == "owner"


def test_owner_cannot_remove_self(client, fake_db, make_business):
    biz = make_business("alice")
    r = client.delete(members_url(biz["id"], "alice-uid"), headers=bearer("alice"))
    assert r.status_code == 403 and role_in_db(fake_db, biz["id"], "alice") == "owner"


def test_member_cannot_remove_anyone(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    add_member(fake_db, biz["id"], "carol", "member")
    assert client.delete(members_url(biz["id"], "carol-uid"), headers=bearer("bob")).status_code == 403
    assert client.delete(members_url(biz["id"], "alice-uid"), headers=bearer("bob")).status_code == 403
    assert role_in_db(fake_db, biz["id"], "carol") == "member"


def test_remove_unknown_member_404(client, make_business):
    biz = make_business("alice")
    assert client.delete(members_url(biz["id"], "ghost-uid"), headers=bearer("alice")).status_code == 404


def test_removal_is_tenant_scoped(client, fake_db, make_business):
    """Alice owns A, Bob owns B. Alice cannot touch Bob's members by using her own role."""
    a, b = make_business("alice"), make_business("bob", name="B")
    add_member(fake_db, b["id"], "carol", "member")
    for method, path, body in (
        ("delete", members_url(b["id"], "carol-uid"), None),
        ("patch", members_url(b["id"], "carol-uid") + "/role", {"role": "admin"}),
        ("get", members_url(b["id"]), None),
    ):
        kwargs = {"json": body} if body else {}
        r = getattr(client, method)(path, headers=bearer("alice"), **kwargs)
        assert r.status_code == 404, (method, path)
    assert role_in_db(fake_db, b["id"], "carol") == "member"
    assert a["id"] != b["id"]


def test_members_of_archived_business_are_frozen(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    r = client.delete(members_url(biz["id"], "bob-uid"), headers=bearer("alice"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "business_archived"
    r = client.patch(members_url(biz["id"], "bob-uid") + "/role", json={"role": "admin"},
                     headers=bearer("alice"))
    assert r.status_code == 409


def test_unauthenticated_member_endpoints(client):
    for method, path in (("get", "/members"), ("delete", "/members/x"), ("patch", "/members/x/role")):
        assert getattr(client, method)(f"/api/v1/businesses/abc{path}").status_code == 401

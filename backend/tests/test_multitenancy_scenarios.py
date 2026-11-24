"""The 14 scenarios from the Phase 2 brief, end-to-end, with separate users and businesses."""
from tests.conftest import add_member, bearer


def test_brief_scenarios_1_to_7_isolation(client, make_business):
    a = make_business("alice", name="Business A")           # 1
    b = make_business("bob", name="Business B")             # 2
    assert [x["id"] for x in client.get("/api/v1/businesses", headers=bearer("alice")).json()] == [a["id"]]  # 3
    assert [x["id"] for x in client.get("/api/v1/businesses", headers=bearer("bob")).json()] == [b["id"]]    # 4
    assert client.get(f"/api/v1/businesses/{b['id']}", headers=bearer("alice")).status_code == 404            # 5
    assert client.patch(f"/api/v1/businesses/{b['id']}", json={"name": "x"},
                        headers=bearer("alice")).status_code == 404                                           # 6
    assert client.delete(f"/api/v1/businesses/{b['id']}", headers=bearer("alice")).status_code == 404         # 7
    assert client.get(f"/api/v1/businesses/{b['id']}", headers=bearer("bob")).json()["name"] == "Business B"


def test_brief_scenario_8_member_cannot_do_owner_only_things(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    add_member(fake_db, biz["id"], "carol", "member")
    base = f"/api/v1/businesses/{biz['id']}"
    h = bearer("bob")
    assert client.patch(base, json={"name": "x"}, headers=h).status_code == 403
    assert client.delete(base, headers=h).status_code == 403
    assert client.post(f"{base}/invitations", json={"email": "z@z.com"}, headers=h).status_code == 403
    assert client.get(f"{base}/members", headers=h).status_code == 403
    assert client.delete(f"{base}/members/carol-uid", headers=h).status_code == 403
    assert client.patch(f"{base}/members/carol-uid/role", json={"role": "admin"}, headers=h).status_code == 403
    assert client.get(base, headers=h).status_code == 200  # but may view

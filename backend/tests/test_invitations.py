from dataclasses import replace
from datetime import datetime, timedelta, timezone

from tests.conftest import add_member, bearer


def invite(client, bid, who, email, role="member"):
    return client.post(f"/api/v1/businesses/{bid}/invitations",
                       json={"email": email, "role": role}, headers=bearer(who))


def inv_doc(fake_db, bid):
    docs = [d for p, d in fake_db.docs.items() if p.startswith(f"businesses/{bid}/invitations/")]
    return docs


def expire(fake_db, bid):
    for p, d in fake_db.docs.items():
        if p.startswith(f"businesses/{bid}/invitations/"):
            d["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)


# ---------- creating ----------

def test_owner_invites_admin_and_member_with_normalized_email(client, fake_db, make_business):
    biz = make_business("alice")
    r = invite(client, biz["id"], "alice", "  Bob@Example.COM ", "admin")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "bob@example.com" and body["role"] == "admin"
    assert body["status"] == "pending" and body["invited_by"] == "alice-uid"
    assert body["business_id"] == biz["id"] and body["accepted_at"] is None
    assert body["expires_at"] > body["created_at"]
    assert invite(client, biz["id"], "alice", "carol@example.com", "member").status_code == 201
    stored = inv_doc(fake_db, biz["id"])
    assert len(stored) == 2
    assert set(stored[0]) == {"invitation_id", "business_id", "email", "role", "invited_by",
                              "status", "created_at", "expires_at", "accepted_at"}


def test_admin_can_invite_members_only(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    assert invite(client, biz["id"], "bob", "carol@example.com", "member").status_code == 201
    r = invite(client, biz["id"], "bob", "dave@example.com", "admin")
    assert r.status_code == 403 and r.json()["error"]["code"] == "insufficient_role"


def test_member_cannot_invite(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    assert invite(client, biz["id"], "bob", "carol@example.com").status_code == 403
    assert inv_doc(fake_db, biz["id"]) == []


def test_outsider_cannot_invite_to_someone_elses_business(client, make_business, fake_db):
    biz = make_business("alice")
    assert invite(client, biz["id"], "bob", "bob@example.com", "admin").status_code == 404
    assert inv_doc(fake_db, biz["id"]) == []


def test_owner_role_cannot_be_invited_and_validation(client, make_business):
    biz = make_business("alice")
    for body in ({"email": "x@y.com", "role": "owner"}, {"email": "not-an-email"}, {"email": ""},
                 {"role": "member"}, {"email": "x@y.com", "status": "accepted"},
                 {"email": "x@y.com", "invited_by": "bob-uid"}):
        r = client.post(f"/api/v1/businesses/{biz['id']}/invitations", json=body, headers=bearer("alice"))
        assert r.status_code == 422, body


def test_role_defaults_to_member(client, make_business):
    biz = make_business("alice")
    r = client.post(f"/api/v1/businesses/{biz['id']}/invitations", json={"email": "bob@example.com"},
                    headers=bearer("alice"))
    assert r.status_code == 201 and r.json()["role"] == "member"


# ---------- duplicates ----------

def test_duplicate_pending_invitation_rejected_case_insensitively(client, fake_db, make_business):
    biz = make_business("alice")
    assert invite(client, biz["id"], "alice", "bob@example.com").status_code == 201
    for email in ("bob@example.com", "BOB@EXAMPLE.COM"):
        r = invite(client, biz["id"], "alice", email)
        assert r.status_code == 409 and r.json()["error"]["code"] == "invitation_exists"
    assert len(inv_doc(fake_db, biz["id"])) == 1


def test_cannot_invite_existing_member_or_self(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "member")
    for email in ("bob@example.com", "alice@example.com", "ALICE@example.com"):
        r = invite(client, biz["id"], "alice", email)
        assert r.status_code == 409 and r.json()["error"]["code"] == "already_member", email
    assert inv_doc(fake_db, biz["id"]) == []


def test_reinvite_allowed_after_expiry_and_after_decline(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    expire(fake_db, biz["id"])
    assert invite(client, biz["id"], "alice", "bob@example.com").status_code == 201  # replaces expired
    client.post(f"/api/v1/invitations/{inv['invitation_id']}/decline", headers=bearer("bob"))
    assert invite(client, biz["id"], "alice", "bob@example.com").status_code == 201  # replaces declined
    assert len(inv_doc(fake_db, biz["id"])) == 1


def test_cannot_invite_into_archived_business(client, make_business):
    biz = make_business("alice")
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    r = invite(client, biz["id"], "alice", "bob@example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "business_archived"


# ---------- listing ----------

def test_business_side_listing_owner_and_admin_only(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    add_member(fake_db, biz["id"], "carol", "member")
    invite(client, biz["id"], "alice", "dave@example.com")
    for who, code in (("alice", 200), ("bob", 200), ("carol", 403)):
        r = client.get(f"/api/v1/businesses/{biz['id']}/invitations", headers=bearer(who))
        assert r.status_code == code, who
    assert [i["email"] for i in client.get(f"/api/v1/businesses/{biz['id']}/invitations",
                                           headers=bearer("alice")).json()] == ["dave@example.com"]
    assert client.get(f"/api/v1/businesses/{biz['id']}/invitations", headers=bearer("eve")).status_code == 404


def test_my_invitations_shows_only_own_pending_unexpired(client, fake_db, make_business):
    a = make_business("alice", name="Alpha")
    b = make_business("carol", name="Gamma")
    invite(client, a["id"], "alice", "bob@example.com")
    invite(client, b["id"], "carol", "bob@example.com", "admin")
    invite(client, a["id"], "alice", "dave@example.com")  # someone else's
    mine = client.get("/api/v1/invitations", headers=bearer("bob")).json()
    assert {(i["business_name"], i["role"]) for i in mine} == {("Alpha", "member"), ("Gamma", "admin")}
    assert all(i["email"] == "bob@example.com" for i in mine)
    # Mixed-case token email (Dave@Example.com) still matches the normalized invitation.
    assert len(client.get("/api/v1/invitations", headers=bearer("dave")).json()) == 1
    assert client.get("/api/v1/invitations", headers=bearer("carol")).json() == []
    expire(fake_db, a["id"])
    assert [i["business_name"] for i in client.get("/api/v1/invitations", headers=bearer("bob")).json()] == ["Gamma"]


def test_my_invitations_hides_archived_businesses(client, make_business):
    biz = make_business("alice")
    invite(client, biz["id"], "alice", "bob@example.com")
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    assert client.get("/api/v1/invitations", headers=bearer("bob")).json() == []


# ---------- accepting ----------

def test_accept_creates_membership_and_marks_accepted(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com", "admin").json()
    r = client.post(f"/api/v1/invitations/{inv['invitation_id']}/accept", headers=bearer("bob"))
    assert r.status_code == 200
    assert r.json()["status"] == "accepted" and r.json()["accepted_at"] is not None

    member = fake_db.docs[f"businesses/{biz['id']}/members/bob-uid"]
    assert member["role"] == "admin" and member["email"] == "bob@example.com" and member["uid"] == "bob-uid"
    assert fake_db.docs[f"businesses/{biz['id']}/invitations/{inv['invitation_id']}"]["status"] == "accepted"
    # Bob now has access, with the invited role; the business appears in his list.
    got = client.get(f"/api/v1/businesses/{biz['id']}", headers=bearer("bob")).json()
    assert got["role"] == "admin"
    assert [b["id"] for b in client.get("/api/v1/businesses", headers=bearer("bob")).json()] == [biz["id"]]
    assert client.get("/api/v1/invitations", headers=bearer("bob")).json() == []


def test_only_the_intended_email_can_accept(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    url = f"/api/v1/invitations/{inv['invitation_id']}"
    for who in ("carol", "alice"):  # a different verified user, even the inviter
        r = client.post(f"{url}/accept", headers=bearer(who))
        assert r.status_code == 404 and r.json()["error"]["code"] == "invitation_not_found", who
        assert client.post(f"{url}/decline", headers=bearer(who)).status_code == 404
    assert f"businesses/{biz['id']}/members/carol-uid" not in fake_db.docs
    assert fake_db.docs[f"businesses/{biz['id']}/invitations/{inv['invitation_id']}"]["status"] == "pending"
    # Same response as a non-existent invitation: no probing.
    ghost = client.post("/api/v1/invitations/" + "0" * 32 + "/accept", headers=bearer("carol"))
    assert ghost.json() == client.post(f"{url}/accept", headers=bearer("carol")).json()


def test_unverified_email_cannot_use_invitations(client, fake_db, make_business):
    """eve signed up with an address she does not control: she must not be able to claim it."""
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "eve@example.com").json()
    for method, path in (("get", "/api/v1/invitations"),
                         ("post", f"/api/v1/invitations/{inv['invitation_id']}/accept"),
                         ("post", f"/api/v1/invitations/{inv['invitation_id']}/decline")):
        r = getattr(client, method)(path, headers=bearer("eve"))
        assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"
    assert f"businesses/{biz['id']}/members/eve-uid" not in fake_db.docs


def test_unverified_email_can_use_invitations_when_verification_is_disabled(client, make_business):
    client.app.state.settings = replace(client.app.state.settings, require_verified_email=False)
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "eve@example.com").json()

    listed = client.get("/api/v1/invitations", headers=bearer("eve"))
    assert listed.status_code == 200
    assert [item["invitation_id"] for item in listed.json()] == [inv["invitation_id"]]

    accepted = client.post(
        f"/api/v1/invitations/{inv['invitation_id']}/accept",
        headers=bearer("eve"),
    )
    assert accepted.status_code == 200


def test_expired_invitation_cannot_be_accepted(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    expire(fake_db, biz["id"])
    for action in ("accept", "decline"):
        r = client.post(f"/api/v1/invitations/{inv['invitation_id']}/{action}", headers=bearer("bob"))
        assert r.status_code == 409 and r.json()["error"]["code"] == "invitation_expired"
    assert f"businesses/{biz['id']}/members/bob-uid" not in fake_db.docs
    listed = client.get(f"/api/v1/businesses/{biz['id']}/invitations", headers=bearer("alice")).json()
    assert listed[0]["status"] == "expired"


def test_cannot_accept_twice_or_after_decline(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    url = f"/api/v1/invitations/{inv['invitation_id']}"
    assert client.post(f"{url}/accept", headers=bearer("bob")).status_code == 200
    r = client.post(f"{url}/accept", headers=bearer("bob"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "invitation_already_accepted"
    assert len([p for p in fake_db.docs if p.startswith(f"businesses/{biz['id']}/members/")]) == 2

    inv2 = invite(client, biz["id"], "alice", "carol@example.com").json()
    url2 = f"/api/v1/invitations/{inv2['invitation_id']}"
    assert client.post(f"{url2}/decline", headers=bearer("carol")).json()["status"] == "declined"
    r = client.post(f"{url2}/accept", headers=bearer("carol"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "invitation_already_declined"
    assert f"businesses/{biz['id']}/members/carol-uid" not in fake_db.docs


def test_accept_never_overwrites_an_existing_membership(client, fake_db, make_business):
    """Duplicate-membership safety: if Bob became a member some other way, accepting must not
    create a second membership or silently change his role."""
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com", "admin").json()
    add_member(fake_db, biz["id"], "bob", "member")
    r = client.post(f"/api/v1/invitations/{inv['invitation_id']}/accept", headers=bearer("bob"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_member"
    assert fake_db.docs[f"businesses/{biz['id']}/members/bob-uid"]["role"] == "member"


def test_cannot_accept_into_archived_business(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    r = client.post(f"/api/v1/invitations/{inv['invitation_id']}/accept", headers=bearer("bob"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "business_archived"
    assert f"businesses/{biz['id']}/members/bob-uid" not in fake_db.docs


def test_malformed_and_unknown_invitation_ids(client):
    for bad in ("nope", "../x", "G" * 32, "0" * 32):
        r = client.post(f"/api/v1/invitations/{bad}/accept", headers=bearer("bob"))
        assert r.status_code in (404,), bad


def test_decline_keeps_no_membership(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    r = client.post(f"/api/v1/invitations/{inv['invitation_id']}/decline", headers=bearer("bob"))
    assert r.status_code == 200 and r.json()["status"] == "declined"
    assert f"businesses/{biz['id']}/members/bob-uid" not in fake_db.docs
    assert client.get(f"/api/v1/businesses/{biz['id']}", headers=bearer("bob")).status_code == 404


def test_invitation_endpoints_require_authentication(client):
    for method, path in (("get", "/api/v1/invitations"), ("post", "/api/v1/invitations/x/accept"),
                         ("post", "/api/v1/invitations/x/decline"),
                         ("get", "/api/v1/businesses/abc/invitations"),
                         ("post", "/api/v1/businesses/abc/invitations")):
        assert getattr(client, method)(path).status_code == 401, path


def test_removed_member_can_be_reinvited(client, fake_db, make_business):
    biz = make_business("alice")
    inv = invite(client, biz["id"], "alice", "bob@example.com").json()
    client.post(f"/api/v1/invitations/{inv['invitation_id']}/accept", headers=bearer("bob"))
    client.delete(f"/api/v1/businesses/{biz['id']}/members/bob-uid", headers=bearer("alice"))
    inv2 = invite(client, biz["id"], "alice", "bob@example.com")
    assert inv2.status_code == 201
    r = client.post(f"/api/v1/invitations/{inv2.json()['invitation_id']}/accept", headers=bearer("bob"))
    assert r.status_code == 200

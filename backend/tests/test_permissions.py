import pytest

from app.core.permissions import Permission, can_invite_role, can_manage_member, has_permission
from app.dependencies.auth import require_platform_admin
from app.schemas.business import BusinessRole as R
from tests.conftest import add_member, bearer

P = Permission


@pytest.mark.parametrize("role,allowed", [
    (R.owner, set(Permission)),
    (R.admin, {P.BUSINESS_VIEW, P.BUSINESS_EDIT, P.MEMBERS_VIEW, P.MEMBERS_REMOVE, P.INVITATIONS_VIEW,
               P.INVITATIONS_CREATE, P.DOCUMENTS_MANAGE, P.AGENTS_MANAGE, P.INTEGRATIONS_MANAGE}),
    (R.member, {P.BUSINESS_VIEW}),
])
def test_permission_matrix(role, allowed):
    for perm in Permission:
        assert has_permission(role, perm) == (perm in allowed), (role, perm)


def test_admin_never_gets_owner_only_permissions():
    for perm in (P.BILLING_MANAGE, P.BUSINESS_ARCHIVE, P.MEMBERS_CHANGE_ROLE, P.BUSINESS_EDIT_SETTINGS):
        assert not has_permission(R.admin, perm)


def test_manage_and_invite_rules():
    assert can_manage_member(R.owner, R.admin) and can_manage_member(R.owner, R.member)
    assert can_manage_member(R.admin, R.member)
    assert not can_manage_member(R.admin, R.admin)
    assert not can_manage_member(R.admin, R.owner) and not can_manage_member(R.owner, R.owner)
    assert not can_manage_member(R.member, R.member)
    assert can_invite_role(R.owner, R.admin) and can_invite_role(R.owner, R.member)
    assert can_invite_role(R.admin, R.member) and not can_invite_role(R.admin, R.admin)
    assert not can_invite_role(R.owner, R.owner) and not can_invite_role(R.member, R.member)


# ---------- System Admin is platform-level only ----------

def test_system_admin_is_not_a_member_of_every_business(client, make_business):
    biz = make_business("alice")
    url = f"/api/v1/businesses/{biz['id']}"
    for path in (url, f"{url}/members", f"{url}/invitations"):
        assert client.get(path, headers=bearer("root")).status_code == 404, path
    assert client.patch(url, json={"name": "x"}, headers=bearer("root")).status_code == 404
    assert client.delete(url, headers=bearer("root")).status_code == 404
    assert client.get("/api/v1/businesses", headers=bearer("root")).json() == []


def test_platform_admin_dependency(client):
    client.app.add_api_route("/__platform/ping", lambda user=__import__("fastapi").Depends(
        require_platform_admin): {"ok": True}, methods=["GET"])
    assert client.get("/__platform/ping", headers=bearer("root")).status_code == 200
    denied = client.get("/__platform/ping", headers=bearer("alice"))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "platform_admin_required"
    assert client.get("/__platform/ping", headers=bearer("fake")).status_code == 403


def test_business_owner_role_does_not_grant_platform_access(client, make_business):
    make_business("alice")
    client.app.add_api_route("/__platform/ping2", lambda user=__import__("fastapi").Depends(
        require_platform_admin): {"ok": True}, methods=["GET"])
    assert client.get("/__platform/ping2", headers=bearer("alice")).status_code == 403

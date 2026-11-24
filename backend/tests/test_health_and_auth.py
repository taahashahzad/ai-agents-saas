import pytest

from tests.conftest import ALLOWED_ORIGIN, bearer

PROTECTED = [
    ("GET", "/api/v1/users/me"),
    ("POST", "/api/v1/users/me"),
    ("POST", "/api/v1/businesses"),
    ("GET", "/api/v1/businesses"),
    ("GET", "/api/v1/businesses/abc123"),
    ("PATCH", "/api/v1/businesses/abc123"),
    ("DELETE", "/api/v1/businesses/abc123"),
]


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("method,path", PROTECTED)
def test_missing_authentication_is_rejected(client, method, path):
    r = client.request(method, path, json={})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_required"
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Token abc", "Basic abc", "Bearer", "Bearer "])
def test_malformed_authorization_header_is_rejected(client, header):
    r = client.get("/api/v1/users/me", headers={"Authorization": header})
    assert r.status_code == 401


@pytest.mark.parametrize("token,code,status", [
    ("garbage", "invalid_token", 401),
    ("expired", "token_expired", 401),
    ("revoked", "token_revoked", 401),
    ("disabled", "user_disabled", 401),
    ("certs-down", "service_unavailable", 503),
])
def test_bad_tokens(client, token, code, status):
    r = client.get("/api/v1/businesses", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == status
    assert r.json()["error"]["code"] == code


def test_cors_allows_only_configured_origin(client):
    ok = client.options("/api/v1/businesses", headers={
        "Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert ok.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    bad = client.options("/api/v1/businesses", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_unknown_route_uses_consistent_error_shape(client):
    r = client.get("/api/v1/nope", headers=bearer("alice"))
    assert r.status_code == 404
    assert set(r.json()["error"]) >= {"code", "message"}

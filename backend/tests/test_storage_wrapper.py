"""R2 storage layer, tested with REAL boto3 clients whose HTTP layer is stubbed (botocore Stubber),
so the exact boto3 calls and error handling are verified without any network or credentials."""
import io
import logging
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.core.config import Settings, get_settings
from app.core.r2 import StorageNotConfiguredError, get_r2_client
from app.core.storage import R2Storage, StorageError, StorageObjectNotFound

ENDPOINT = "https://acct123.r2.cloudflarestorage.com"
KEY = "businesses/b1/knowledge/d1/original.pdf"


def make():
    client = boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id="k",
                          aws_secret_access_key="s", region_name="auto")
    return R2Storage(client, "my-bucket"), client, Stubber(client)


def body(data: bytes):
    return StreamingBody(io.BytesIO(data), len(data))


# ---------------------------------------------------------------- operations

def test_upload_download_delete_send_the_expected_requests():
    storage, _, stub = make()
    stub.add_response("put_object", {}, {"Bucket": "my-bucket", "Key": KEY, "Body": b"data",
                                         "ContentType": "application/pdf"})
    stub.add_response("get_object", {"Body": body(b"data")}, {"Bucket": "my-bucket", "Key": KEY})
    stub.add_response("delete_object", {}, {"Bucket": "my-bucket", "Key": KEY})
    with stub:
        storage.upload_bytes(KEY, b"data", "application/pdf")
        assert storage.download_bytes(KEY) == b"data"
        storage.delete(KEY)
        stub.assert_no_pending_responses()


def test_missing_object_maps_to_not_found():
    storage, _, stub = make()
    stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    with stub, pytest.raises(StorageObjectNotFound):
        storage.download_bytes(KEY)


def test_r2_errors_are_translated_and_nothing_sensitive_is_logged(caplog):
    # Even with the app at DEBUG, boto/urllib3 internals (which log object keys and request
    # parameters) must stay silent.
    from app.main import create_app
    create_app(r2_settings(log_level="DEBUG"))
    storage, _, stub = make()
    msg = "secret-bucket credentials key=AKIA123 for acct123"
    stub.add_client_error("put_object", "AccessDenied", msg, 403)
    stub.add_client_error("get_object", "InternalError", msg, 500)
    stub.add_client_error("delete_object", "AccessDenied", msg, 403)
    with stub, caplog.at_level(logging.DEBUG):
        for call in (lambda: storage.upload_bytes(KEY, b"x", "text/plain"),
                     lambda: storage.download_bytes(KEY),
                     lambda: storage.delete(KEY)):
            with pytest.raises(StorageError) as exc:
                call()
            assert "secret" not in str(exc.value) and not isinstance(exc.value, StorageObjectNotFound)
    logged = caplog.text
    assert "AccessDenied" in logged                       # the error CODE is useful and safe
    for leaked in ("secret-bucket", "AKIA123", KEY, "businesses/"):
        assert leaked not in logged


def test_network_failures_become_storage_errors():
    storage, client, _ = make()
    client.put_object = Mock(side_effect=EndpointConnectionError(endpoint_url="https://secret-host"))
    client.get_object = Mock(side_effect=EndpointConnectionError(endpoint_url="https://secret-host"))
    client.delete_object = Mock(side_effect=EndpointConnectionError(endpoint_url="https://secret-host"))
    for call in (lambda: storage.upload_bytes(KEY, b"x", "text/plain"), lambda: storage.download_bytes(KEY),
                 lambda: storage.delete(KEY)):
        with pytest.raises(StorageError) as exc:
            call()
        assert "secret-host" not in str(exc.value)


def test_delete_is_idempotent_when_object_is_already_gone():
    storage, _, stub = make()
    stub.add_client_error("delete_object", service_error_code="NoSuchKey", http_status_code=404)
    with stub:
        storage.delete(KEY)  # no error


@pytest.mark.parametrize("bad_key", ["", "/abs/path", "businesses/../other/x", "a/../b", "k" * 1025])
def test_unsafe_keys_never_reach_r2(bad_key):
    storage, client, _ = make()
    client.put_object = client.get_object = client.delete_object = Mock()
    for call in (lambda: storage.upload_bytes(bad_key, b"x", "text/plain"),
                 lambda: storage.download_bytes(bad_key), lambda: storage.delete(bad_key)):
        with pytest.raises(StorageError):
            call()
    client.put_object.assert_not_called()
    client.get_object.assert_not_called()
    client.delete_object.assert_not_called()


# ---------------------------------------------------------------- client + settings

def r2_settings(**over):
    base = dict(app_env="test", cors_origins=["http://x"], firebase_credentials_path=None,
                firebase_project_id=None, check_token_revoked=False, log_level="WARNING",
                r2_access_key_id="key-id", r2_secret_access_key="very-secret", r2_bucket_name="my-bucket",
                r2_endpoint_url=ENDPOINT)
    return Settings(**{**base, **over})


def test_client_uses_r2_endpoint_region_auto_and_is_cached():
    client = get_r2_client(r2_settings())
    assert client.meta.endpoint_url == ENDPOINT and client.meta.region_name == "auto"
    assert get_r2_client(r2_settings()) is client


@pytest.mark.parametrize("missing", ["r2_access_key_id", "r2_secret_access_key", "r2_bucket_name",
                                     "r2_endpoint_url"])
def test_partial_configuration_counts_as_not_configured(missing):
    settings = r2_settings(**{missing: None})
    assert settings.r2_configured is False
    with pytest.raises(StorageNotConfiguredError):
        get_r2_client(settings)


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME",
                 "R2_ENDPOINT_URL", "R2_REGION", "MAX_UPLOAD_MB", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_settings_derive_endpoint_from_account_id_and_trim_values(clean_env):
    clean_env.setenv("R2_ACCOUNT_ID", " acct123 \n")
    clean_env.setenv("R2_ACCESS_KEY_ID", "key-id\n")
    clean_env.setenv("R2_SECRET_ACCESS_KEY", " very-secret ")
    clean_env.setenv("R2_BUCKET_NAME", "my-bucket")
    s = get_settings()
    assert s.r2_endpoint_url == ENDPOINT and s.r2_region == "auto" and s.r2_configured
    assert (s.r2_access_key_id, s.r2_secret_access_key) == ("key-id", "very-secret")


def test_explicit_endpoint_wins_and_trailing_slash_is_removed(clean_env):
    clean_env.setenv("R2_ACCOUNT_ID", "acct123")
    clean_env.setenv("R2_ENDPOINT_URL", "https://acct123.eu.r2.cloudflarestorage.com/")
    assert get_settings().r2_endpoint_url == "https://acct123.eu.r2.cloudflarestorage.com"


def test_non_https_endpoint_is_rejected_at_startup(clean_env):
    clean_env.setenv("R2_ENDPOINT_URL", "http://acct123.r2.cloudflarestorage.com")
    with pytest.raises(RuntimeError, match="https://"):
        get_settings()


def test_unset_means_not_configured_and_secrets_never_appear_in_repr(clean_env):
    assert get_settings().r2_configured is False
    secret_settings = r2_settings()
    assert "very-secret" not in repr(secret_settings) and "key-id" not in repr(secret_settings)


# ---------------------------------------------------------------- what actually goes over the wire

class _Captured(Exception):
    pass


def test_boto3_builds_r2_compatible_requests():
    """Inspect the real signed HTTP request (aborted before any network I/O)."""
    client = get_r2_client(r2_settings(r2_endpoint_url="https://wire-test.r2.cloudflarestorage.com"))
    captured = []

    def grab(request, **_):
        captured.append(request)
        raise _Captured()

    client.meta.events.register("before-send.s3.PutObject", grab)
    with pytest.raises(_Captured):
        client.put_object(Bucket="my-bucket", Key=KEY, Body=b"hello", ContentType="application/pdf")
    req = captured[0]
    h = {(k.decode() if isinstance(k, bytes) else k).lower(): (v.decode() if isinstance(v, bytes) else v)
         for k, v in req.headers.items()}
    assert req.url == f"https://wire-test.r2.cloudflarestorage.com/my-bucket/{KEY}"      # path-style
    assert h["authorization"].startswith("AWS4-HMAC-SHA256")
    assert "/auto/s3/aws4_request" in h["authorization"]                                 # region "auto"
    assert not [name for name in h if name.startswith("x-amz-checksum")]                 # R2-safe
    assert "x-amz-sdk-checksum-algorithm" not in h
    assert h["content-type"] == "application/pdf"


class FakeS3Client:
    """Minimal boto3-S3 look-alike, so the REAL R2Storage class runs end-to-end in API tests."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[(Bucket, Key)] = (bytes(Body), ContentType)

    def get_object(self, Bucket, Key):
        from botocore.exceptions import ClientError
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "x"}}, "GetObject")
        return {"Body": body(self.objects[(Bucket, Key)][0])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_full_document_flow_through_the_real_r2_storage_class(client, make_business):
    from tests.conftest import bearer
    from app.dependencies.storage import get_storage
    s3 = FakeS3Client()
    client.app.dependency_overrides[get_storage] = lambda: R2Storage(s3, "my-bucket")
    biz = make_business("alice")
    url = f"/api/v1/businesses/{biz['id']}/documents"

    r = client.post(url, files={"file": ("menu.txt", b"Burger 9.99", "text/plain")}, headers=bearer("alice"))
    assert r.status_code == 201 and r.json()["status"] == "processed"
    did = r.json()["document_id"]
    base = f"businesses/{biz['id']}/knowledge/{did}"
    assert sorted(k for _, k in s3.objects) == [f"{base}/extracted.txt", f"{base}/original.txt"]
    assert {b for b, _ in s3.objects} == {"my-bucket"}
    assert s3.objects[("my-bucket", f"{base}/original.txt")][1] == "text/plain; charset=utf-8"

    dl = client.get(f"{url}/{did}/download", headers=bearer("alice"))
    assert dl.status_code == 200 and dl.content == b"Burger 9.99"

    assert client.delete(f"{url}/{did}", headers=bearer("alice")).status_code == 204
    assert s3.objects == {}
    assert client.get(f"{url}/{did}/download", headers=bearer("alice")).status_code == 404

    # Object removed behind our back -> clean 404, not a crash.
    r = client.post(url, files={"file": ("b.txt", b"hi", "text/plain")}, headers=bearer("alice"))
    s3.objects.clear()
    assert client.get(f"{url}/{r.json()['document_id']}/download", headers=bearer("alice")).status_code == 404

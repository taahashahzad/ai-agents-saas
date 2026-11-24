import pytest

from app.core import storage as _storage_mod  # noqa: F401  (ensures module imports cleanly)
from tests.conftest import add_member, bearer
from tests.files import DOCX_MIME, make_blank_pdf, make_broken_docx, make_docx, make_pdf


def docs_url(bid, suffix=""):
    return f"/api/v1/businesses/{bid}/documents{suffix}"


def upload(client, bid, who, filename="menu.txt", data=b"Burger 9.99\nFries 3.50", ctype="text/plain"):
    return client.post(docs_url(bid), files={"file": (filename, data, ctype)}, headers=bearer(who))


# ---------------------------------------------------------------- upload + extraction

def test_owner_uploads_and_document_is_processed(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", "Menu 2024.txt", b"Burger 9.99\n\n\n\nFries   3.50")
    assert r.status_code == 201
    doc = r.json()
    did = doc["document_id"]
    assert doc["status"] == "processed" and doc["processing_error"] is None
    assert doc["business_id"] == biz["id"] and doc["uploaded_by"] == "alice-uid"
    assert doc["file_type"] == "txt" and doc["filename"] == "Menu 2024.txt"
    assert doc["file_size"] == len(b"Burger 9.99\n\n\n\nFries   3.50")
    assert doc["extracted_character_count"] == len("Burger 9.99\n\nFries 3.50")
    # Private storage details are never exposed.
    assert not {"storage_path", "extracted_text_path", "is_deleted"} & set(doc)

    base = f"businesses/{biz['id']}/knowledge/{did}"
    assert fake_storage.paths() == [f"{base}/extracted.txt", f"{base}/original.txt"]
    assert fake_storage.objects[f"{base}/extracted.txt"][0].decode() == "Burger 9.99\n\nFries 3.50"

    stored = fake_db.docs[f"businesses/{biz['id']}/documents/{did}"]
    assert stored["storage_path"] == f"{base}/original.txt"
    assert stored["extracted_text_path"] == f"{base}/extracted.txt"
    assert stored["is_deleted"] is False and stored["status"] == "processed"
    assert {"document_id", "business_id", "filename", "original_filename", "file_type", "mime_type",
            "file_size", "storage_path", "uploaded_by", "uploaded_at", "updated_at", "status",
            "processing_error", "extracted_text_path", "extracted_character_count",
            "is_deleted"} <= set(stored)
    # Raw document text is NOT stored in Firestore.
    assert "Burger" not in str(stored)


def test_admin_uploads_successfully(client, fake_db, make_business):
    biz = make_business("alice")
    add_member(fake_db, biz["id"], "bob", "admin")
    r = upload(client, biz["id"], "bob")
    assert r.status_code == 201 and r.json()["uploaded_by"] == "bob-uid"


@pytest.mark.parametrize("filename,data,ctype,expected", [
    ("a.pdf", make_pdf("Opening hours nine to five"), "application/pdf", "Opening hours nine to five"),
    ("a.docx", make_docx(["Clinic policy", "Be on time"], [["Service", "Price"], ["Checkup", "50"]]),
     DOCX_MIME, "Clinic policy\nBe on time\nService | Price\nCheckup | 50"),
    ("a.txt", "Café menu".encode("utf-8"), "text/plain", "Café menu"),
    ("a.txt", "Caf\xe9 windows".encode("cp1252"), "text/plain", "Café windows"),
    ("a.csv", b"item,price\nBurger,9.99\nFries,\n", "text/csv",
     "Columns: item | price\nitem: Burger | price: 9.99\nitem: Fries"),
    ("a.csv", b"name;fee\nGrade 1;100\n", "application/vnd.ms-excel",
     "Columns: name | fee\nname: Grade 1 | fee: 100"),
])
def test_text_extraction_per_file_type(client, fake_storage, make_business, filename, data, ctype, expected):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", filename, data, ctype)
    assert r.status_code == 201 and r.json()["status"] == "processed", r.text
    extracted = [v[0].decode() for p, v in fake_storage.objects.items() if p.endswith("extracted.txt")]
    assert extracted == [expected]


# ---------------------------------------------------------------- permissions + tenancy

def test_member_cannot_upload_delete_or_retry_but_can_view_and_download(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    add_member(fake_db, biz["id"], "bob", "member")
    before = dict(fake_storage.objects)

    assert upload(client, biz["id"], "bob").status_code == 403
    assert client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("bob")).status_code == 403
    assert client.post(docs_url(biz["id"], f"/{did}/retry"), headers=bearer("bob")).status_code == 403
    assert fake_storage.objects == before

    assert client.get(docs_url(biz["id"]), headers=bearer("bob")).status_code == 200
    assert client.get(docs_url(biz["id"], f"/{did}"), headers=bearer("bob")).status_code == 200
    dl = client.get(docs_url(biz["id"], f"/{did}/download"), headers=bearer("bob"))
    assert dl.status_code == 200 and dl.content == b"Burger 9.99\nFries 3.50"


def test_users_only_see_documents_of_their_own_businesses(client, make_business):
    a, b = make_business("alice", name="A"), make_business("bob", name="B")
    da = upload(client, a["id"], "alice", "a.txt").json()["document_id"]
    db_ = upload(client, b["id"], "bob", "b.txt").json()["document_id"]
    assert [d["document_id"] for d in client.get(docs_url(a["id"]), headers=bearer("alice")).json()["items"]] == [da]
    assert [d["document_id"] for d in client.get(docs_url(b["id"]), headers=bearer("bob")).json()["items"]] == [db_]
    assert client.get(docs_url(b["id"]), headers=bearer("alice")).status_code == 404
    assert client.get(docs_url(a["id"]), headers=bearer("carol")).status_code == 404


def test_cross_tenant_download_delete_get_retry_are_rejected(client, fake_storage, fake_db, make_business):
    a, b = make_business("alice", name="A"), make_business("bob", name="B")
    victim = upload(client, b["id"], "bob", "secret.txt", b"private plans").json()["document_id"]
    snapshot_objects = dict(fake_storage.objects)

    for who, bid in (("alice", b["id"]),   # not a member of B
                     ("alice", a["id"])):  # member of A, but B's document ID (ID-swapping)
        for method, suffix in (("get", f"/{victim}"), ("get", f"/{victim}/download"),
                               ("delete", f"/{victim}"), ("post", f"/{victim}/retry")):
            r = getattr(client, method)(docs_url(bid, suffix), headers=bearer(who))
            assert r.status_code == 404, (who, bid, method, suffix)
    assert fake_storage.objects == snapshot_objects
    assert fake_db.docs[f"businesses/{b['id']}/documents/{victim}"]["is_deleted"] is False
    # And the real owner still has access.
    assert client.get(docs_url(b["id"], f"/{victim}/download"), headers=bearer("bob")).content == b"private plans"


def test_tampered_metadata_cannot_point_at_another_tenants_file(client, fake_db, fake_storage, make_business):
    a, b = make_business("alice", name="A"), make_business("bob", name="B")
    victim = upload(client, b["id"], "bob", "secret.txt", b"private plans").json()["document_id"]
    mine = upload(client, a["id"], "alice").json()["document_id"]
    fake_db.docs[f"businesses/{a['id']}/documents/{mine}"]["storage_path"] = \
        f"businesses/{b['id']}/knowledge/{victim}/original.txt"
    assert client.get(docs_url(a["id"], f"/{mine}/download"), headers=bearer("alice")).status_code == 404


def test_unauthenticated_requests_are_rejected(client):
    for method, suffix in (("get", ""), ("post", ""), ("get", "/x"), ("get", "/x/download"),
                           ("delete", "/x"), ("post", "/x/retry")):
        assert getattr(client, method)(docs_url("abc", suffix)).status_code == 401, (method, suffix)


# ---------------------------------------------------------------- validation

@pytest.mark.parametrize("filename,data,ctype,status,code", [
    ("virus.exe", b"MZ\x90\x00", "application/octet-stream", 415, "unsupported_file_type"),
    ("pic.png", b"\x89PNG\r\n", "image/png", 415, "unsupported_file_type"),
    ("noextension", b"hello", "text/plain", 415, "unsupported_file_type"),
    (".pdf", b"%PDF-1.4", "application/pdf", 415, "unsupported_file_type"),
    ("notes.txt", b"hello", "application/pdf", 415, "unsupported_file_type"),          # MIME mismatch
    ("notes.txt", b"hello", "application/octet-stream", 415, "unsupported_file_type"),
    ("fake.pdf", b"MZ\x90\x00 this is an executable", "application/pdf", 422, "invalid_file"),  # bad bytes
    ("fake.docx", b"just text", DOCX_MIME, 422, "invalid_file"),
    ("fake.docx", make_pdf(), DOCX_MIME, 422, "invalid_file"),
    ("bin.txt", b"abc\x00\x01\x02def", "text/plain", 422, "invalid_file"),
    ("empty.txt", b"", "text/plain", 422, "invalid_file"),
])
def test_invalid_uploads_are_rejected_and_nothing_is_stored(
        client, fake_db, fake_storage, make_business, filename, data, ctype, status, code):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", filename, data, ctype)
    assert r.status_code == status and r.json()["error"]["code"] == code, r.text
    assert fake_storage.objects == {}
    assert not [p for p in fake_db.docs if "/documents/" in p]


def test_oversized_file_is_rejected(client, fake_storage, make_business):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", "big.txt", b"a" * 300_000)  # limit in tests: 200,000
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    assert fake_storage.objects == {}
    # A file exactly at the limit is fine.
    assert upload(client, biz["id"], "alice", "ok.txt", b"a" * 200_000).status_code == 201


def test_huge_request_is_rejected_before_parsing(client, fake_storage, make_business):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", "huge.txt", b"a" * 2_000_000)  # Content-Length guard
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    assert fake_storage.objects == {}


def test_missing_file_field_is_a_validation_error(client, make_business):
    biz = make_business("alice")
    r = client.post(docs_url(biz["id"]), data={"x": "y"}, headers=bearer("alice"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_unsafe_filenames_are_sanitized(client, fake_storage, make_business):
    biz = make_business("alice")
    d1 = upload(client, biz["id"], "alice", "../../etc/passwd.txt").json()
    assert d1["filename"] == "passwd.txt" and d1["original_filename"] == "passwd.txt"
    d2 = upload(client, biz["id"], "alice", 'we<>ird:name?*.report.TXT').json()
    assert d2["filename"] == "we_ird_name_report.txt"
    d3 = upload(client, biz["id"], "alice", "C:\\Users\\bob\\menu.txt").json()
    assert d3["filename"] == "menu.txt"
    for p in fake_storage.objects:   # storage keys never contain user-supplied names
        assert p.endswith(("/original.txt", "/extracted.txt")) and ".." not in p


def test_client_supplied_ownership_fields_are_ignored(client, fake_db, make_business):
    biz, other = make_business("alice"), make_business("bob")
    r = client.post(docs_url(biz["id"]), files={"file": ("a.txt", b"hi", "text/plain")},
                    data={"business_id": other["id"], "uploaded_by": "bob-uid", "status": "processed"},
                    headers=bearer("alice"))
    assert r.status_code == 201
    doc = r.json()
    assert doc["business_id"] == biz["id"] and doc["uploaded_by"] == "alice-uid"
    assert [p for p in fake_db.docs if p.startswith(f"businesses/{other['id']}/documents/")] == []


# ---------------------------------------------------------------- processing failures + retry

def test_corrupted_pdf_is_recorded_as_failed(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice", "bad.pdf", b"%PDF-1.4\ngarbage that is not a pdf", "application/pdf")
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "failed" and "corrupted" in doc["processing_error"].lower()
    assert doc["extracted_character_count"] is None
    assert not any(p.endswith("extracted.txt") for p in fake_storage.objects)
    assert fake_db.docs[f"businesses/{biz['id']}/documents/{doc['document_id']}"]["extracted_text_path"] is None


def test_other_extraction_failures_have_clear_user_safe_messages(client, make_business):
    biz = make_business("alice")
    blank = upload(client, biz["id"], "alice", "scan.pdf", make_blank_pdf(), "application/pdf").json()
    assert blank["status"] == "failed" and "scanned" in blank["processing_error"].lower()
    broken = upload(client, biz["id"], "alice", "broken.docx", make_broken_docx(), DOCX_MIME).json()
    assert broken["status"] == "failed" and "docx" in broken["processing_error"].lower()
    ws = upload(client, biz["id"], "alice", "ws.txt", b"   \n \n ").json()
    assert ws["status"] == "failed" and "no readable text" in ws["processing_error"].lower()
    for d in (blank, broken, ws):   # no library internals / stack traces / paths leak
        text = d["processing_error"].lower()
        assert "traceback" not in text and "businesses/" not in text and "exception" not in text


def test_storage_error_during_processing_then_successful_retry(client, fake_storage, make_business):
    biz = make_business("alice")
    fake_storage.fail_download = True
    doc = upload(client, biz["id"], "alice").json()
    assert doc["status"] == "failed" and "storage" in doc["processing_error"].lower()

    fake_storage.fail_download = False
    r = client.post(docs_url(biz["id"], f"/{doc['document_id']}/retry"), headers=bearer("alice"))
    assert r.status_code == 200 and r.json()["status"] == "processed"
    assert r.json()["processing_error"] is None and r.json()["extracted_character_count"] > 0


def test_retry_rules(client, fake_db, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    url = docs_url(biz["id"], f"/{did}/retry")
    r = client.post(url, headers=bearer("alice"))                       # already processed
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_processed"

    path = f"businesses/{biz['id']}/documents/{did}"
    from datetime import datetime, timedelta, timezone
    fake_db.docs[path].update(status="processing", updated_at=datetime.now(timezone.utc))
    r = client.post(url, headers=bearer("alice"))                       # actively processing
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_processing"

    fake_db.docs[path]["updated_at"] = datetime.now(timezone.utc) - timedelta(minutes=30)
    r = client.post(url, headers=bearer("alice"))                       # stuck: safe to retry
    assert r.status_code == 200 and r.json()["status"] == "processed"


def test_upload_survives_storage_outage_without_creating_metadata(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    fake_storage.fail_upload = True
    r = upload(client, biz["id"], "alice")
    assert r.status_code == 502 and r.json()["error"]["code"] == "storage_error"
    assert "bucket" not in r.text.lower() and "businesses/" not in r.text
    assert not [p for p in fake_db.docs if "/documents/" in p]


def test_document_deleted_while_processing_leaves_no_orphan(client, fake_db, fake_storage, make_business):
    from app.services import document_processing
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    path = f"businesses/{biz['id']}/documents/{did}"
    fake_storage.delete(f"businesses/{biz['id']}/knowledge/{did}/extracted.txt")
    fake_db.docs[path].update(status="failed", extracted_text_path=None)
    fake_storage.after_download = lambda: fake_db.docs[path].update(is_deleted=True)  # delete mid-flight
    document_processing.process_document(fake_db, fake_storage, biz["id"], did)
    assert not any(p.endswith("extracted.txt") for p in fake_storage.objects)


def test_storage_not_configured_returns_503(client, make_business):
    from app.dependencies.storage import get_storage
    client.app.dependency_overrides.pop(get_storage)   # test settings contain no R2 credentials
    biz = make_business("alice")
    r = upload(client, biz["id"], "alice")
    assert r.status_code == 503 and r.json()["error"]["code"] == "storage_not_configured"
    assert client.get(docs_url(biz["id"]), headers=bearer("alice")).status_code == 200  # metadata still works
    assert client.post(f"/api/v1/businesses/{biz['id']}/knowledge", headers=bearer("alice"),
                       json={"title": "t", "category": "c", "content": "x"}).status_code == 201


# ---------------------------------------------------------------- download

def test_download_returns_original_bytes_with_safe_headers(client, make_business):
    biz = make_business("alice")
    pdf = make_pdf("hello")
    did = upload(client, biz["id"], "alice", "Menü Spring.pdf", pdf, "application/pdf").json()["document_id"]
    r = client.get(docs_url(biz["id"], f"/{did}/download"), headers=bearer("alice"))
    assert r.status_code == 200 and r.content == pdf
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert r.headers["x-content-type-options"] == "nosniff" and "no-store" in r.headers["cache-control"]


def test_download_when_file_missing_or_storage_down(client, fake_storage, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    url = docs_url(biz["id"], f"/{did}/download")
    fake_storage.fail_download = True
    r = client.get(url, headers=bearer("alice"))
    assert r.status_code == 502 and r.json()["error"]["code"] == "storage_error"
    fake_storage.fail_download = False
    fake_storage.objects.clear()
    r = client.get(url, headers=bearer("alice"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "file_not_found"


# ---------------------------------------------------------------- delete

def test_deleted_documents_are_gone_everywhere(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    keep = upload(client, biz["id"], "alice", "keep.txt").json()["document_id"]

    r = client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("alice"))
    assert r.status_code == 204 and r.content == b""
    assert fake_storage.paths(f"businesses/{biz['id']}/knowledge/{did}") == []   # both objects removed
    assert fake_storage.paths(f"businesses/{biz['id']}/knowledge/{keep}") != []

    stored = fake_db.docs[f"businesses/{biz['id']}/documents/{did}"]
    assert stored["is_deleted"] is True and stored["storage_path"] is None
    assert stored["extracted_text_path"] is None and stored["deleted_by"] == "alice-uid"

    for method, suffix in (("get", f"/{did}"), ("get", f"/{did}/download"), ("delete", f"/{did}"),
                           ("post", f"/{did}/retry")):
        assert getattr(client, method)(docs_url(biz["id"], suffix), headers=bearer("alice")).status_code == 404
    assert [d["document_id"] for d in client.get(docs_url(biz["id"]), headers=bearer("alice")).json()["items"]] == [keep]


def test_delete_storage_failure_hides_document_and_can_be_repeated(client, fake_db, fake_storage, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    fake_storage.fail_delete = True
    r = client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("alice"))
    assert r.status_code == 502
    # Already inaccessible even though cleanup failed...
    assert client.get(docs_url(biz["id"], f"/{did}/download"), headers=bearer("alice")).status_code == 404
    assert client.get(docs_url(biz["id"]), headers=bearer("alice")).json()["items"] == []
    # ...and the same call finishes the cleanup once storage recovers.
    fake_storage.fail_delete = False
    assert client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("alice")).status_code == 204
    assert fake_storage.objects == {}
    assert client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("alice")).status_code == 404


def test_unknown_and_malformed_document_ids(client, make_business):
    biz = make_business("alice")
    for bad in ("doesnotexist1234567890", "__bad__", "a.b"):
        for method, suffix in (("get", f"/{bad}"), ("delete", f"/{bad}"), ("get", f"/{bad}/download"),
                               ("post", f"/{bad}/retry")):
            r = getattr(client, method)(docs_url(biz["id"], suffix), headers=bearer("alice"))
            assert r.status_code == 404 and r.json()["error"]["code"] == "document_not_found"


# ---------------------------------------------------------------- listing / pagination / archived

def test_pagination_covers_every_document_once(client, make_business):
    biz = make_business("alice")
    ids = [upload(client, biz["id"], "alice", f"f{i}.txt").json()["document_id"] for i in range(5)]
    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = client.get(docs_url(biz["id"]), params=params, headers=bearer("alice")).json()
        seen += [d["document_id"] for d in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert pages == 3 and sorted(seen) == sorted(ids) and len(set(seen)) == 5
    assert seen == ids[::-1]   # newest first


def test_invalid_cursor_and_limit(client, make_business):
    biz = make_business("alice")
    for cursor in ("nope", "__x__", "a" * 20):
        r = client.get(docs_url(biz["id"]), params={"cursor": cursor}, headers=bearer("alice"))
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_cursor"
    assert client.get(docs_url(biz["id"]), params={"limit": 0}, headers=bearer("alice")).status_code == 422
    assert client.get(docs_url(biz["id"]), params={"limit": 101}, headers=bearer("alice")).status_code == 422


def test_cursor_from_another_business_does_not_leak(client, make_business):
    a, b = make_business("alice", name="A"), make_business("bob", name="B")
    foreign = upload(client, b["id"], "bob").json()["document_id"]
    upload(client, a["id"], "alice")
    r = client.get(docs_url(a["id"]), params={"cursor": foreign}, headers=bearer("alice"))
    assert r.status_code == 422


def test_archived_business_is_read_only(client, fake_db, make_business):
    biz = make_business("alice")
    did = upload(client, biz["id"], "alice").json()["document_id"]
    client.delete(f"/api/v1/businesses/{biz['id']}", headers=bearer("alice"))
    for r in (upload(client, biz["id"], "alice"),
              client.delete(docs_url(biz["id"], f"/{did}"), headers=bearer("alice")),
              client.post(docs_url(biz["id"], f"/{did}/retry"), headers=bearer("alice"))):
        assert r.status_code == 409 and r.json()["error"]["code"] == "business_archived"
    assert client.get(docs_url(biz["id"], f"/{did}"), headers=bearer("alice")).status_code == 200
    assert client.get(docs_url(biz["id"], f"/{did}/download"), headers=bearer("alice")).status_code == 200

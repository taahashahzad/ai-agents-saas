# AI Agent SaaS - Backend

FastAPI + Firebase Admin SDK + Cloud Firestore. Backend only; the React frontend lives elsewhere.
Phase 2 added memberships, invitations and RBAC. **Phase 3 adds the Business Knowledge Base**
(document upload to **Cloudflare R2**, text extraction, structured knowledge entries). Phase 4 adds
business-scoped OpenAI embeddings, Qdrant retrieval, indexing status/actions, and an authenticated RAG query.
Phase 5 adds business-scoped agent configuration, a LangGraph runtime, and persistent playground conversations.

## Architecture

```
backend/
  app/
    main.py                  App factory: CORS, error handlers, routers
    core/
      config.py              Env-based settings
      firebase.py            Firebase Admin init, Firestore client
      security.py            ID-token verification -> AuthenticatedUser (+ platform_role claim)
      permissions.py         RBAC: roles -> permissions matrix (single source of truth)
      transactions.py        Firestore transaction helper
      r2.py                  boto3 client for Cloudflare R2 (S3-compatible endpoint)
      storage.py             R2Storage service: upload/download/delete, errors translated
      limits.py              Upload size guard (Content-Length) middleware
      emails.py              Email normalization
      errors.py              AppError types + handlers (one JSON error shape)
    dependencies/
      auth.py                get_current_user, get_invitee, require_platform_admin
      business.py            get_business_membership, require_permission, require_business_role
      db.py  settings.py  storage.py
    api/routes/              health, users, businesses, members, invitations, documents, knowledge, rag, agents, conversations
    services/                business, membership, invitation, user services plus:
                             document_service      upload/list/get/download/delete/retry
                             document_processing   pipeline: Storage -> text -> Storage -> status
                             text_extraction       PDF/DOCX/TXT/CSV -> clean text (pure functions)
                             file_validation       filename, MIME, size, real-content checks
                             knowledge_service     structured knowledge entries
                             rag_service           chunking, OpenAI, tenant-filtered Qdrant search
                             rag_indexing          document/entry indexing status and vector sync
                             agent_service         business-scoped agent configuration and lifecycle
                             agent_orchestrator    simple LangGraph validate/retrieve/answer flow
                             conversation_service  bounded conversation history and message persistence
                             guards                archived-business check
    schemas/                 Pydantic models: user, business, member, invitation, document, knowledge
  scripts/
    set_system_admin.py      Grant/revoke the platform role (server-side only)
    backfill_phase2.py       One-off data migration (dry-run by default)
  tests/                     pytest suite + in-memory Firestore fake (tests only)
  docs/FRONTEND_API_CONTRACT.md     <- give this to the frontend developer
  firestore.rules  firestore.indexes.json  firebase.json
```

Layering: **routes -> dependencies (authn/authz) -> services -> Firestore**.

### How a business request is authorized

1. `get_current_user` verifies the Firebase ID token -> UID (never from the body).
2. `get_business_membership` reads `businesses/{id}/members/{uid}`. No membership -> **404**
   (identical to "business does not exist", so IDs can't be probed).
3. `require_permission(Permission.X)` checks the member's role against `core/permissions.py`
   -> **403** if the role lacks the permission.
4. Member mutations (role change, removal, invitations, accept) re-check the actor's role
   **inside a Firestore transaction**.

New business-scoped features (documents, agents, conversations, integrations, billing...) should use
`/businesses/{business_id}/...` plus `Depends(require_permission(Permission.DOCUMENTS_MANAGE))` etc.
The permissions already exist in the matrix.

### Roles and permissions

Platform role `system_admin` (Firebase custom claim) is separate from business roles and grants **no
business access**: a System Admin is not a member of any business unless added like anyone else.

| Capability | owner | admin | member |
|---|:-:|:-:|:-:|
| View business | yes | yes | yes |
| Edit name / description | yes | yes | - |
| Change business_type (owner-controlled setting) | yes | - | - |
| Archive business | yes | - | - |
| View members and invitations | yes | yes | - |
| Invite | admin, member | member | - |
| Remove members | admin, member | member | - |
| Change roles (member <-> admin) | yes | - | - |
| View / download knowledge-base documents | yes | yes | yes |
| Upload / delete / retry documents | yes | yes | - |
| View structured knowledge entries | yes | yes | yes |
| Create / edit / delete knowledge entries | yes | yes | - |
| AI agents / integrations (reserved) | yes | yes | - |
| Billing (reserved) | yes | - | - |

The owner can never be removed, demoted or invited. Ownership transfer is **not** implemented.

## Firebase setup

1. Create a project at <https://console.firebase.google.com>; enable Authentication and Firestore (production mode).
2. Project settings -> Service accounts -> Generate new private key -> save as
   `backend/secrets/firebase-service-account.json` (git-ignored; never commit or share it).
3. Deploy rules and **indexes** (Phase 2 adds indexes):
   ```bash
   firebase use <your-project-id>
   firebase deploy --only firestore:rules,firestore:indexes
   ```
   Wait until the indexes show **Enabled** in Firestore -> Indexes (a few minutes).
4. In production leave `FIREBASE_CREDENTIALS_PATH` empty and use the runtime's service account.

Collections are created automatically on first write; you never create them by hand.

### Required Firestore indexes (`firestore.indexes.json`)

All are single-field collection-group exemptions (no composite indexes):

| Collection group | Field | Used by |
|---|---|---|
| `members` | `uid` | `GET /businesses` (businesses I belong to) |
| `invitations` | `email` | `GET /invitations` (my invitations) |
| `invitations` | `invitation_id` | accept / decline lookup |

Missing index -> Firestore returns "requires an index" with a creation link.

### Firestore security rules

Unchanged: deny-all for clients. Only this backend (Admin SDK, bypasses rules) reads/writes data.

## Phase 3: Knowledge Base

**Firebase is used for Authentication and Firestore only. Cloudflare R2 is used exclusively for files.**
There is no Firebase Storage anywhere in this project.

### Design decisions

| Topic | Decision |
|---|---|
| Authorization | Reuses the Phase 2 dependencies: `require_permission(Permission.DOCUMENTS_VIEW / DOCUMENTS_MANAGE / KNOWLEDGE_VIEW / KNOWLEDGE_MANAGE)`. The new permissions live in the one matrix in `core/permissions.py`. |
| Tenant isolation | Every Firestore path and object key is built from the membership-verified `business_id`. Every Qdrant query applies the same verified ID as a mandatory payload filter. A document/entry ID from another business cannot resolve (404). |
| R2 access | `core/r2.py` builds one cached boto3 S3 client (endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, region `auto`, SigV4, retries + timeouts). `core/storage.py` (`R2Storage`) is the only code that calls it. Routes never touch boto3. |
| Private bucket | Credentials exist only in server env vars. Files are never public and no object URL is ever returned or stored. |
| Download | Streamed through FastAPI after the membership + role check (no presigned URLs). Presigned GET/PUT can be added later inside `R2Storage` without touching routes or services. |
| Validation | Extension must be pdf/docx/txt/csv; declared MIME must match; size limit enforced twice (Content-Length guard + while reading); real content checked (PDF header, DOCX structure + zip-bomb guard, text decodes with no NUL bytes). Filenames sanitized. |
| Processing | `document_processing.process_document()` runs synchronously inside the upload request but has no HTTP dependency, so a queue worker can call it later. Claiming a document is a Firestore transaction. |
| Failures | An unreadable document is still stored with `status=failed` and a user-safe `processing_error`; upload returns 201. Library errors, keys and credentials are never returned. |
| Delete | Soft: Firestore metadata is marked `is_deleted=true` first (access stops at once), then both R2 objects are deleted, then the paths are cleared. If R2 fails the call returns 502 and the same request can be repeated to finish. |
| Logging | Only S3 error codes are logged. boto3/botocore/urllib3 loggers are held at WARNING even if `LOG_LEVEL=DEBUG`, because at DEBUG they log object keys and request parameters (which can include file contents). |

### How Firestore metadata relates to R2 objects

```
Firestore: businesses/{business_id}/documents/{document_id}          R2 bucket (private)
   document_id, business_id, filename, original_filename, ...         ------------------------------------
   storage_path ----------------------------------------------------> businesses/{business_id}/knowledge/{document_id}/original.<ext>
   extracted_text_path ---------------------------------------------> businesses/{business_id}/knowledge/{document_id}/extracted.txt
   status: uploaded -> processing -> processed | failed
   extracted_character_count, processing_error, is_deleted ...
Firestore: businesses/{business_id}/knowledge_entries/{entry_id}     (plain Firestore, no R2 object)
```

- Firestore is the source of truth for *which* documents exist and their status; R2 only holds the bytes.
- Object keys are generated by the server from IDs (never from user input or file names) and are stored as
  `storage_path` / `extracted_text_path`. They are never returned by the API.
- Upload order: R2 upload of the original -> Firestore metadata -> extract -> R2 upload of `extracted.txt` -> status update.
  If the Firestore write fails the original is deleted again; if extraction fails the status becomes `failed`.
- Delete order: hide in Firestore -> delete both R2 objects -> clear the paths (repeatable if R2 fails halfway).
- Extracted text is never stored in Firestore (document size limit).

### Phase 4 retrieval and indexing

- Extracted document text stays in private R2; structured knowledge stays in Firestore. Chunk text and
  embeddings are stored in the shared Qdrant collection with business/source metadata.
- Upload and successful extraction automatically index when OpenAI and Qdrant are configured.
  Structured knowledge create/edit synchronizes its vectors. The document and entry APIs expose
  independent indexing state; managers can retry/reindex explicitly.
- Deletion removes the corresponding vectors before deleting the source record. Reindexing replaces
  the source's old points so an unsuccessful reindex does not leave outdated vectors available.
- The RAG query requires the business knowledge-view permission and filters Qdrant results by the
  verified business ID before sending source excerpts to the answer model. Source passages are
  explicitly treated as untrusted data.
- Configure `OPENAI_API_KEY` and `QDRANT_URL` to enable RAG. Without them, the existing knowledge
  base still works; vector indexing/query routes report that RAG is not configured.
- Full API contract and setup details: [`docs/FRONTEND_API_CONTRACT.md`](./docs/FRONTEND_API_CONTRACT.md).

### Cloudflare R2 setup

1. **Create/enable R2.** Cloudflare dashboard -> **Storage & databases -> R2 object storage**. R2 has a free monthly
   allowance, but you may have to add a payment method to enable it (see Cloudflare's R2 pricing page). Cloudflare
   requires R2 to be enabled before you can create API tokens.
2. **Create the bucket.** *Create bucket* -> choose a name (e.g. `ai-agents-knowledge`) and keep the defaults.
   **Do not** enable the public `r2.dev` URL and **do not** attach a custom domain: the bucket must stay private.
3. **Find your Account ID and endpoint.** On the R2 *Overview* page (Account details). The S3 endpoint is
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
4. **Create API credentials.** R2 *Overview* -> **API Tokens -> Manage** -> **Create Account API token**
   (or *User API token*) -> permission **Object Read & Write** -> **Apply to specific buckets only** -> select your
   bucket -> **Create**. Copy the **Access Key ID** and **Secret Access Key** immediately: the secret is shown only once.
   (Use the *S3 Access Key ID / Secret Access Key* pair, not the token value.)
5. **Put the values in `backend/.env`** (git-ignored; copy `.env.example` first):
   ```env
   R2_ACCOUNT_ID=<your account id>
   R2_ACCESS_KEY_ID=<access key id>
   R2_SECRET_ACCESS_KEY=<secret access key>
   R2_BUCKET_NAME=<bucket name>
   R2_ENDPOINT_URL=https://<your account id>.r2.cloudflarestorage.com
   R2_REGION=auto
   ```
   `R2_ENDPOINT_URL` may be left empty; it is then built from `R2_ACCOUNT_ID`. Restart the server after editing `.env`.
   In production set these as environment variables / secrets of your host instead of a file.
6. **Rotate** the token in the dashboard if a secret is ever exposed.

If R2 is not configured, only the file endpoints (upload/download/delete/retry) answer `503 storage_not_configured`;
everything else keeps working.

### Test uploads and downloads manually

You need a Firebase ID token for a user who is owner/admin of a business (see Firebase setup) and a `business_id`
from `POST /api/v1/businesses`. On Windows PowerShell use `curl.exe` (plain `curl` is a different command).

```bash
# upload (multipart field must be named "file")
curl -X POST http://localhost:8000/api/v1/businesses/BUSINESS_ID/documents \
  -H "Authorization: Bearer ID_TOKEN" -F "file=@menu.pdf;type=application/pdf"
# -> 201 {"document_id": "...", "status": "processed", ...}

# download the original
curl -H "Authorization: Bearer ID_TOKEN" -o downloaded.pdf \
  http://localhost:8000/api/v1/businesses/BUSINESS_ID/documents/DOCUMENT_ID/download

# delete
curl -X DELETE -H "Authorization: Bearer ID_TOKEN" \
  http://localhost:8000/api/v1/businesses/BUSINESS_ID/documents/DOCUMENT_ID
```
Then check in the Cloudflare dashboard (R2 -> your bucket -> Objects) that
`businesses/<business_id>/knowledge/<document_id>/original.pdf` and `extracted.txt` appeared after the upload and
disappeared after the delete, and that the document appears/disappears in Firestore
(`businesses/<id>/documents/<document_id>`). To confirm the bucket is private, open an object's URL in a browser:
it must be denied.

### Firestore structure

```
businesses/{business_id}/documents/{document_id}
    document_id, business_id, filename, original_filename, file_type, mime_type, file_size,
    storage_path, uploaded_by, uploaded_at, updated_at, status, processing_error,
    extracted_text_path, extracted_character_count, is_deleted (+ deleted_at, deleted_by)
businesses/{business_id}/knowledge_entries/{entry_id}
    entry_id, business_id, title, category, content, created_by, created_at, updated_at
businesses/{business_id}/agents/{agent_id}
    agent_id, business_id, name, instructions, personality, greeting, language, model, status, ...
businesses/{business_id}/conversations/{conversation_id}
    conversation_id, business_id, agent_id, status, created_at, updated_at, last_message_preview
businesses/{business_id}/conversations/{conversation_id}/messages/{message_id}
    message_id, conversation_id, role, content, sources, created_at
```
Collections are created automatically on first write. `firestore.rules` stays deny-all (the backend uses the Admin SDK).
Agent and conversation records are business-scoped. Conversation history is bounded when sent to the model;
only the fixed, permission-checked business-knowledge search tool is available to agents.

### Required Firestore indexes

| Collection | Fields | Used by |
|---|---|---|
| `documents` | `is_deleted` ASC, `uploaded_at` DESC | list documents |
| `knowledge_entries` | `category` ASC, `created_at` DESC | list entries filtered by category |

Both are in `firestore.indexes.json`: `firebase deploy --only firestore:indexes`, then wait until they show **Enabled**.

### New dependencies and environment variables

`pip install -r requirements.txt` (adds `python-multipart`, `pypdf`, `python-docx`, `boto3`,
`openai`, `qdrant-client`, `langchain-text-splitters`, and `langgraph`).

| Variable | Default | Purpose |
|---|---|---|
| `R2_ACCOUNT_ID` | (none) | Used to build the endpoint if `R2_ENDPOINT_URL` is empty |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | (none) | R2 S3 credentials (server-side only) |
| `R2_BUCKET_NAME` | (none) | Private bucket for all knowledge-base files |
| `R2_ENDPOINT_URL` | derived | Must start with `https://` (the app refuses to start otherwise) |
| `R2_REGION` | `auto` | Always `auto` for R2 |
| `MAX_UPLOAD_MB` | `10` | Max upload size, clamped to 1-50 MB |
| `OPENAI_API_KEY` | (none) | Backend-only; enables RAG embeddings and answers |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | `text-embedding-3-small` or `text-embedding-3-large`, 1536 dimensions |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | RAG answer generation model |
| `QDRANT_URL` | (none) | Backend-only Qdrant endpoint; enables RAG |
| `QDRANT_API_KEY` | (none) | Optional local, recommended for hosted Qdrant |
| `QDRANT_COLLECTION` | `business_knowledge` | Shared vector collection |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `1000` / `150` | Text chunking parameters |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | `5` / `0.2` | Retrieval count (1-20) and similarity cutoff |

### API summary

Full request/response details and examples: **`docs/FRONTEND_API_CONTRACT.md`**.

| Method | Path | Success | Who |
|---|---|---|---|
| GET | `/businesses/{id}/documents` | 200 `{items, next_cursor}` | owner, admin, member |
| POST | `/businesses/{id}/documents` (multipart `file`) | 201 Document | owner, admin |
| GET | `/businesses/{id}/documents/{document_id}` | 200 Document | owner, admin, member |
| GET | `/businesses/{id}/documents/{document_id}/download` | 200 file bytes | owner, admin, member |
| DELETE | `/businesses/{id}/documents/{document_id}` | 204 | owner, admin |
| POST | `/businesses/{id}/documents/{document_id}/retry` | 200 Document | owner, admin |
| POST | `/businesses/{id}/documents/{document_id}/index` | 200 Document | owner, admin |
| POST | `/businesses/{id}/documents/{document_id}/reindex` | 200 Document | owner, admin |
| GET | `/businesses/{id}/documents/{document_id}/index-status` | 200 Document | owner, admin, member |
| GET | `/businesses/{id}/knowledge` | 200 `{items, next_cursor}` | owner, admin, member |
| POST | `/businesses/{id}/knowledge` | 201 Entry | owner, admin |
| PATCH | `/businesses/{id}/knowledge/{entry_id}` | 200 Entry | owner, admin |
| POST | `/businesses/{id}/knowledge/{entry_id}/index` | 200 Entry | owner, admin |
| DELETE | `/businesses/{id}/knowledge/{entry_id}` | 204 | owner, admin |
| POST | `/businesses/{id}/rag/query` | 200 Answer and sources | owner, admin, member |
| POST | `/businesses/{id}/agents` | 201 Agent | owner, admin |
| GET | `/businesses/{id}/agents` | 200 Agent[] | owner, admin |
| GET | `/businesses/{id}/agents/{agent_id}` | 200 Agent | owner, admin |
| PATCH | `/businesses/{id}/agents/{agent_id}` | 200 Agent | owner, admin |
| PATCH | `/businesses/{id}/agents/{agent_id}/status` | 200 Agent | owner, admin |
| DELETE | `/businesses/{id}/agents/{agent_id}` | 204, deletes attached conversations/messages | owner, admin |
| POST | `/businesses/{id}/agents/{agent_id}/chat` | 200 Chat turn and sources | owner, admin |
| GET | `/businesses/{id}/agents/{agent_id}/conversations` | 200 Conversation[] | owner, admin |
| GET | `/businesses/{id}/conversations/{conversation_id}` | 200 Conversation and messages | owner, admin |
| DELETE | `/businesses/{id}/conversations/{conversation_id}` | 204 | owner, admin |

### Phase 3/4 errors

413 `file_too_large`, 415 `unsupported_file_type`, 422 `invalid_file` / `invalid_cursor`, 404 `document_not_found` /
`file_not_found` / `entry_not_found`, 409 `already_processed` / `already_processing`, 502 `storage_error`,
503 `storage_not_configured` / `rag_not_configured` / `rag_unavailable`.

### Tests

The pytest suite is in `tests/`; RAG-specific unit and authorization coverage is in
`tests/test_rag_service.py` and `tests/test_rag_api.py`. Provider calls are mocked; tests do not contact
OpenAI or Qdrant.
Extraction tests use real PDF/DOCX bytes. The R2 layer is tested with real boto3 clients whose HTTP layer is stubbed
(`botocore.stub`): exact S3 calls, error mapping, no secrets in logs, and the real signed request (path-style URL,
region `auto`, no checksum headers). API tests use an in-memory storage fake, plus one end-to-end test through the real
`R2Storage` class. Nothing in the test suite contacts Cloudflare or Firebase.

### Phase 3 limitations

- Processing runs inside the upload request (fine for <= 10 MB). Move `process_document` to a queue before raising the limit.
- Scanned/image-only PDFs are not supported (no OCR) and are marked `failed` with an explanatory message.
- Legacy `.doc`/`.xls` and other formats are unsupported. Password-protected PDFs are marked `failed`.
- The Content-Length guard cannot see chunked uploads without that header; also limit request size at your proxy.

### RAG evaluation

`evaluation/restaurant_rag.json` contains a fictional five-source restaurant corpus and 20 questions.
With backend RAG settings configured, run `python scripts/evaluate_rag.py` from `backend/` to report
retrieval recall at configured top-k and the rate of answers containing all required reference terms.
The evaluation uses a unique synthetic business ID and removes its vectors when complete.
- Uploads/downloads pass through the API and are buffered in memory (fine at the size limit). Direct browser-to-R2
  presigned uploads are a possible later optimisation.
- No per-business document count/storage quota yet.
- The automated tests do not call the real R2 service; do one manual upload/download/delete after setup (see above).

## Local setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # then edit
uvicorn app.main:app --reload --port 8000
pytest
```

### Email verification and invitations (important)

Invitations are matched by email, so the token's email must be **verified** by Firebase; otherwise anyone
could sign up with someone else's address and accept their invitations. `REQUIRE_VERIFIED_EMAIL=true` is the
default. Firebase email/password users are **unverified** until you call `sendEmailVerification()` and
they click the link. For local testing before you build that step, set `REQUIRE_VERIFIED_EMAIL=false`
(never in production). Unverified users get `403 email_not_verified` on `/invitations` endpoints.

### Granting System Admin (server-side only)

```bash
python -m scripts.set_system_admin <firebase-uid>            # grant
python -m scripts.set_system_admin <firebase-uid> --revoke   # revoke
```
The user must refresh their ID token (sign out/in or `getIdToken(true)`). `GET /users/me` then returns
`"platform_role": "system_admin"`. There is no API to assign it.

### Migration / backfill (existing Phase 1 data)

Optional but recommended. Idempotent; dry-run by default:
```bash
python -m scripts.backfill_phase2            # preview
python -m scripts.backfill_phase2 --apply    # write
```
Adds `users.updated_at` and `members.email` where missing. The API works without it (members list falls back
to the users document for emails), but the "already a member" invitation check only sees members that have an
`email`. Phase 1 data needs no other change: existing `owner`/`member` roles are unchanged.

## API documentation

Base path `/api/v1`. All endpoints except `/health` need `Authorization: Bearer <Firebase ID token>`.

### Existing (Phase 1)

| Method | Path | Success | Who |
|---|---|---|---|
| GET | `/health` | 200 | public |
| GET | `/users/me` | 200 User (404 `profile_not_found` before first POST) | self |
| POST | `/users/me` | 201 created / 200 updated, User | self |
| POST | `/businesses` | 201 Business (caller becomes owner) | any user |
| GET | `/businesses` | 200 Business[] (active, where I'm a member) | any user |
| GET | `/businesses/{id}` | 200 Business | owner, admin, member |
| PATCH | `/businesses/{id}` | 200 Business | owner, admin (`business_type`: owner only) |
| DELETE | `/businesses/{id}` | 200 Business, `status:"archived"` (soft delete) | owner |

### New (Phase 2)

| Method | Path | Success | Who |
|---|---|---|---|
| GET | `/businesses/{id}/members` | 200 Member[] (owner, admin, member order) | owner, admin |
| PATCH | `/businesses/{id}/members/{uid}/role` | 200 Member | owner |
| DELETE | `/businesses/{id}/members/{uid}` | 204 | owner (admin/member targets), admin (member targets) |
| POST | `/businesses/{id}/invitations` | 201 Invitation | owner (admin/member), admin (member) |
| GET | `/businesses/{id}/invitations` | 200 Invitation[] (all statuses, newest first) | owner, admin |
| GET | `/invitations` | 200 Invitation[] (my pending, unexpired) | any verified user |
| POST | `/invitations/{invitation_id}/accept` | 200 Invitation (`accepted`) | invited email only |
| POST | `/invitations/{invitation_id}/decline` | 200 Invitation (`declined`) | invited email only |

**Schemas**

- **User**: `{ uid, email, display_name, platform_role, created_at, updated_at }` (`platform_role` is `"system_admin"` or `null`)
- **Business**: unchanged; `role` is now `owner | admin | member`
- **Member**: `{ uid, email, display_name, role, joined_at }`
- **MemberRoleUpdate** (PATCH body): `{ "role": "admin" | "member" }` (`"owner"` -> 400 `ownership_transfer_unsupported`)
- **InvitationCreate** (POST body): `{ "email": string, "role": "admin" | "member" }` (`role` defaults to `member`)
- **Invitation**: `{ invitation_id, business_id, business_name, email, role, invited_by, status, created_at, expires_at, accepted_at }`
  - `status`: `pending | accepted | declined | expired` (`expired` = pending past `expires_at`, computed on read)
  - `business_name` is filled on `/invitations` endpoints and the business-side list.

**Behavior notes**

- Emails are trimmed and lowercased before storing/matching.
- One invitation per (business, email). A duplicate pending one -> 409 `invitation_exists`; re-inviting after
  accept/decline/expiry replaces the old record. Invites expire after `INVITATION_TTL_DAYS` (default 7).
- Accepting never overwrites an existing membership (409 `already_member`).
- Someone else's invitation behaves exactly like a missing one (404 `invitation_not_found`).
- Archived businesses are read-only for members/invitations (409 `business_archived`).
- Invitation delivery by email is not implemented; the invitee sees it via `GET /invitations`.

**Errors**: always `{ "error": { "code", "message", "details"? } }`.

| Status | `code` |
|---|---|
| 400 | `ownership_transfer_unsupported` |
| 401 | `authentication_required`, `invalid_token`, `token_expired`, `token_revoked`, `user_disabled` |
| 403 | `forbidden`, `insufficient_role`, `cannot_modify_owner`, `email_not_verified`, `email_required`, `platform_admin_required` |
| 404 | `not_found`, `profile_not_found`, `member_not_found`, `invitation_not_found` |
| 409 | `business_archived`, `invitation_exists`, `already_member`, `invitation_expired`, `invitation_already_accepted`, `invitation_already_declined` |
| 422 | `validation_error` |
| 503 | `service_unavailable` |

## Tests

`pytest` runs without Firebase or network (Firebase is mocked; Firestore is an in-memory fake used only in tests).
Phase 2 coverage: `test_multitenancy_scenarios.py` (brief scenarios 1-8), `test_members.py` (9-11),
`test_invitations.py` (12-14), `test_permissions.py` (matrix + System Admin), `test_backfill.py`.

## Known limitations

- Ownership transfer, "leave business", and invitation revoke/resend are not implemented.
- Members cannot see the team list (least privilege). To allow it, add `P.MEMBERS_VIEW` to the member set in
  `core/permissions.py`.
- No email delivery for invitations.
- Business PATCH/DELETE check permissions and then write without a transaction (a role change landing in
  the same few milliseconds could let one in-flight edit through).
- The automated tests run the transactional code against a fake; the real Firestore transaction path should
  be smoke-tested once against a real project or the Firestore emulator.
- `GET /businesses` is not paginated.
- Phase 3 limitations are listed in the "Phase 3: Knowledge Base" section.

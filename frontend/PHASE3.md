# Phase 3 — Business Knowledge Base (frontend)

Frontend permissions are for user experience only. The backend is the security boundary and re-checks every action (403 for a member writing, 404 for a non-member, 409 `business_archived`).

## Storage architecture (Cloudflare R2 behind FastAPI)

Firebase Auth handles sign-in, Firestore holds metadata and Cloudflare R2 holds the files, but the frontend only ever talks to FastAPI:

- Uploads: `POST /businesses/{id}/documents` (multipart) through the shared Axios client.
- Downloads: `GET .../download` through the same client, saved from a blob. No R2 or public file URL is built or assumed.
- No Firebase Storage SDK is imported or initialized, `VITE_FIREBASE_STORAGE_BUCKET` is no longer used, and no R2 credentials exist in the frontend. The only `firebase/*` imports are `firebase/app` and `firebase/auth`.
- Metadata and statuses (`uploaded | processing | processed | failed`) are displayed exactly as the backend returns them.

## What was built

- **Route** `/knowledge` ("Knowledge Base" in the sidebar, visible to every role). Tabs: **Documents** and **Business Information** (`/knowledge?tab=info`).
- **Documents:** upload button + drag-and-drop (multiple files, uploaded one at a time), extension and size validation, per-file progress, table with name / type / size / date / uploaded by / status, actions menu (View details, Download original, Retry processing, Delete), delete confirmation, "Load more" pagination.
- **Business Information:** free-form entries (Title, Category, Content), card layout, category filter chips, add / view / edit / delete, delete confirmation. Categories are free text; the quick-pick suggestions vary by business type but nothing is required or hardcoded.
- **Roles:** everyone can view and download; owner and admin can upload, delete, retry and manage entries. Archived business = read-only for everyone.
- Loading skeletons, empty states ("Your Knowledge Base is empty. Upload documents or add business information to get started."), error alerts with Retry, success notices.

## How the important parts work

1. **Uploads (`src/api.js`, `services/documentService.js`).** The shared Axios client used to force `Content-Type: application/json` on every request. With that default, Axios serializes a `FormData` body as JSON, so uploads would fail. The default is removed (Axios still sets JSON automatically for object bodies), and `uploadDocument` sends a `FormData` with a single field named `file`; the browser then generates the multipart header with its boundary. `onUploadProgress` drives the progress bar. A ref guard plus a disabled dropzone prevent duplicate submissions.
2. **Downloads.** The bucket is private and the file is streamed through the API, so a plain link cannot send the token. The file is fetched as a blob through the same authenticated client, then saved with a temporary link. Error bodies arrive as blobs, so they are parsed back into JSON to show the real message.
3. **Tenant isolation.** Every request builds its URL from the active business id (never hardcoded, never sent in a body). `DashboardLayout` already remounts the page when the active business changes; the Knowledge Base children are also keyed by business id, and their cleanup aborts in-flight requests (`AbortController`) and any running upload. There is no global cache: all Knowledge Base state lives inside components for one business, and a request counter ignores late responses. Aborted requests are treated as cancellations, not errors.
4. **Errors (`utils/errors.js`).** Understands the contract shape `{ error: { code, message, details } }` and shows `message` (plus the first validation detail for 422). It also handles network failures, timeouts and non-JSON bodies, and never shows raw HTML or stack traces. Earlier error shapes still work.
5. **Permissions.** `getPermissions()` gained `manageKnowledge` (owner/admin). The role comes from `GET /businesses` via the existing `BusinessContext`; nothing is read from localStorage.

## Files

New: see the list in the chat message / zip. Edited: `src/api.js`, `src/App.jsx`, `src/components/Sidebar.jsx`, `src/services/endpoints.js`, `src/utils/errors.js`, `src/utils/permissions.js`, `.env.example`. If you changed any of these locally, apply `phase3-edits.diff` (it contains only the Phase 3 changes) instead of overwriting.

## Routes

Added: `/knowledge`. No existing route changed.

## API methods (all under `/api/v1`, all with `Authorization: Bearer <Firebase ID token>`)

| Method | Path | Function |
|---|---|---|
| GET | `/businesses/{id}/documents?limit&cursor` | `listDocuments` |
| POST | `/businesses/{id}/documents` (multipart, field `file`) | `uploadDocument` |
| GET | `/businesses/{id}/documents/{doc}` | `getDocument` |
| GET | `/businesses/{id}/documents/{doc}/download` (blob) | `downloadDocument` |
| DELETE | `/businesses/{id}/documents/{doc}` | `deleteDocument` |
| POST | `/businesses/{id}/documents/{doc}/retry` | `retryDocument` |
| GET | `/businesses/{id}/knowledge?limit&cursor` | `listEntries` |
| POST | `/businesses/{id}/knowledge` | `createEntry` |
| PATCH | `/businesses/{id}/knowledge/{entry}` | `updateEntry` (only changed fields) |
| DELETE | `/businesses/{id}/knowledge/{entry}` | `deleteEntry` |

## Environment

Optional new variable: `VITE_MAX_UPLOAD_MB` (default `10`). `.env.example` also now points `VITE_API_BASE_URL` at `http://127.0.0.1:8000` as in the contract; keep your own value in `.env`. No new dependencies.

## Run

```bash
npm install     # nothing new, but safe
npm run dev     # http://localhost:5173
npm run build
```

## Manual testing (needs the real backend and Firebase)

Use three accounts: A (owner), B (admin), C (member) of business 1; A also owns business 2.

1. **Owner:** open Knowledge Base. Upload a PDF by button and a TXT by drag-and-drop. Watch progress, then the status in the table (`Processed`, or `Failed` with the reason).
2. **Admin (B):** same upload and delete work.
3. **Member (C):** no upload button, no dropzone, no Add/Edit/Delete; a "view-only" notice is shown. Download and View details still work.
4. **Delete:** confirmation appears; the row disappears after confirming.
5. **Business Information:** add an entry, edit it, delete it. Member sees entries but no controls.
6. **Status/retry:** upload a scanned (image-only) PDF; it shows `Failed` with the OCR message and a Retry action.
7. **Download:** download a PDF and a CSV; open them.
8. **Failures:** upload a file over the limit, an `.exe`, an empty file, and with the backend stopped; each shows a readable message.
9. **Switching:** put different files in business 1 and 2; switch in the sidebar; only the selected business's data is shown, never the other's.
10. **URL manipulation:** the business is never taken from the URL. A user who is not a member gets 404 from the backend for any id.
11. **Regression:** login, signup, business create/edit/archive, team and invitations still work.

## Remaining integration points

- **Upload limit:** the backend does not expose `MAX_UPLOAD_MB`. Keep `VITE_MAX_UPLOAD_MB` equal to it (the server still enforces it with 413).
- **Uploaded by:** the API returns only a uid, so the UI shows "You" or "Team member". If the backend later adds a name, change `DocumentTable.jsx` and `DocumentDetailsModal.jsx`.
- **Archived flag:** the UI treats a business as archived when `GET /businesses` returns `archived: true` or `status: "archived"`. If it does not return that, writes simply fail with 409 `business_archived` and the message is shown.
- **CORS:** the backend must allow the frontend origin (`http://localhost:5173`), the methods GET, POST, PATCH, DELETE and the `Authorization` header.
- **System admin without membership:** per the contract a non-member gets 404, so such a user sees an error on this page.
- **Not exercised against the real backend or Firebase:** the checks were run against a local server that follows the contract.

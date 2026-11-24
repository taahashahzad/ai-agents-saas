# AI Agent Platform — Frontend

React + Vite + Tailwind CSS + Firebase Auth + Axios + React Router.
Frontend only. All business data goes through the backend REST API; React never touches Firestore business collections.

## Firebase setup

1. Open the [Firebase Console](https://console.firebase.google.com) and create (or choose) a project.
2. **Build > Authentication > Get started > Sign-in method**: enable **Email/Password**.
3. **Project settings > Your apps > Web (`</>`)**: register a web app and copy its config values.
4. **Authentication > Settings > Authorized domains**: make sure `localhost` is listed (it is by default).
5. Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | Backend origin, e.g. `http://localhost:8000` (no trailing slash, no `/api/v1`) |
| `VITE_FIREBASE_*` | Values from the Firebase web app config |

The backend must use the same Firebase project to verify ID tokens, and must allow CORS from `http://localhost:5173`.

## Local development

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build into dist/
npm run preview    # serve the production build locally
```

## Authentication flow

1. `onAuthStateChanged` (in `src/context/AuthContext.jsx`) runs once on load. Until it fires, `loading` is true and route guards show a spinner, which prevents a flash of the login page.
2. **Register**: `createUserWithEmailAndPassword` > set display name > force-refresh the ID token > `POST /api/v1/users/me` with `{ full_name, email }` to create/sync the backend profile > redirect to the dashboard.
3. **Login**: `signInWithEmailAndPassword`; `onAuthStateChanged` then loads the backend profile with `GET /api/v1/users/me` (best effort — the UI falls back to Firebase data if it fails).
4. **Logout**: `signOut`; the guard redirects to `/login`.
5. `ProtectedRoute` redirects unauthenticated users to `/login` (remembering where they were going). `PublicOnlyRoute` redirects signed-in users away from login/register.

## API integration

- `src/api.js` is the only Axios instance. `baseURL` = `VITE_API_BASE_URL`.
- A **request interceptor** calls `auth.currentUser.getIdToken()` (the SDK returns a cached token and refreshes it automatically when expired) and sets `Authorization: Bearer {token}` on every request.
- A **response interceptor** retries a 401 once with a force-refreshed token, then signs the user out if it still fails.
- `src/services/endpoints.js` holds every path. **Only `POST /api/v1/users/me` was specified; the rest are assumptions** and are marked as such in that file:

| Action | Endpoint |
|---|---|
| Sync profile | `POST /api/v1/users/me` |
| Get profile | `GET /api/v1/users/me` (assumed) |
| List businesses | `GET /api/v1/businesses` (assumed) |
| Create business | `POST /api/v1/businesses` (assumed) |
| Get business | `GET /api/v1/businesses/{id}` (assumed) |
| Update business | `PUT /api/v1/businesses/{id}` (assumed) |
| Archive business | `POST /api/v1/businesses/{id}/archive` (assumed) |

- `src/services/businessService.js` accepts a bare array or `{ items | businesses | data: [...] }` for lists, and unwraps `{ business | data }` for single objects. Business type is sent as lowercase `restaurant`, `clinic` or `school`.
- Errors are converted to readable messages by `src/utils/errors.js` (Firebase codes, FastAPI `detail`, `message`, network errors).

## Structure

```
src/
  api.js                 Axios instance + interceptors
  firebase.js            Firebase init
  App.jsx / main.jsx     Routes and app entry
  context/AuthContext    Auth state + register/login/logout
  hooks/                 useAuth, useBusinesses
  services/              endpoints, userService, businessService
  routes/                ProtectedRoute, PublicOnlyRoute
  layouts/               AuthLayout, DashboardLayout
  components/            UI primitives, Sidebar, Topbar, BusinessCard, BusinessForm
  pages/                 Login, Register, Dashboard, CreateBusiness, BusinessDetails, NotFound
  utils/                 validators, errors, constants
```

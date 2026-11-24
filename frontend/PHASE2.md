# Phase 2 — Multi-tenancy and RBAC (frontend)

Frontend permissions are for user experience only. The backend is the security boundary and must re-check every action.

## How it works

- `BusinessContext` loads `GET /api/v1/businesses` after sign-in. The role for each business comes from that response; roles are never stored locally and never assumed global. Only the selected business **ID** is remembered (per user, in localStorage) and is validated against the backend list on every load.
- `DashboardLayout` keys its content by the active business ID, so switching businesses remounts the current page and discards its state. Nothing from the previous business can be shown.
- `utils/permissions.js` is the single place that maps a role to UI permissions.
- `system_admin` is read from `GET /api/v1/users/me` (platform-level). A system admin with no membership in a business is shown as "System Admin" and gets the full management UI; the backend decides what actually works.

## Permission matrix (UI)

| Action | Owner | Admin | Member |
|---|---|---|---|
| See Team page / members / invitations | yes | yes | no |
| Invite | Admin or Member | Member only | no |
| Remove member | Admin or Member | Member only | no |
| Change role (Admin <-> Member) | yes | no | no |
| Edit business | yes | yes | no |
| Archive business | yes | no | no |
| Own role / Owner row changes | never | never | never |

## API endpoints used

| Method | Path | Used for |
|---|---|---|
| GET | `/api/v1/users/me` | profile, platform role |
| GET | `/api/v1/businesses` | memberships + role per business |
| GET | `/api/v1/businesses/{id}/members` | Team page |
| DELETE | `/api/v1/businesses/{id}/members/{uid}` | remove member |
| PATCH | `/api/v1/businesses/{id}/members/{uid}/role` | body `{ "role": "admin" \| "member" }` |
| GET | `/api/v1/businesses/{id}/invitations` | invitation list + status |
| POST | `/api/v1/businesses/{id}/invitations` | body `{ "email", "role" }` |
| GET | `/api/v1/invitations` | invitations addressed to me |
| POST | `/api/v1/invitations/{id}/accept` | accept |
| POST | `/api/v1/invitations/{id}/decline` | decline |

Plus the Phase 1 endpoints (create/get/update/archive business). All paths live in `src/services/endpoints.js`.

## Environment variables

No new variables.

## Backend dependencies to confirm (schemas not yet agreed)

1. `GET /api/v1/businesses` must return the caller's role on each business, as `role` (also accepted: `my_role`, `membership_role`, `membership.role`). Without it every business shows no role and management UI stays hidden.
2. `GET /api/v1/users/me` should expose the platform role (`is_system_admin: true`, or `role` / `platform_role` = `"system_admin"`).
3. Member objects: `uid`, `full_name` or `name`, `email`, `role`, `joined_at`.
4. Invitation objects: `id`, `email`, `role`, `status` (`pending` / `accepted` / `declined` / `expired`), `created_at`, optional `expires_at`; for `GET /invitations` also `business_id`, `business_name`, and an inviter name.
5. Error codes: 403 forbidden, 404 not found, 409 already member/invited, 410 or 400/422 for expired/invalid invitations. FastAPI `detail` strings and 422 `detail` arrays are shown to the user.
6. Accept must add the business to `GET /api/v1/businesses` for that user.

If any shape differs, adjust `normalizeMember` / `normalizeInvitation` in `src/services/memberService.js` or `getBusinessRole` / `isSystemAdmin` in `src/utils/permissions.js`.

## Manual testing (needs the real backend)

Use three accounts (A, B, C) and two businesses.

1. **Owner:** A creates business 1. Sidebar shows "Owner"; Team page, Invite button, Make admin/member and Archive are visible.
2. **Invite + accept:** A invites B as Member, and C as Admin. Team > Invitations shows both as Pending. Sign in as B: sidebar shows an Invitations badge; accept; business 1 appears in the switcher with "Member".
3. **Member view (B):** no Team link; `/team` shows "Team management is restricted"; no Edit/Archive on the business page.
4. **Admin view (C):** C accepts. Team page shows Invite (Member only in the role list), Remove only on Members, no Make admin/member buttons, Edit visible, Archive hidden. A's Owner row has no actions.
5. **Switching:** B creates business 2 (B is Owner there). Switch between 1 and 2 in the sidebar: topbar, role badge, permissions and Team content change immediately with no stale rows.
6. **Isolation:** A does not see B's business 2 in the list.
7. **Invalid invitations:** decline an invitation, or accept one that expired/was already used, and confirm a clear error appears and the list refreshes.
8. **Unauthorized actions:** with browser devtools, call a restricted endpoint as Member; a 403 message ("You don't have permission...") must appear in any UI path that triggers it. Expired Firebase sessions trigger one token refresh retry, then sign-out.

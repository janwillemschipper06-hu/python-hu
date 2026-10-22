# Authentication Implementation Plan

The **staged, session-by-session execution plan** for building the authentication and access design
into the Customer Onboarding Portal. The *what and why* lives in
[`authentication-and-access.md`](./authentication-and-access.md) (authoritative) and ADRs
[0002](./adr/0002-tenant-isolation-via-execute-only-stored-procedures.md),
[0005](./adr/0005-dedicated-workforce-tenant-invite-only-access.md),
[0006](./adr/0006-three-router-authorization-and-adf-certificate.md),
[0007](./adr/0007-secrets-in-database-envelope-encryption.md),
[0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md), and
[0011](./adr/0011-admin-app-role-assigned-directly-to-users.md). **This doc is the *how
and in what order*.** It is the single source of truth for progress across sessions.

> **Updated during execution:** the plan originally introduced no new ADR. Stage 1's approach changed
> from app-side token validation to **platform authentication** (Azure Container Apps built-in auth),
> recorded in **[ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)**.
> The remaining choices here (staging, workflow) are process, not architecture.
>
> **Admin-authority mechanism changed (ADR-0011):** admin authority is a **direct `Admin` app-role
> assignment on the user** — **not** a `Portal-Admins` group (which would need Entra ID P1 we don't
> have). This is the model in **dev and prod**; the portal automates it via Graph at Stage 5.

> **⚠ Immediate action to unblock admin sign-in (manual, human):** until Stage 5 automates it, assign
> your own user the `Admin` app role by hand — **Entra admin center → Enterprise applications →
> `cop-api-dev` → Users and groups → Add assignment → Users → your user → role Portal Admin →
> Assign.** Without this, no token carries `roles: ["Admin"]` and every `/api/v1/admin/*` call is 403.
> Do **not** add the `Portal-Admins` group (needs P1; retired — [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)).

---

## How to use this doc (resume protocol for a fresh session)

Each stage is executed in its **own Copilot session** with no memory of the others. A session picks
up like this:

1. **Read this whole doc**, plus the referenced sections of `authentication-and-access.md`.
2. In the **Stage index** below, find the **first stage whose Status is not `Done`**.
3. Check its **prerequisites**: the previous stage is `Done`, and every **Entra reference value** the
   stage needs (see the table) is filled in — not a `<fill me>` placeholder. If a prerequisite is
   missing, **stop and tell the human** what Entra work or reference value is outstanding.
4. Execute **only that one stage** — its agent coding + infra work.
5. Keep the repo's existing checks green (`ruff`, `mypy`, existing `pytest`). **Do not** add or run
   auth-specific tests — the human tests everything (see Working agreement). Just don't break the
   build.
6. **Do not commit or push.** Leave the changes in the working tree and **summarise them** (files
   touched + what/why) so the human can review the diff first.
7. Set the stage's Status to **`In review (dev)`** in the Stage index, fill in the "Delivered" note,
   and **stop.** **The human reviews the diff, then commits and pushes to `develop` themselves**
   (this auto-deploys to the dev environment), tests on dev, and when satisfied flips the Status to
   `Done` and starts the next session.

**Status values:** `Not started` → `In progress` → `In review (dev)` → `Done`.

---

## Working agreement (decided in the grilling session, 2026-09-30)

| Topic | Decision |
|---|---|
| **Scope** | The **entire** `authentication-and-access.md` design, delivered in stages. |
| **Who does Entra** | **The human (Jan Willem Schipper) does *all* Entra work manually** — tenants, app registrations, app roles, groups, Conditional Access, certificates, Graph consent. The agent never creates or edits Entra objects. |
| **Who writes code** | **The agent writes code + infra only.** |
| **Testing** | **The human tests everything** on the dev deployment at each review gate. The agent does **not** write or run auth tests; it only keeps the existing lint/type/test suite passing. |
| **Delivery** | The agent **makes the changes but does not commit or push.** The **human reviews the working-tree diff, then commits and pushes to `develop`** (auto-deploys to dev via `.devops/pipelines/deploy.yml`). **No pull requests.** |
| **Environments** | **Dev only.** **Prod is out of scope for this plan** — significant additional work is required before any prod go-live. |
| **Review gate** | Between every stage: the human tests the running dev app, then authorises the next session. |
| **Entra → agent handoff** | The human pastes the non-secret identifiers Entra produces into the **Entra reference values** table below. The agent reads them there and propagates them into `infra/environments/dev/main.bicepparam` (threaded through `main.bicep` → `resources.bicep`). **Real secrets** (e.g. the ADF certificate) go into **Key Vault**, referenced by the app — **never committed**. |

---

## Entra reference values

> **Human fills these in** as each stage's Entra work is done. Everything here is a **non-secret
> identifier** (tenant IDs, client/app IDs, object IDs, role GUIDs) — safe to commit. **Never** put a
> client secret, certificate, or private key in this table.

| Key | Object name | Value | Produced in | Notes |
|---|---|---|---|---|
| Identity tenant ID | `9altitudes Customer Onboarding Portal` | `0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52` | Stage 1 | The dedicated workforce Entra tenant (GUID). |
| Identity tenant primary domain | — | `9altitudesexternaliddev.onmicrosoft.com` | Stage 1 | Its `*.onmicrosoft.com` domain. |
| Corporate tenant ID (9altitudes) | — | `3c2c919b-877a-4cd6-be64-b25bbdaee76f` | Stage 1 | Optional now; needed for cross-tenant/MFA trust (Stage 7). |
| API app — Application (client) ID | `cop-api-dev` | `884c1ef6-d4ec-4098-9f56-2f2192e60d62` | Stage 1 | The **audience** for every portal call. |
| API app — Application ID URI | `cop-api-dev` | `api://884c1ef6-d4ec-4098-9f56-2f2192e60d62` | Stage 1 | Default form. Token `aud`. |
| App role `Admin` — value / ID | on `cop-api-dev` | `Admin` / `d9ca4663-5e3a-41d0-84af-fb97b4becbf1` | Stage 1 | Allowed member types **Users/Groups**; assigned **directly to each admin's user** (never a group — that needs P1). See [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md). |
| App role `Extract.Read` — value / ID | on `cop-api-dev` | `Extract.Read` / `d77cec0a-1a75-443d-b99b-aa560cae40a1` | Stage 9 | Allowed member types **Applications**; created early in Stage 1 — inert until the ADF app is assigned at Stage 9. |
| Delegated scope (SPA → API) | on `cop-api-dev` | `access_as_user` — `api://884c1ef6-d4ec-4098-9f56-2f2192e60d62/access_as_user` | Stage 1 | Admins + users consent. |
| SPA app — Application (client) ID | `cop-spa-dev` | `e91fba5f-0584-4d6e-a399-6562d7bff9fb` | Stage 1 | Public client (SPA platform); used by MSAL in Stage 4. |
| SPA redirect URI(s) | `cop-spa-dev` | `http://localhost:5173`, `https://icy-moss-0bf843003.3.azurestaticapps.net` | Stage 1/4 | Both registered as **SPA** platform URIs (PKCE). The second is the deployed Static Web App default origin — must equal `window.location.origin` (no trailing slash). Add any custom-domain origin here too. |
| `Portal-Admins` group — object ID | `Portal-Admins` | `n/a (retired)` | — | **Retired — not used.** Admin authority is a **direct user app-role assignment** (ADR-0011); no group, no P1, in dev or prod. |
| Backend Graph caller | `cop-graph-dev` | **registered in the resource/corporate tenant** `3c2c919b…` (multitenant) — client ID `2e499fff-f1cf-46e7-b082-c79fe38fc972` (received 2026-10-12). Identity-tenant SP object ID: `b346d0f1-2eed-4ee0-818b-724ac3275ed2` (4 Graph app roles granted on it 2026-10-13). Old identity-tenant app (`client c997ea30-5105-449d-8f53-b5d6b3b01483`, `object c8648ca4-23bd-486e-a951-8c981cbd3209`) is **superseded/unsupported — delete it**. | Stage 5 | Backend authenticates as this app to call Graph. **Separate** from `cop-api-dev`/`cop-spa-dev` (responsibilities split). ⚠️ The original single-tenant-in-identity-tenant app fails with `AADSTS700236`; corrected runbook: [`entra-configuration.md`](./entra-configuration.md) §3.E. |
| ADF client app — appid | `cop-adf-dev` | `fbe02bce-ee96-4121-beb9-ee72d2af4d07` (SP object `9dca69f0-accd-445c-9d65-2c30e324418b`; `Extract.Read` assigned 2026-10-13, no certificate yet) | Stage 9 | Reporting identity; holds `Extract.Read`. Certificate lives in Key Vault. |

---

## Stage index

| # | Stage | Depends on | Status | Delivered |
|---|---|---|---|---|
| 1 | Token validation foundation | — | Done | **Approach changed to platform auth — see [ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md).** App-side PyJWT validator (committed 9d3a397) **replaced** by Container Apps built-in auth (`authConfigs` in `infra/resources.bicep`: `Return401`, `/health`+`/api/v1/ping` excluded, Entra provider issuer/audience, `allowedApplications` for Stage 9); `api/src/auth/` now decodes the injected `X-MS-CLIENT-PRINCIPAL` behind the unchanged `validated_token` seam (PyJWT/`cryptography` + `config.py`/`validator.py` + `ENTRA_*` app env removed). `/whoami` unchanged. **Validated on dev.** |
| 2 | Identity data model | 1 | Done | **Validated on dev.** SSDT: added `onboarding.Users` (Entra `oid` unique, email, non-authoritative role mirror, invited/redeemed stamps), `onboarding.UserCustomers` (scope join, FKs to Users/Customer), append-only `onboarding.AuditLog`; procs `GetUserByOid`, `ListUserCustomers` (in-DB scope enforcement; returns the `Customer` shape), `UpsertUser`, `LinkUserCustomer`/`UnlinkUserCustomer`, `AppendAuditEvent` (sole audit write path). Security: schema-level `GRANT EXECUTE` already covers the new procs with no table rights; added defence-in-depth `DENY UPDATE, DELETE` on `AuditLog` in `create-sql-user-app.sql` **and** the pipeline `SqlUserSetup` job, and documented the posture in `Security/onboarding.sql`. No Python touched; `ruff`/`mypy`/`pytest` unaffected. |
| 3 | Authorization — three routers + guards | 2 | Done | **Validated on dev.** Implemented the three-router authorization model (`authentication-and-access.md` §4). New `api/src/auth/guards.py`: typed role principals `AdminPrincipal`, `AdminActingPrincipal`, `CustomerPrincipal`, `ExtractPrincipal` (+ `PortalPrincipal` union) and the three router-level guards `require_admin` / `require_portal_user` / `require_extract_client` (each `Depends(validated_token)`, role-checks the claim, deny-by-default 403). `require_portal_user` resolves customer scope via new `api/src/services/user_customers.py` `load_user_customers(oid)` → Stage 2 `onboarding.ListUserCustomers`. Restructured `api/src/routers/` into `admin.py` (`/api/v1/admin/*`), `portal.py` (`/api/v1/portal/*`), `extract.py` (`/api/v1/extract/*`), each mounting its guard as a **mandatory router-level dependency**; the old `customers.py` all-customers list moved to `GET /api/v1/admin/customers`, plus portal `GET /customers` (scope-resolved: admin→all, guest→own) and `GET /customers/{id}` (admin→any existing; guest→own or 404 so it can't probe outside scope), and a machine-only `GET /api/v1/extract/customers` reporting feed. Removed the temporary `/whoami` router + service. `src/main.py` now mounts the three routers under the single deny-by-default `protected` router; `src/auth/__init__.py` re-exports the guards/principals. `/health` + `/api/v1/ping` stay unauthenticated (open decision: yes). Updated `tests/test_customers.py` to the admin path (injects an admin principal via `dependency_overrides`); no auth-specific tests added. Verified `ruff`/`mypy` clean and `pytest` green (7 passed), and hand-checked the full guard matrix (admin reaches admin+portal, scoped guest reaches only its own customers + denied others, machine reaches only extract, no token → 401). No infra/Bicep changes. |
| 4 | SPA interactive sign-in | 3 | Done | **Validated on dev.** Implemented the interactive vertical slice in `frontend/` and restyled the SPA to the 9altitudes look shared with the Advanced Monitoring admin portal. **Auth:** added `@azure/msal-browser`; new `frontend/src/authConfig.ts` (authority = identity tenant `VITE_ENTRA_TENANT_ID`, client = SPA app `VITE_SPA_CLIENT_ID`, delegated scope `VITE_API_SCOPE` = the **API** app's `access_as_user` so the token `aud` matches the platform's `allowedAudiences` — ADR-0010). **Token in memory only** per security §5.5/§7 (`cacheLocation: "memoryStorage"` — never local/session storage); `restoreSession()` uses `ssoSilent` to re-establish a session after reload; `signIn`/`signOut` via popup; a `VITE_DISABLE_AUTH` local-dev bypass. `frontend/src/api.ts` now attaches `Authorization: Bearer <token>` and calls the Stage 3 routers; `App.tsx` is a role-aware shell (admin → `/api/v1/admin/customers` all-scope; customer-scoped guest → `/api/v1/portal/customers`), reading the `roles` claim only to choose the view (the API re-checks every call). **Styling:** added Tailwind (`tailwind.config.ts`/`postcss.config.js`, brand palette), rewrote `index.css`, copied the shared brand images into `frontend/src/pictures/`, and added `LoginForm`/`LoadingState`/`CustomerTable` components. **Hardening:** strict CSP + HSTS/`nosniff`/`Referrer-Policy`/`Permissions-Policy` in `staticwebapp.config.json` (§5.5); allow-list is APIM + `login.microsoftonline.com`. **Config:** the frontend's non-secret `VITE_*` build values now have a **single source of truth in Bicep**. `infra/main.bicep` takes an `entraSpaClientId` param (set in `main.bicepparam` alongside the existing `entraTenantId`/`entraApiAudience`) and emits `entraTenantId`/`entraSpaClientId`/`entraApiScope` outputs; the infra stage (`deploy-bicep.sh` → `update-variable-group.sh`) persists them into the `ba-9a-cop-<env>` variable group as `VITE_ENTRA_TENANT_ID`/`VITE_SPA_CLIENT_ID`/`VITE_API_SCOPE`, from where `stage-static-web-app.yml` reads them at build time (so run Infra at least once before a frontend-only deploy). `VITE_API_BASE_URL` stays a manual variable-group entry; `.env.example`/`.env.local` cover local dev. `authConfig.ts` now **fails loudly** if any of those three are empty or an unsubstituted `$( )`/`#{ }` placeholder (surfaced on the login screen) instead of baking a broken authority into the bundle — the original AADSTS900023 root cause. `tsc`/`vite build`, Prettier, and ESLint (`--max-warnings=0`) all clean; `az bicep build` clean (pre-existing env-URL lint warning only); no Python/DB touched. **Deviations from the plan, flagged for review:** (a) used `@azure/msal-browser` only (no `@azure/msal-react`) to match the proven admin-portal pattern; (b) the **HttpOnly refresh-cookie + CSRF (BFF)** part is **deferred** — it is architecturally incompatible with a pure MSAL SPA and needs a backend token-exchange endpoint; it remains the stage's open decision (where the cookie/CSRF terminates) and is not part of this slice. **CSP API host is hardcoded to the dev APIM origin** (`https://api-himal-dev.9altitudes.com`) — parameterise before other envs. |
| 5 | Invite + provisioning via Graph | 4 | Done | **Validated on dev.** Atomic invite endpoint `POST /api/v1/admin/invitations` (`require_admin`, 201) on the admin router. New secretless cross-tenant Graph client `api/app/integrations/graph.py` (`requests`): the Container App UAMI mints an `api://AzureADTokenExchange` assertion, exchanged at the identity tenant for an app-only Graph token as `cop-graph-dev` (federated credential — no stored secret); supports `create_b2b_invitation` and a direct `Admin` app-role assignment (`appRoleAssignedTo` on the `cop-api-dev` SP, idempotent on Graph's duplicate-400). `invite_user` service orchestrates one unit: Graph invite → `onboarding.UpsertUser` → scope (`LinkUserCustomer` per customer for users, or `assign_admin_app_role` for admins) → `onboarding.AppendAuditEvent`; re-invite reuses identity. Added `InvitationRequest`/`InvitationResult`/`Role` schemas with role-shaped scope validation (user requires customers, admin forbids them), `app/core/db.py` `call_procedure` write helper, and a shared cross-cutting `app/core/audit.py` audit write path. Graph failures propagate to a JSON 500 (no custom error wrapping). Infra threads `GRAPH_*` env (tenant/client/API-SP-object/admin-role/authority host) through `resources.bicep`/`main.bicep`; `main.bicepparam` set `entraGraphClientId` + `entraAdminAppRoleId`. Docs: new `entra-configuration.md` §3.E/§4 runbook (separate-app rationale, dev+prod), `.env.example` `GRAPH_*`. Tests green (18 passed), `black`/`ruff`/`mypy` clean, `az bicep build` clean. `entraApiSpObjectId`/`GRAPH_API_SP_OBJECT_ID` = `896af7db-2988-4580-be21-e7e92d29bee2` (cop-api-dev Enterprise-application SP object ID) — both user and admin invites fully wired. |
| 6 | Admin lifecycle management | 5 | Done | **Delivered; Entra Graph consents granted 2026-10-13; human review waived by the owner.** Full admin user-lifecycle, each audited, on the `require_admin` router: resend invite, revoke pending, edit access (add/remove `UserCustomers`), promote/demote (create/remove the direct `Admin` app-role assignment), deactivate (soft) and reactivate, delete (hard). **DB (SSDT):** added `Users.DeactivatedUtc`; new procs `ListUsers` (users + linked-customer count), `UnlinkAllUserCustomers`, `SetUserDeactivated`, `SetUserRoleMirror`, `DeleteUser`; `GetUserByOid` now `CONVERT`s the `oid` to `NVARCHAR(36)` + returns `DeactivatedUtc` (schema-level `GRANT EXECUTE` already covers the new procs; auto-globbed by the `.sqlproj`). **Graph (`api/app/integrations/graph.py`):** added `remove_admin_app_role` (read user `appRoleAssignments`, match the `Admin` assignment, delete it — idempotent) and `delete_guest_user` (404-safe). **Backend (`identity` module):** `PortalUser`/`AccessUpdateRequest`/`RoleUpdateRequest`/`DeactivationRequest`/`LifecycleResult` schemas; repository + service methods for list/get/resend/update-access/set-role/set-deactivated/delete (each writes `AppendAuditEvent`; delete audits `DeleteUser` vs `RevokePendingInvitation` by redeemed state; deactivate removes all scope + `Admin` role + resets the role mirror); admin-router endpoints `GET /users`, `GET /users/{oid}/customers`, `POST /users/{oid}/{resend,access,role,deactivate,delete}`. **All actions use `POST`** (CORS allows only `GET`/`POST`). **Frontend:** new `UserManagement.tsx` (user table + per-row actions + invite form + edit-access panel), wired into `App.tsx` behind an admin **Customers / User management** tab; `api.ts`/`types.ts` extended. `black`/`ruff`/`mypy` clean, 18 pytest pass; frontend `tsc`+`vite build`, ESLint and Prettier clean. **Human prerequisite before dev testing:** ✅ **Done (granted 2026-10-13 via `scripts/entra/Provision-IdentityTenant.ps1`).** All four Graph application permissions are now app-role-assigned on the `cop-graph-dev` SP in the identity tenant (option 4 — assigned on the SP, not declared/consented on the resource-tenant app): `User.ReadWrite.All` (`741f803b-…`, hard-delete/revoke), `User.Read.All` (`df021288-…`, read `appRoleAssignments` for demote/deactivate), plus Stage 5's `AppRoleAssignment.ReadWrite.All` + `User.Invite.All`. Runbook: [`entra-configuration.md`](./entra-configuration.md) §3.E.1. No infra/env changes — but the 2026-10-13 identity-tenant rebuild changed the cop-api/cop-spa/cop-graph client IDs + cop-api SP object ID, so **run the Infra stage before testing** (updates EasyAuth + `GRAPH_*` env + the `ba-9a-cop-dev` variable group's `VITE_SPA_CLIENT_ID`). |
| 7 | Sign-in security policies (Conditional Access) | 4 | **Deferred — needs Entra ID P1** | The identity tenant is on **Microsoft Entra ID Free**, so Conditional Access policies cannot be created. To be done **in the future, once the identity tenant is licensed for P1** (per-user P1 or External ID MAU model; see `scripts/entra/README.md`). Until then, sign-in security relies on what the Free tier offers (e.g. Security Defaults / per-user MFA). Nothing in Stages 8–10 is blocked by this. |
| 8 | Secret storage + envelope encryption | 3 | **Out of scope for this plan** | Not Entra work (the stage itself says "Your Entra work: none"). It is Key Vault Premium/HSM, DB, and backend work that belongs with the **template and task** features (submit/reveal/purge), where it will be planned and built. Tracked there, not here. |
| 9 | Machine identity — ADF reporting extraction | 3 | In progress | **Entra work done on dev (2026-10-13):** `Extract.Read` role on `cop-api-dev`, `cop-adf-dev` client + service principal, role assigned, appid in `entraAllowedApplications`. **Remaining:** ADF certificate (Key Vault) uploaded to the client; the extract router currently serves only the basic `GET /api/v1/extract/customers`; review gate (cert client reaches the feed, non-allowlisted appid rejected). |
| 10 | Hardening & detection | 5,9 (7 deferred, 8 out of scope) | Not started | Can start now. Items tied to Stage 7 (Conditional Access / impossible-travel signals) and Stage 8 (secret-reveal / Key Vault unwrap alerts) are deferred with those stages. |

---

## Stage 1 — Token validation foundation

> **Approach changed — authentication is offloaded to the platform.** Token *validation* is done by
> **Azure Container Apps built-in authentication** ("EasyAuth"), configured in this repo's Bicep as a
> `Microsoft.App/containerApps/authConfigs` resource in **API mode** (`unauthenticatedClientAction:
> Return401`). The app **does not validate JWTs**; it reads the platform-injected `X-MS-CLIENT-PRINCIPAL`
> behind the existing `validated_token` seam and does **authorization only**. See
> **[ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)**. The
> already-committed app-side PyJWT validator (9d3a397) is the first pass and will be **replaced** by
> this; `/api/v1/whoami` and the `validated_token` seam are kept.

**Reads:** `authentication-and-access.md` §2 (identity topology, app registrations), §4.3 (guard
sketch); [ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md).

**Goal / definition of done:** the deployed API is fronted by **Container Apps built-in auth** so a
real Entra access token issued by the identity tenant is validated **by the platform** (signature,
issuer, audience, expiry) before reaching the app, and a temporary authenticated endpoint echoes the
platform-injected caller claims — so the human can confirm end-to-end token validation before any
authorization logic exists. A missing/invalid token is rejected with `401` **by the platform**.

**Your Entra work (concrete runbook — all in the [Entra admin center](https://entra.microsoft.com)):**

> Object names are fixed here so a fresh session and the reference table agree. Do this in the
> **identity tenant** unless a step says otherwise. **P1 note (confirmed for this dev tenant):**
> assigning an app role to a *group* needs Entra ID P1, which this tenant does **not** have — and
> which we do **not** require. Admins are assigned the `Admin` role **directly on their user**
> (step 3), in **dev and prod**; the portal automates this via Graph at Stage 5. There is **no**
> `Portal-Admins` group ([ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)); the
> backend behaves identically (the token carries `roles: ["Admin"]`).

1. **Create the identity tenant.** Manage tenants → Create → **Workforce**. Organization name
   `9altitudes Customer Onboarding Portal`; initial domain `9acopidentity` (→
   `9acopidentity.onmicrosoft.com`; pick another if taken); set country for residency. Switch into
   the new tenant. Confirm **no self-service sign-up / user flows** exist (default). **Record** the
   tenant ID and primary domain.
2. **API app registration** (App registrations → New registration):
   - Name `cop-api-dev`; account type **single tenant** (this directory only); no redirect URI.
     **Record** the Application (client) ID.
   - **Expose an API** → set Application ID URI to the default `api://<client-id>` (**record** it) →
     Add a scope: name `access_as_user`, who can consent **Admins and users**, enable it.
   - **App role** → create **one** (**record its ID**):
     - Display "Portal Admin", value `Admin`, allowed member types **Users/Groups**, description
       "Full portal administrator: manage customers, users, and templates, and reveal customer secrets."
     - The `Extract.Read` reporting role is created later in **Stage 9** (when the feed is built).
       There is **no** `Secret.Consume` role — see
       [ADR-0009](./adr/0009-no-machine-secret-consumer.md) (no machine secret-consumer).
3. **Admin assignment (direct user app-role — the model in dev *and* prod; no P1):**
   - Enterprise applications → `cop-api-dev` → Users and groups → Add assignment → under **Users**
     select **your own user** → role **Portal Admin** → Assign. **Record** which user(s) you assigned.
     This is what puts `roles: ["Admin"]` in your token so `require_admin` passes — **without it, no
     one is an admin.**
   - This first assignment is the **bootstrap**; from **Stage 5** the portal creates/removes these
     assignments for you via Graph. There is **no** `Portal-Admins` group (assigning a role to a group
     needs P1 and is **not used** — [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)).
4. **SPA app registration** (App registrations → New registration):
   - Name `cop-spa-dev`; single tenant; platform **Single-page application**; redirect URI
     `http://localhost:5173`. **Record** the Application (client) ID. Under Authentication, set
     **Allow public client flows = Yes** (lets you fetch a test token for the Stage 1 gate).
   - API permissions → Add → **My APIs** → `cop-api-dev` → Delegated → `access_as_user` → Add →
     **Grant admin consent**.
5. *(Optional now, needed Stage 7)* **Record** the **9altitudes corporate tenant ID**.
6. **Paste every recorded value into the Entra reference values table above**, then tell the agent
   "Stage 1 Entra done".

**Agent coding work:**
- **Remove** the app-side JWT/JWKS validation stack: drop `PyJWT[crypto]` + `cryptography` from
  `api/requirements.txt` and delete the crypto/JWKS logic in `api/src/auth/validator.py`. The app
  performs **no** token cryptography.
- Keep the **`validated_token` FastAPI dependency** as the public seam, but re-implement it to parse
  the **platform-injected** principal header `X-MS-CLIENT-PRINCIPAL` (base64 JSON: a set of validated
  claims) and return the same parsed-claims shape (`oid`, `roles`, `azp`/`appid`, audience). Keep the
  defensive claim accessors in `api/src/auth/claims.py`. This keeps Stages 3/5/6/8 unchanged.
- Keep the **temporary** `GET /api/v1/whoami` protected by `validated_token` returning `oid`,
  `roles`, `azp`/`appid`, and audience. (Removed or folded into a router in Stage 3.)
- Leave the existing `/health`, `/api/v1/ping`, `/api/v1/customers` untouched for now.

**Infra / config:**
- Add a **`Microsoft.App/containerApps/authConfigs`** child resource to `infra/resources.bicep` (its
  values threaded via `infra/main.bicep` params and `infra/environments/dev/main.bicepparam`):
  - `globalValidation.unauthenticatedClientAction: Return401` (API/bearer mode — never redirects).
  - An identity provider whose **issuer/metadata** points at the identity tenant's OpenID
    configuration and whose **`allowedAudiences`** is the API Application ID URI
    (`api://<cop-api-dev-client-id>`). The identity tenant is a **dedicated, standard workforce Entra
    tenant** (ADR-0005), so the issuer is the standard workforce host — confirm with a real token.
  - `allowedApplications` left ready for the Stage 9 ADF appid (empty in Stage 1).
- The `ENTRA_TENANT_ID` / `ENTRA_API_AUDIENCE` env vars may stay for reference, but they are **no
  longer used for validation** (the platform validates). Update `api/.env.example` to note this.
- **May be required:** the auth provider config can need a **client secret / metadata reference**. If
  so, the human creates it on the API app registration (Entra) and it is stored in the **existing Key
  Vault** (the UAMI already has *Key Vault Secrets User*) and referenced from `authConfigs` — **never
  committed**. Confirm the exact requirement when implementing.

**Review gate (human, on dev):** acquire a token for the API audience (e.g. an admin sign-in or a
test token) and call `/api/v1/whoami` through the deployed app — a valid token returns claims incl.
`roles: ["Admin"]` for you; a missing/invalid token returns 401.

**Open decisions to resolve in this stage:**
- **Local-dev auth story.** With validation in the platform, the app runs locally by **injecting a
  fake principal at the `validated_token` seam** (e.g. a dev-only header/fixture), since there is no
  EasyAuth sidecar locally. Deployed environments always sit behind the platform auth (no bypass in
  the app). Pin the exact fake-principal mechanism when implementing.
- **Issuer/provider shape.** Confirm the identity provider is configured as the
  `azureActiveDirectory` provider with `openIdIssuer` set to the workforce tenant's issuer, and
  whether a client secret is required — verify against a real token at the review gate.

---

## Stage 2 — Identity data model

**Reads:** `authentication-and-access.md` §9 (data model touchpoints), §4.1; ADR-0002 (EXECUTE-only
stored procedures); ADR-0008 (app data access via stored procedures only).

**Goal / definition of done:** the database has the `Users`, `UserCustomers`, and append-only audit
tables and the EXECUTE-only stored procedures that later stages call, deployed to dev — with the app
SQL principal holding **EXECUTE only**, no raw table access.

**Your Entra work:** none.

**Agent coding work (SSDT project under `database/`):**
- Add tables under `database/onboarding/Tables/`: `Users` (Entra `oid`, email, role mirror,
  invited/redeemed timestamps), `UserCustomers` (user↔customer scope join), and an **append-only
  audit** table.
- Add stored procedures under `database/onboarding/Stored Procedures/` for the reads/writes later
  stages need (user lookup by `oid`, load a user's customer scope, upsert user, link/unlink
  customer, append audit row). Follow the existing `ListCustomers.sql` pattern.
- Extend `database/Security/onboarding.sql` (and `database/Scripts/create-sql-user-app.sql`) so the
  app principal gets **EXECUTE** on the new procs and **no** direct table rights; the audit table is
  **insert-only** for the app (no `UPDATE`/`DELETE`).

**Infra / config:** none beyond the DB deploy stage picking up the SSDT changes.

**Review gate (human, on dev):** confirm the DB deploy applied the new objects; spot-check that the
app principal cannot `SELECT`/`UPDATE` the tables directly and that the procs enforce customer scope.

**Open decisions to resolve in this stage:**
- Exact audit schema (columns) — keep it **value-free** (who/what/when/target IDs only).

---

## Stage 3 — Authorization: three routers + guards

**Reads:** `authentication-and-access.md` §4 (authorization model, three routers, guard sketch).

**Goal / definition of done:** the API enforces the three-router model — `require_admin`,
`require_portal_user`, `require_extract_client` — mounted as **router-level** dependencies, with the
existing endpoints moved under the correct router and customer scope resolved from `UserCustomers`.

**Your Entra work:** none (uses the app roles from Stage 1).

**Agent coding work:**
- Implement the guards and principal types (`AdminPrincipal`, `AdminActingPrincipal`,
  `CustomerPrincipal`, `ExtractPrincipal`) per §4.3, backed by the Stage 2 procs
  (`load_user_customers`).
- Restructure `api/src/routers/` into `admin` (`/api/v1/admin/*`), `portal` (`/api/v1/portal/*`),
  and `extract` (`/api/v1/extract/*`) routers, each mounting its guard as a **mandatory router-level
  dependency**. Move `customers` under the appropriate router; remove/fold the temporary `/whoami`.
- Admin-acting-on-customer path: scope taken from the **customer named in the request path**.

**Infra / config:** none.

**Review gate (human, on dev):** an admin token reaches admin + portal routes; a scoped customer
token reaches only its own customers and is denied others; an unscoped/invalid token is denied; a
machine role cannot reach interactive routes.

**Open decisions to resolve in this stage:**
- Whether `/api/v1/ping` and `/health` stay unauthenticated (recommended: yes — probes/smoke).
  **Resolved: yes** — both remain mounted outside the `protected` router (unchanged from Stage 1), so
  the platform health probe and the post-deploy smoke test reach them with no token.

---

## Stage 4 — SPA interactive sign-in

**Reads:** `authentication-and-access.md` §7 (browser session hardening), §5 (sign-in security).

**Goal / definition of done:** the React SPA signs a user in against the identity tenant with MSAL,
acquires an access token for the API scope, and calls the protected API end-to-end — admin and
customer views each seeing only what they're entitled to. This completes the **interactive vertical
slice**.

**Your Entra work:**
- Finalise the **SPA redirect URIs** (Static Web App origin + local dev) and PKCE/public-client
  config on the SPA app registration; grant the delegated API scope; admin-consent if required.
- Paste the redirect URIs into the reference table.

**Agent coding work (`frontend/`):**
- Add MSAL (`@azure/msal-browser` + `@azure/msal-react`); configure authority = identity tenant,
  client ID = SPA app, API scope from Stage 1.
- **Access token in memory only** — never `localStorage`/`sessionStorage`. Wire `frontend/src/api.ts`
  to attach the bearer token; add login/logout and route guards for admin vs customer views.
- Apply the **refresh-token cookie** (`HttpOnly; Secure; SameSite=Strict`) + **CSRF** protection and
  the **strict CSP / security headers** in `frontend/staticwebapp.config.json` (§7).

**Infra / config:** build-time `VITE_*` values (SPA client ID, authority, API scope) are sourced from
Bicep (`main.bicepparam` → `main.bicep` outputs → infra stage → `ba-9a-cop-<env>` variable group →
Static Web App build); `VITE_API_BASE_URL` stays a manual variable-group entry. Ensure the API
`STATIC_WEBAPP_URL`/CORS origin matches. The SPA's requested API scope/audience **must equal the
platform's `allowedAudiences`** (the API Application ID URI from Stage 1) so Container Apps built-in
auth accepts the bearer token; EasyAuth runs in `Return401` API mode and does **not** redirect the
SPA (see
[ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)).

**Review gate (human, on dev):** sign in as yourself (admin) and as a test customer user; confirm
each sees only permitted data, the token is not in web storage, and CSP is enforced.

**Open decisions to resolve in this stage:**
- Where the refresh-cookie + CSRF is terminated (SPA host vs API vs APIM) — pin when implementing.

---

## Stage 5 — Invite + provisioning via Microsoft Graph

**Reads:** `authentication-and-access.md` §3 (invite-only provisioning), §6 (lifecycle), §12 (audit).

**Goal / definition of done:** an admin can submit the **Invite** form and, as one atomic action, the
backend issues an Entra B2B guest invitation, creates/reuses the `Users` row, and provisions scope
(`UserCustomers` links for a user, or a **direct `Admin` app-role assignment** for an admin) — with an
audit entry.

**Your Entra work:**
- Create a **dedicated Graph-caller app registration** (`cop-graph-<env>`) **in the resource/corporate
  tenant** (same tenant as the Container App's UAMI) as a **multitenant** app, **secretless** via a
  federated identity credential trusting the UAMI (same-tenant trust — Entra blocks cross-tenant
  MI-as-FIC with `AADSTS700236`), then **provision + admin-consent it into the identity tenant**.
- Grant it the **Graph permissions** needed to invite B2B guests (`User.Invite.All`) and **manage
  app-role assignments** (`AppRoleAssignment.ReadWrite.All`), and admin-consent them.
- Record in the reference table which identity calls Graph and which permissions were consented.
- **Step-by-step runbook (dev + prod) + why it's a separate app:**
  [`entra-configuration.md`](./entra-configuration.md) §3.E and §4.

**Agent coding work:**
- Backend Graph client (app-only) for: create B2B invitation, create/remove the user's `Admin`
  app-role assignment (`appRoleAssignedTo` on the `cop-api-dev` service principal).
- The **atomic invite** endpoint on the admin router: Graph invite + `Users` upsert + scope
  provisioning + audit write, as one unit of work; re-invite never duplicates identity.
- Plain, secret-free invite notification per §3.3.

**Infra / config:** any Graph endpoint/config env vars; Key Vault references if a Graph credential is
needed (prefer the managed identity — no stored secret).

**Review gate (human, on dev):** invite a test customer and a test admin; confirm the guest
invitation, the `Users`/`UserCustomers` rows (or the `Admin` app-role assignment), and the audit
entries.

**Open decisions to resolve in this stage:**
- **Graph permission scope:** `AppRoleAssignment.ReadWrite.All` is **tenant-wide** (no resource-scoped
  variant); accepted for this dedicated identity tenant per
  [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md), mitigated by app-only consent +
  audit on every assignment change.
- **RESOLVED (corrected) — how the backend calls Graph:** a **dedicated multitenant app registration**
  (`cop-graph-<env>`) **in the resource/corporate tenant** (same tenant as the UAMI), **secretless** via
  a **federated identity credential** trusting the UAMI, **provisioned + admin-consented into the
  identity tenant** where its Graph permissions live. The earlier "single-tenant app in the identity
  tenant" shape is **unsupported** (`AADSTS700236`: Entra forbids federating to a managed identity in a
  different tenant). Reusing `cop-api`/`cop-spa` was rejected to keep tenant-wide Graph privilege
  isolated. Full corrected runbook + rationale: [`entra-configuration.md`](./entra-configuration.md)
  §3.E and §4.

---

## Stage 6 — Admin lifecycle management

**Reads:** `authentication-and-access.md` §6 (user lifecycle), §8 (admin management from the portal).

**Goal / definition of done:** the admin UI can run the full lifecycle — resend, revoke pending,
edit access (add/remove `UserCustomers`), promote/demote (create/remove the `Admin` app-role
assignment), deactivate (soft), delete (hard) — all from the portal, each audited.

**Your Entra work:** declare **two** additional Graph application permissions beyond Stage 5 on the
`cop-graph-<env>` app registration (in the resource/corporate tenant) and **grant admin consent in the
identity tenant** (on its provisioned SP) — `User.ReadWrite.All` (`741f803b-c850-494e-b5df-cde7c675a1ca`,
to delete the guest object on hard-delete / revoke) and `User.Read.All`
(`df021288-bdef-4463-88db-98f22de89214`, to read a user's `appRoleAssignments` for demote/deactivate).
`AppRoleAssignment.ReadWrite.All` (remove the assignment) is already granted from Stage 5. Runbook:
[`entra-configuration.md`](./entra-configuration.md) §3.E.1.

**Agent coding work:**
- Admin-router endpoints for each lifecycle action via Graph + DB, with audit writes.
- Admin UI in `frontend/` for the user list and these actions.

**Infra / config:** none new.

**Review gate (human, on dev):** exercise each lifecycle action against test users; confirm CAE-style
de-provisioning removes access and audit entries are written.

---

## Stage 7 — Sign-in security policies (Conditional Access)

> **Status: DEFERRED.** The identity tenant is on Microsoft Entra ID Free; Conditional Access needs
> Entra ID P1. We will do this stage in the future, once the tenant is actually P1. The content below
> is kept as the plan for that time.

**Reads:** `authentication-and-access.md` §5 (MFA, Conditional Access, sessions).

> **Entra-only stage — no meaningful coding.** Placed after Stage 4 so policies are validated against
> a working sign-in. You *may* run it earlier; it does not block other coding stages.

**Goal / definition of done:** the identity tenant enforces the §5 posture: phishing-resistant MFA
for admins (via cross-tenant inbound MFA trust with the corporate tenant), app-based MFA for customer
users (no SMS/email OTP as the factor), session lifetimes (~8h admin / ~24h customer), **CAE on**,
legacy auth blocked, non-persistent browser sessions.

> **Scope to this portal's apps.** The identity tenant is a dedicated **workforce** tenant but it
> hosts **more than one application**, so **target each Conditional Access policy at this portal's
> cloud apps** (`cop-api-<env>`, `cop-spa-<env>`) — **not** *All cloud apps* — so other apps in the
> tenant are unaffected. MFA grant, session controls, and the legacy-auth block are all per-app
> assignable. The **cross-tenant inbound MFA trust** is the exception: it lives in **External
> Identities → Cross-tenant access settings**, is keyed per **partner organization** (not per app),
> and only affects guests invited from the corporate tenant. See `authentication-and-access.md` §5.

**Your Entra work:** configure the Conditional Access policies (app-scoped as above) and cross-tenant
access settings.

**Agent coding work:** documentation only — record the enacted policies (e.g. a short note in this
plan or `security-design.md`); adjust the app's session-frequency expectations if needed.

**Review gate (human):** verify MFA is enforced for both roles on dev sign-in; confirm CAE
de-provisioning takes near-real-time effect (tie in with Stage 6).

---

## Stage 8 — Secret storage + envelope encryption

> **Status: OUT OF SCOPE for this auth plan.** This is not Entra work; it is delivered together with
> the template and task features. The content below is kept as the design reference for that work.

**Reads:** `authentication-and-access.md` §11 (secret storage, encryption, retrieval, disposal);
ADR-0007; ADR-0002.

**Goal / definition of done:** customer secrets are stored as **ciphertext only** under
application-layer envelope encryption (AES-256-GCM DEK wrapped by an **HSM KEK** in Key Vault
Premium), reachable only through EXECUTE-only procs; admins can reveal (incl. bulk) and the
submit/reveal paths never log secret values; lifecycle `stored → opened → purged` with the disposal
job.

**Your Entra work:** none (KEK access is via the app's managed identity in the resource tenant).

**Agent coding work + infra:**
- **Infra:** upgrade Key Vault from **Standard to Premium** (HSM) in `infra/resources.bicep`; create
  the **KEK** key; grant the UAMI **wrap/unwrap only (no export)**. Add any needed env/config.
- **DB:** `Secrets` table/schema (ciphertext + nonce + auth tag + key-version) and EXECUTE-only procs
  (ADR-0002); no raw `SELECT` on ciphertext for the app.
- **Backend:** envelope-encryption service using a vetted crypto library (no hand-rolled primitives):
  per-value DEK, AES-256-GCM, KEK wrap/unwrap via Key Vault; **submit**, **admin reveal**
  (bulk-capable, no step-up, one audit entry each), and the **daily + completion purge** job (§11.5);
  strict **no-body-logging** on submit/reveal routes (§11.3).

**Review gate (human, on dev):** submit a secret, confirm the DB holds only ciphertext; reveal it as
admin; confirm audit entries and that no value appears in any log; confirm purge behaviour.

**Open decisions to resolve in this stage:**
- KEK rotation cadence and key-version handling.
- Exactly which job/scheduler runs the daily purge (Container App job vs cron vs pipeline).

---

## Stage 9 — Machine identity: ADF reporting extraction

**Reads:** `authentication-and-access.md` §10 (ADF/reporting identity), §4.2 (extract router);
ADR-0006; ADR-0009 (no machine secret-consumer).

**Goal / definition of done:** the `extract` router serves the single ADF **reporting** client
(`Extract.Read`, certificate auth, carrying **no** secret values) behind the Container Apps built-in
auth `appid` allowlist (`allowedApplications`;
[ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)). There is **no**
machine secret-consume path (ADR-0009).

**Your Entra work:**
- Add the **`Extract.Read`** app role on `cop-api-dev` (display "Reporting Extract Read", allowed
  member types **Applications**, description "Machine reporting access to the extraction API
  (dashboard feeds). Never returns secret values.").
- Create the **`cop-adf-dev`** client app registration and assign it the `Extract.Read` role.
- Create the ADF **certificate**; store it in **Key Vault** (ADF-side), rotate on schedule —
  **never** commit it.
- Paste the appid and the `Extract.Read` role ID into the reference table.

**Agent coding work + infra:**
- Extract-router reporting endpoints (`Extract.Read`) carrying **no** secret values, plus the
  `require_extract_client` guard (accepts only `Extract.Read`).
- Enforce the caller-`appid` **allowlist** in **this repo's** Container Apps built-in auth: add the
  `cop-adf-dev` appid to `allowedApplications` in the Stage 1 `authConfigs`. The app's
  `require_extract_client` guard still checks `roles: ["Extract.Read"]`. Per
  [ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md), APIM (if
  present) only routes `/api/v1/extract/*` and is **no longer** the authoritative allowlist.

**Review gate (human, on dev):** the cert client reaches the reporting feed; a non-allowlisted appid
is rejected; no secret values are ever returned on this router.

**Open decisions to resolve in this stage:**
- Certificate vs client-secret fallback for ADF (doc §10 allows the fallback if cert management is
  too heavy).
- ~~Where the `appid` allowlist is maintained (shared APIM vs this repo).~~ **Resolved
  ([ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)):** in this
  repo, via Container Apps built-in auth `allowedApplications`.

---

## Stage 10 — Hardening & detection

**Reads:** `authentication-and-access.md` §12 (logging, audit, detection), §13 (residual risks); §7.

**Goal / definition of done:** the anomaly-based detection, log hygiene, and header hardening are in
place, and the delivered system is checked against the threat model and residual-risk register.

**Your Entra work:** none (any Entra-side sign-in logging/alerts you choose to add are optional).

**Agent coding work + ops:**
- **Anomaly alerts** in Log Analytics (§12): unusual secret-reveal/decrypt volume, off-hours admin
  bursts, auth-failure/authorization-denial spikes, impossible-travel, anomalous Key Vault unwrap
  volume; retain the high-signal per-link-creation alert.
- **Auth-failure (`401`) signals now originate at the platform layer** — source the auth-failure
  alerts from **Container Apps built-in auth logs**, while authorization-denial (`403`) signals stay
  in app logs (see [ADR-0010](./adr/0010-platform-authentication-via-container-apps-built-in-auth.md)).
- Confirm **append-only** audit retention/immutability (~12 months).
- Verify the SPA **CSP/security headers** and output-encoding (§7) against the final build.
- Walk the **residual-risk table** (§13, R1/R2/R4/R5) and confirm each compensating control is real.

**Review gate (human):** review alerts firing on synthetic anomalies; confirm no secret values in
logs; sign off the residual-risk register.

---

## References

- [`authentication-and-access.md`](./authentication-and-access.md) — authoritative design.
- [`security-design.md`](./security-design.md) — §3–§5 defer to the above.
- ADR-0002 / 0005 / 0006 / 0007 / 0008 / 0010.
- `.devops/pipelines/deploy.yml` — the dev deploy pipeline (push to `develop` → dev).

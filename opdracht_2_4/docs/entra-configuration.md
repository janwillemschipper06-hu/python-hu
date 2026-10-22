# Entra configuration runbook

Every **manual Microsoft Entra object** this portal depends on — what it is, **why it exists**, and the
**exact steps to recreate it per environment**. Use this as the dev record and the **prod go-live
checklist**.

- **Design rationale (the "why" in depth):** [`authentication-and-access.md`](./authentication-and-access.md) §2 (identity topology & app registrations).
- **Staged build narrative & review gates:** [`authentication-implementation-plan.md`](./authentication-implementation-plan.md) (the per-stage "Your Entra work" runbooks). This doc **consolidates** those into one place and adds the dev→prod mapping.
- **Load-bearing decisions:** ADR-0005 (dedicated workforce tenant, invite-only), ADR-0006 (three-router authz + ADF certificate), ADR-0010 (platform auth via Container Apps built-in auth), ADR-0011 (admin authority = direct `Admin` app-role assignment), ADR-0012 (four app roles `Admin`/`PM`/`User`/`Extract.Read`; assignment required).

> **Who does this:** a human, in the [Entra admin center](https://entra.microsoft.com), in the
> **identity tenant** unless a step says otherwise. The agent never creates or edits Entra objects.
> **Secrets rule:** every identifier recorded here (tenant/client/object IDs, role GUIDs) is
> **non-secret and safe to commit**. **Never** commit a client secret, certificate, or private key —
> those live in Key Vault.

---

## 1. Tenant topology — why three tenants

Three Entra tenants are kept apart **on purpose** (ADR-0005). The split is the backbone of the whole
auth design, so it is the first thing to understand before creating any object.

| Tenant | Role | Why separate |
|---|---|---|
| **Identity tenant** (dedicated workforce Entra) | Holds the portal's access-control objects — the app registrations, app roles, and the **guest users** (admins + customers). This is where sign-in and all Graph provisioning happen. | A disposable, low-privilege directory dedicated to this app. It is **not** the corporate directory and **not** where the Azure resources live, so a bug or compromise here cannot touch corporate identities or production infrastructure. |
| **Corporate tenant (9altitudes)** | Home directory of admin staff. Admins authenticate here (corporate MFA / Conditional Access) and are admitted to the identity tenant as **B2B guests**. | The portal never manages corporate identities — it only manages a guest's `Admin` app-role assignment in the identity tenant. Keeps corporate IAM out of scope. |
| **Application (resource) tenant** | Where the Container App, Azure SQL, Key Vault, APIM, and the app's **managed identities** live. | Inbound user tokens (identity tenant) and Azure resource access (managed identities, resource tenant) are deliberately different trust domains that never mix. |

**Consequence that drives Stage 5:** a **managed identity is single-tenant** — it is a service
principal in the *resource* tenant and can only get tokens for its own tenant. All Graph provisioning
(B2B invite, app-role assignment) happens in the *identity* tenant. **So the Container App's managed
identity cannot call the identity tenant's Graph directly.** A dedicated **Graph-caller app
registration** is required — see §3.E.

> **Where that app must live (load-bearing, learned the hard way).** Entra forbids an app registration
> from federating to a managed identity in a **different** tenant (`AADSTS700236`). So the Graph-caller
> app **must be registered in the same tenant as the UAMI — the resource/corporate tenant
> `3c2c919b…`** — as a **multitenant** app, and then **provisioned (admin-consented) into the identity
> tenant** `0ef950c5…`, where it holds its Graph permissions and runs its Graph calls. Registering it
> as a single-tenant app **in the identity tenant** (the original design) makes the secretless token
> exchange fail. Full corrected runbook: §3.E.

---

## 2. Recorded identifiers (dev → prod)

Fill the **prod** column during prod go-live. Keep this in sync with the "Entra reference values"
table in [`authentication-implementation-plan.md`](./authentication-implementation-plan.md) (same
values, this is the environment-comparison view).

| Identifier | Dev value | Prod value |
|---|---|---|
| Identity tenant — name | `9altitudes Customer Onboarding Portal` | _create a separate prod identity tenant_ |
| Identity tenant — ID | `0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52` | `<fill me>` |
| Identity tenant — primary domain | `9altitudesexternaliddev.onmicrosoft.com` | `<fill me>` |
| Corporate tenant (9altitudes) — ID | `3c2c919b-877a-4cd6-be64-b25bbdaee76f` | `3c2c919b-877a-4cd6-be64-b25bbdaee76f` (same) |
| **Resource tenant** — ID (Azure subscription hosting the Container App) | `3c2c919b-877a-4cd6-be64-b25bbdaee76f` (subscription `Business Analytics Dev-Test`; **same tenant as the 9altitudes corporate tenant**) | `<fill me>` |
| API app — name / client ID | `cop-api-dev` / `884c1ef6-d4ec-4098-9f56-2f2192e60d62` | `cop-api-prod` / `<fill me>` |
| API app — Application ID URI | `api://884c1ef6-d4ec-4098-9f56-2f2192e60d62` | `api://<prod client id>` |
| **API app — service principal (enterprise app) object ID** (appRoleAssignedTo target → `GRAPH_API_SP_OBJECT_ID`) | `fed094f0-b689-4507-9f43-fd3dc0406c1a` | `<fill me>` |
| App role `Admin` — value / ID | `Admin` / `d9ca4663-5e3a-41d0-84af-fb97b4becbf1` | `Admin` / `<fill me>` |
| App role `PM` — value / ID (pinned) | `PM` / `bb99654e-c0a6-4fc9-9896-4503cafa4f08` | same (pinned) |
| App role `User` — value / ID (pinned) | `User` / `bb810150-d66a-4059-8fea-89a05b4c5d7c` | same (pinned) |
| App role `Extract.Read` — value / ID | `Extract.Read` / `d77cec0a-1a75-443d-b99b-aa560cae40a1` | `Extract.Read` / `<fill me>` |
| Delegated scope (SPA→API) | `access_as_user` (`api://884c1ef6-…/access_as_user`) | `access_as_user` (`api://<prod>/access_as_user`) |
| SPA app — name / client ID | `cop-spa-dev` / `e91fba5f-0584-4d6e-a399-6562d7bff9fb` | `cop-spa-prod` / `<fill me>` |
| SPA redirect URIs | `http://localhost:5173`, `http://localhost:5173/blank.html`, `https://icy-moss-0bf843003.3.azurestaticapps.net`, `https://icy-moss-0bf843003.3.azurestaticapps.net/blank.html` | prod SPA origin(s) **and** each origin + `/blank.html` |
| **Graph caller app** — registered in the **resource/corporate tenant** `3c2c919b…` (multitenant), provisioned into the identity tenant — name / client ID | `cop-graph-dev` / `2e499fff-f1cf-46e7-b082-c79fe38fc972` (received 2026-10-12; old identity-tenant app `c997ea30-5105-449d-8f53-b5d6b3b01483` is **superseded/unsupported** — delete it) | `cop-graph-prod` / `<fill me>` |
| **Graph caller app — service-principal object ID in the IDENTITY tenant** (created by admin-consent, §3.E Part 2) | `b346d0f1-2eed-4ee0-818b-724ac3275ed2` (4 Graph app roles granted 2026-10-13; old `c8648ca4-23bd-486e-a951-8c981cbd3209` was the identity-tenant single-tenant app, superseded) | `<fill me>` |
| UAMI (Container App identity) — object/principal ID | `69426bc0-1524-4f77-8cad-d6932ed6a75e` | `<fill me>` |
| UAMI — client ID | `ebefebdb-f851-458b-a921-a12d9d79aafd` | `<fill me>` |
| ADF client app — appid (Stage 9) | `cop-adf-dev` / `fbe02bce-ee96-4121-beb9-ee72d2af4d07` (SP object `9dca69f0-accd-445c-9d65-2c30e324418b`) | `cop-adf-prod` / `<fill me>` |

---

## 3. Object inventory

Each object below has one responsibility. See §4 for why they are **not** merged.

### A. Identity tenant

- **What:** a dedicated, standard **workforce** Entra tenant, self-service sign-up **off**.
- **Why:** an isolated, disposable directory for the portal's access control (§1).
- **Steps:** Manage tenants → Create → **Workforce**. Name + initial `*.onmicrosoft.com` domain
  (use a `…prod…` domain for prod so it is distinguishable from dev); set residency country. Switch
  into the new tenant and confirm **no user flows / self-service sign-up** exist (default). Record the
  tenant ID + primary domain.

### B. API app registration (`cop-api-<env>`)

- **What:** the **resource server / audience** for every portal call. Container Apps built-in auth
  validates each inbound token against this app's audience (ADR-0010). It also **defines the app
  roles** and the delegated scope. It holds **no outbound credential and no Graph permissions.**
- **Why:** one audience the SPA and the machine caller both target; the single place app roles are
  declared and carried in the token as `roles`.
- **Steps (identity tenant → App registrations → New registration):**
  1. Name `cop-api-<env>`, account type **single tenant**, no redirect URI. Record the client ID.
  2. **Expose an API** → Application ID URI = default `api://<client-id>` (record it) → **Add a
     scope** `access_as_user`, who can consent **Admins and users**, enabled.
  3. **App roles** → create:
     - `Admin` — display "Portal Admin", allowed member types **Users/Groups**, description "Full
       portal administrator: manage customers, users, templates, and reveal customer secrets."
       Record the role ID.
     - `Extract.Read` — allowed member types **Applications** (inert until the ADF app is assigned in
       Stage 9). Record the role ID. There is **no** `Secret.Consume` role (ADR-0009).

### C. SPA app registration (`cop-spa-<env>`)

- **What:** the **public client** the browser signs in with (MSAL, PKCE). No secret.
- **Why:** interactive user sign-in only; a public client must never hold app permissions or
  credentials, so it is strictly separate from the API and Graph-caller apps.
- **Steps:**
  1. New registration, name `cop-spa-<env>`, single tenant, platform **Single-page application**,
     redirect URI(s) = each SPA origin (local dev + deployed origin, **no trailing slash**, must equal
     `window.location.origin`) **plus** `<origin>/blank.html` for each (MSAL silent token refresh runs
     in a hidden iframe there; without it you get `AADSTS50011` after idle). Record the client ID.
  2. **API permissions** → My APIs → `cop-api-<env>` → Delegated → `access_as_user` → Add → **Grant
     admin consent**.

### D. Bootstrap `Admin` assignment (direct user app-role)

- **What:** the first admin's authority — an `Admin` app-role assignment placed **directly on the
  user** (not a group; a group needs Entra ID P1, ADR-0011).
- **Why:** without it no one is an admin, so `require_admin` can never pass and the portal can't
  provision anyone else. This bootstraps the chain; from Stage 5 the portal creates/removes these
  assignments via Graph.
- **Steps:** Enterprise applications → `cop-api-<env>` → Users and groups → Add assignment → select
  your user → role **Portal Admin** → Assign. Record who you assigned. (Admins are B2B guests homed in
  the corporate tenant — invite the guest first if needed.)

### E. Graph caller app registration (`cop-graph-<env>`) — Stage 5

> **⚠️ Architecture correction — `AADSTS700236` (read before building this app).**
> Microsoft Entra **does not allow an app registration to federate to a managed identity that lives in
> a different tenant.** The Graph-caller app therefore **must be registered in the same tenant as the
> UAMI — the resource/corporate tenant `3c2c919b…`** — as a **multitenant** app, and then **provisioned
> (admin-consented) into the identity tenant `0ef950c5…`**, where it holds its Graph permissions and
> runs its Graph calls. The **original design** (a single-tenant app registered *in the identity
> tenant* trusting the resource-tenant UAMI) is **unsupported**: the secretless token exchange fails at
> the identity tenant's token endpoint with
> `AADSTS700236: Entra ID tokens issued by issuer 'https://login.microsoftonline.com/3c2c919b-…/v2.0'
> may not be used for federated identity credential flows for applications or managed identities
> registered in this tenant.`
> Authority: Microsoft Learn — [Configure an application to trust a managed identity](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity)
> ("the app registration **must belong to the same tenant as the managed identity**… if you need to
> access resources in another tenant, your app registration **must be a multitenant application and
> provisioned into the other tenant**"). **No application code changes** — only the Entra object
> placement and the `GRAPH_CLIENT_ID` value change.

- **What:** a dedicated **multitenant confidential client, registered in the resource/corporate tenant**
  (the **same** tenant as the Container App's UAMI), that the **backend authenticates as** to call
  Microsoft Graph **in the identity tenant** for provisioning (B2B invite, create/remove the `Admin`
  app-role assignment). It is **secretless**: it trusts the UAMI via a **federated identity credential
  (FIC)** — a **same-tenant** trust, which is what Entra allows — so no certificate or client secret is
  ever stored.
- **Why it must exist (and be its own app):**
  1. **Secretless cross-tenant reach, done the supported way.** The UAMI lives in the resource tenant
     and cannot call the identity tenant's Graph directly (§1). A **multitenant** app homed next to the
     UAMI can trust it via FIC (same tenant) **and** be provisioned into the identity tenant to hold
     Graph **application** permissions there. The MI alone cannot hold them.
  2. **Separation of responsibilities (why not reuse `cop-api`/`cop-spa`).** This app holds
     **tenant-wide, escalation-capable** Graph permissions (`AppRoleAssignment.ReadWrite.All` can
     assign the portal `Admin` role to anyone, ADR-0011). Keeping that power on a **dedicated**
     identity — off the public-facing audience app and off the public SPA client — isolates its blast
     radius and lets it be audited/revoked independently of inbound sign-in. The SPA is a public
     client and **cannot** safely hold app permissions at all.
  3. **Secretless.** The FIC means the only thing that can wield these permissions is the Container
     App's UAMI; there is no stored credential to leak (aligns with security-design §5.4).

- **Token-exchange flow (unchanged in code):** the Container App's UAMI gets a token from the resource
  tenant for audience `api://AzureADTokenExchange`; the backend presents it as a **client assertion** in
  a client-credentials call to the **identity tenant's** token endpoint (`GRAPH_TENANT_ID`) using the
  Graph app's client ID → the identity tenant issues an app-only token for the app's identity-tenant
  service principal → Graph provisioning runs in the identity tenant.

- **Prerequisites (from Azure, resource tenant):**
  - **Resource tenant ID:** `az account show --query tenantId -o tsv` (dev `3c2c919b-877a-4cd6-be64-b25bbdaee76f`).
  - **UAMI object (principal) ID + client ID:** deploy outputs `containerAppIdentityPrincipalId` /
    `containerAppIdentityClientId`, or `az identity show -n <id-…> -g <app rg> --query "{p:principalId,c:clientId}"`
    (dev principal `69426bc0-1524-4f77-8cad-d6932ed6a75e`). The UAMI is `infra/modules/identity.bicep`,
    named `id-<suffix>`.
  - **Identity tenant ID:** dev `0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52` (= `GRAPH_TENANT_ID`).

- **Steps — Part 1: in the RESOURCE / CORPORATE tenant (`3c2c919b…`, where the UAMI lives):**
  1. **New registration**, name `cop-graph-<env>`, account type **"Accounts in any organizational
     directory" (multitenant)**, no redirect URI. Record the **Application (client) ID**.
  2. **Federated credential** → Certificates & secrets → Federated credentials → Add → **Other issuer**
     (the "Managed identity" scenario works too; both store the same issuer/subject/audience):
     - **Issuer:** `https://login.microsoftonline.com/<RESOURCE_TENANT_ID>/v2.0`
       (dev `https://login.microsoftonline.com/3c2c919b-877a-4cd6-be64-b25bbdaee76f/v2.0`)
     - **Subject:** `<UAMI object/principal ID>` (dev `69426bc0-1524-4f77-8cad-d6932ed6a75e`)
     - **Audience:** `api://AzureADTokenExchange`
     - Name/description: e.g. `cop-api-uami-<env>`.
  3. **API permissions** → Microsoft Graph → **Application permissions** — declare (consent is granted
     in Part 2, in the identity tenant):
     - `User.Invite.All` — issue B2B guest invitations.
     - `AppRoleAssignment.ReadWrite.All` — create/remove the `Admin` app-role assignment.
     - `User.ReadWrite.All` — delete the guest object on hard-delete / revoke (Stage 6, §E.1).
     - `User.Read.All` — read a user's `appRoleAssignments` for demote/deactivate (Stage 6, §E.1).
     - `Application.Read.All` — list the API SP's `appRoleAssignedTo` (admin user list). Without it
       `GET /admin/users` fails with a Graph 403.
     Add **no** client secret or certificate.

- **Steps — Part 2: provision + consent in the IDENTITY tenant (`0ef950c5…`, where Graph runs):**
  4. An **identity-tenant admin** provisions the app's service principal there and grants admin
     consent in one step by opening the admin-consent URL **while signed into the identity tenant**:
     `https://login.microsoftonline.com/<IDENTITY_TENANT_ID>/adminconsent?client_id=<GRAPH_APP_CLIENT_ID>`
     (dev: `https://login.microsoftonline.com/0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52/adminconsent?client_id=<GRAPH_APP_CLIENT_ID>`).
     This creates the **enterprise application (service principal) in the identity tenant** and consents
     the four Graph application permissions above **for that tenant**.
  5. In the identity tenant → **Enterprise applications** → `cop-graph-<env>` → record its **Object
     ID** (this is the identity-tenant SP, not the resource-tenant app object). Confirm **Permissions**
     shows the four Graph app roles as **granted for <identity tenant>**.
  6. Record the Graph-caller **client ID** (from Part 1) and **identity-tenant SP object ID** into §2
     and the plan's reference table. **Delete** the old superseded single-tenant `cop-graph-dev`
     (`c997ea30…`) from the identity tenant to avoid confusion.

- **Optional CLI equivalent** (two sign-ins; Graph = `00000003-0000-0000-c000-000000000000`):
  ```bash
  # ----- Part 1: RESOURCE/CORPORATE tenant (3c2c919b…) -----
  az login --tenant 3c2c919b-877a-4cd6-be64-b25bbdaee76f
  az ad app create --display-name cop-graph-dev --sign-in-audience AzureADMultipleOrgs
  APP_ID=$(az ad app list --display-name cop-graph-dev --query "[0].appId" -o tsv)
  az ad sp create --id "$APP_ID"   # service principal in the resource tenant

  # Federated credential — SAME-tenant trust of the UAMI (this is what makes it supported)
  az ad app federated-credential create --id "$APP_ID" --parameters '{
    "name": "cop-api-uami-dev",
    "issuer": "https://login.microsoftonline.com/3c2c919b-877a-4cd6-be64-b25bbdaee76f/v2.0",
    "subject": "69426bc0-1524-4f77-8cad-d6932ed6a75e",
    "audiences": ["api://AzureADTokenExchange"]
  }'

  # Declare the Graph application permissions (well-known Graph app-role GUIDs)
  az ad app permission add --id "$APP_ID" --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions 09850681-111b-4a89-9bed-3f2cae46d706=Role \
                      06b708a9-e830-4db3-a914-8e69da51d44f=Role \
                      741f803b-c850-494e-b5df-cde7c675a1ca=Role \
                      df021288-bdef-4463-88db-98f22de89214=Role

  # ----- Part 2: IDENTITY tenant (0ef950c5…) — an identity-tenant admin -----
  # Preferred: open the admin-consent URL in a browser signed into the identity tenant:
  #   https://login.microsoftonline.com/0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52/adminconsent?client_id=<APP_ID>
  # CLI alternative (provision the SP, then consent in the identity tenant):
  az login --tenant 0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52 --allow-no-subscriptions
  az ad sp create --id "<APP_ID>"                     # SP in the identity tenant
  az ad app permission admin-consent --id "<APP_ID>"  # consent for the identity tenant
  ```

- **Backend config (agent/coding, not Entra):** the backend reads these non-secret values as
  container env vars (wired in `infra/resources.bicep`; see `api/.env.example`). No secret is stored —
  the FIC replaces any credential.
  - `GRAPH_TENANT_ID` — **identity tenant** ID (where the app is provisioned and Graph runs); the
    token exchange POSTs to this tenant's token endpoint. Dev `0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52`.
  - `GRAPH_CLIENT_ID` — the `cop-graph-<env>` application (client) ID **of the app registered in the
    resource/corporate tenant** (§3.E Part 1). **This value changes** with the corrected architecture —
    update it (env var wired in `infra/resources.bicep` / `main.bicepparam` `entraGraphClientId`) and
    redeploy/restart the Container App.
  - `GRAPH_API_SP_OBJECT_ID` — the **API app's** service-principal (enterprise app) object ID in the
    identity tenant: the `appRoleAssignedTo` target for granting the `Admin` role (§2 row above). Fetch
    from identity tenant → Enterprise applications → `cop-api-<env>` → **Object ID**. Blank disables
    admin-role assignment only; **user** invitations work without it.
  - `GRAPH_ADMIN_APP_ROLE_ID` — the `Admin` app-role ID on `cop-api-<env>` (dev:
    `d9ca4663-5e3a-41d0-84af-fb97b4becbf1`).
  - `GRAPH_AUTHORITY_HOST` — OIDC authority host (workforce default `login.microsoftonline.com`).
  - `AZURE_CLIENT_ID` — the UAMI client ID (already set for SQL); selects the identity that mints the
    token-exchange assertion. The invite redirect URL reuses `STATIC_WEBAPP_URL` unless
    `INVITE_REDIRECT_URL` is set.

### E.1 Additional Graph permissions for lifecycle management — Stage 6

Stage 6 (admin user-lifecycle: resend, revoke, edit access, promote/demote, deactivate, delete) adds
**two** Microsoft Graph **application** permissions to the **same** `cop-graph-<env>` app registration
created in §E (registered in the resource/corporate tenant, multitenant). Nothing else about that app
changes (same FIC, same secretless model). A human must add them on the app registration (resource
tenant) and **grant admin consent in the identity tenant** (the SP provisioned there, §3.E Part 2)
before dev testing. If you followed the corrected §3.E runbook these two are already declared and
consented alongside the Stage 5 pair; this section remains for the incremental upgrade path.

- `User.ReadWrite.All` (`741f803b-c850-494e-b5df-cde7c675a1ca`) — **delete the Entra B2B guest
  object** when an admin hard-deletes a user or revokes a still-pending invitation (Graph has no
  separate "cancel invitation" API; both delete the guest, `authentication-and-access.md` §6).
- `User.Read.All` (`df021288-bdef-4463-88db-98f22de89214`) — **read a user's `appRoleAssignments`** to
  locate the `Admin` assignment that must be removed on **demote** and **deactivate**. (This was listed
  _optional_ in §E step 3 for re-invite de-dup; Stage 6 makes it **required**.) Removing the assignment
  itself still uses `AppRoleAssignment.ReadWrite.All`, already granted in Stage 5.

- **Optional CLI equivalent** — declare on the app registration in the **resource/corporate tenant**
  (`APP_ID` = `cop-graph-<env>` Application ID; Graph = `00000003-0000-0000-c000-000000000000`), then
  **admin-consent in the identity tenant** (the SP provisioned per §3.E Part 2):
  ```bash
  # Resource/corporate tenant — declare the two extra permissions
  az login --tenant 3c2c919b-877a-4cd6-be64-b25bbdaee76f
  az ad app permission add --id "$APP_ID" --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions 741f803b-c850-494e-b5df-cde7c675a1ca=Role \
                      df021288-bdef-4463-88db-98f22de89214=Role
  # Identity tenant — consent (preferred: the adminconsent URL from §3.E Part 2)
  az login --tenant 0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52 --allow-no-subscriptions
  az ad app permission admin-consent --id "$APP_ID"
  ```

- **No new backend config/env.** The lifecycle code reuses the Stage 5 Graph wiring
  (`GRAPH_API_SP_OBJECT_ID`, `GRAPH_ADMIN_APP_ROLE_ID`, `GRAPH_*`); only the two consents above are new.

### F. Planned Entra objects (later stages)

Documented here for completeness; build when the stage lands.

- **ADF client app (`cop-adf-<env>`) — Stage 9.** A separate confidential client holding **only** the
  `Extract.Read` app role on `cop-api-<env>`, authenticating with a **certificate** (ADF cannot use
  workload-identity federation for REST/Web linked services — ADR-0006). Certificate lives in Key
  Vault; add the appid to `entraAllowedApplications`. Detail: `authentication-and-access.md` §10.
- **Sign-in security (Cross-tenant access + Conditional Access) — Stage 7.** Inbound **MFA trust**
  from the corporate tenant, app-based MFA for customers, session lifetimes, CAE on, legacy auth
  blocked, non-persistent sessions — **scoped to this portal's cloud apps** because the tenant hosts
  multiple apps. **Full step-by-step runbook in §3.G below.** Design detail:
  `authentication-and-access.md` §5.

### G. Sign-in security policies (Conditional Access) — Stage 7

- **What:** the Conditional Access (CA) policies **+** cross-tenant access settings that enforce the
  §5 sign-in posture of [`authentication-and-access.md`](./authentication-and-access.md):
  phishing-resistant MFA for admins, app-based MFA for customers, 8h/24h session lifetimes, **CAE on**,
  legacy auth blocked, non-persistent browser sessions.
- **Why:** customer secrets now live in our DB, so sign-in is a primary control (security-design R4).
- **Why app-scoped:** the identity tenant hosts **more than one application** (§1), so **every policy
  targets this portal's cloud apps** — other apps in the tenant keep their own policies. The **one**
  exception is the inbound MFA trust, which is per **partner organization**, not per app.
- **Where:** the **identity tenant** at [entra.microsoft.com](https://entra.microsoft.com), unless a
  step says the corporate tenant.

> **Target apps for every Conditional Access policy below:** `cop-api-<env>` **and** `cop-spa-<env>`
> (Target resources → Cloud apps → **Select apps**). **Never** *All cloud apps*.

> **How CA tells admins from customers.** Both are B2B guests, so the policies key on **home
> organization**: admins are guested from the **9altitudes corporate tenant** (`3c2c919b-877a-4cd6-be64-b25bbdaee76f`),
> customers from any other org. The admin policy selects *that* tenant under the external-user
> "specify organizations" option; the customer policy targets all **other** guests. If you later need
> finer control, back admin targeting with a group and target the group instead.

**Steps**

0. **Prerequisites**
   - Record the **corporate tenant ID** (§2) — needed for the inbound trust and the admin policy.
   - Protection → **Authentication methods** → Policy: enable **Microsoft Authenticator** (push +
     passkey) and/or **Passkey (FIDO2)** for the targeted users so a compliant factor exists.
   - **Break-glass:** before enabling any policy, create/confirm at least one cloud-only
     emergency-access account and **exclude it from every policy** (standard CA safety).

1. **Cross-tenant inbound MFA trust** _(per partner org — NOT app-scoped)_
   - External Identities → **Cross-tenant access settings** → **Organizational settings** → **Add
     organization** → enter the 9altitudes corporate tenant (ID `3c2c919b-…` or its domain).
   - Open that org → **Inbound access** → **Trust settings** → tick **"Trust multifactor
     authentication from Microsoft Entra tenants"** (optionally also "Trust compliant devices" /
     "hybrid Azure AD joined devices") → **Save**.
   - Effect: an admin who already satisfied MFA at the corporate tenant is **not re-challenged** here;
     our CA sees the MFA claim as satisfied.

2. **Authentication strengths** (Protection → Authentication methods → **Authentication strengths**)
   - **Admins:** use the built-in **"Phishing-resistant MFA"** strength (passkey / WHfB / cert).
   - **Customers:** **Add** a custom strength, e.g. *"App-based MFA (no SMS/OTP)"*, allowing **only**
     **Microsoft Authenticator (push)**, **passkey / FIDO2**, and **WHfB** — **exclude SMS, Voice, and
     email OTP** (phishable / SIM-swappable). Save.

3. **CA policy — Admins: phishing-resistant MFA** _(app-scoped)_
   - New policy, e.g. `COP-<env>-Admins-PR-MFA`.
   - Assignments → Users → Include → **Guest or external users** → **B2B collaboration guest users**
     → under "specify organizations" pick the **9altitudes corporate tenant**. **Exclude** break-glass.
   - Target resources → Cloud apps → **Select apps** → `cop-api-<env>`, `cop-spa-<env>`.
   - Grant → **Require authentication strength** → **Phishing-resistant MFA**.
   - Session → **Sign-in frequency** → **8 hours** (periodic); **Persistent browser session** →
     **Never persistent**.
   - Start in **Report-only**; switch **On** after step 7.
   - > **Caveat:** authentication-strength enforcement for guests relies on the home tenant signalling
     > the method via MFA trust. If the phishing-resistant claim isn't passed through and admins get
     > blocked, require the base **"Multifactor authentication"** strength here and let the **corporate
     > tenant** enforce the phishing-resistant method.

4. **CA policy — Customers: app-based MFA** _(app-scoped)_
   - New policy, e.g. `COP-<env>-Customers-MFA`.
   - Assignments → Users → Include → **Guest or external users** (B2B guests) → **Exclude** the
     corporate tenant (covered by step 3) and break-glass.
   - Target resources → Cloud apps → **Select apps** → `cop-api-<env>`, `cop-spa-<env>`.
   - Grant → **Require authentication strength** → **App-based MFA (no SMS/OTP)** (step 2).
   - Session → **Sign-in frequency** → **24 hours**; **Persistent browser session** → **Never
     persistent**.
   - Report-only first, then **On**.

5. **CA policy — Block legacy authentication** _(app-scoped)_
   - New policy, e.g. `COP-<env>-Block-Legacy`.
   - Users → all guests (minus break-glass); Target resources → the two `cop-*` apps; Conditions →
     **Client apps** → tick **Exchange ActiveSync clients** + **Other clients**; Grant → **Block
     access**.

6. **Continuous Access Evaluation (CAE)**
   - CAE is **on by default** for supporting resources — do **not** disable it. In each policy's
     **Session** tab leave **"Customize continuous access evaluation"** at its default (enabled), or set
     it explicitly to **Enable**. This makes Stage 6 de-provisioning (deactivate / unlink / disabled
     user) take **near-real-time** effect instead of waiting for token expiry.

7. **Verify (the Stage 7 review gate)**
   - **Admin guest:** sign in → confirm **no second MFA prompt** in our tenant (inbound trust
     honoured), access granted, re-auth after ~8h, session not persisted.
   - **Customer guest:** sign in → confirm **app-based MFA is required** and **SMS / email OTP is not
     offered** as the factor; re-auth after ~24h; session not persisted.
   - Confirm a **legacy-auth** attempt is **blocked**.
   - With Stage 6 wired, **deactivate** a test user and confirm access is cut **near-real-time** (CAE).
   - Flip both MFA policies from **Report-only** to **On** once verified.

8. **Record** — note the enacted policy names/IDs and the custom strength here and in the plan's
   Stage 7 review notes (all non-secret).

---

## 4. Responsibilities matrix — why each stays separate

| App registration | Single responsibility | Holds a credential? | Holds Graph app permissions? | Inbound or outbound |
|---|---|---|---|---|
| `cop-api-<env>` | Resource server / token audience; **defines** app roles | No | No | Inbound (validated by platform) |
| `cop-spa-<env>` | Public client for interactive user sign-in (MSAL/PKCE) | No (public client) | No | Inbound (acquires user tokens) |
| `cop-graph-<env>` | Backend's identity for **outbound** Graph provisioning (multitenant app in the **resource/corporate tenant**, provisioned into the identity tenant — §3.E) | **FIC to UAMI** (same-tenant, no stored secret) | **Yes** — tenant-wide, escalation-capable (consented in the identity tenant) | Outbound (calls Graph) |
| `cop-adf-<env>` (Stage 9) | Machine reporting caller; holds `Extract.Read` only | Certificate (Key Vault) | No | Inbound (machine → API) |

Merging any two would either (a) put high-privilege Graph power on a public-facing or public-client
app, or (b) force a public client to hold a credential — both widen blast radius for no benefit. One
identity, one job.

---

## 5. Prod go-live checklist

1. Create the **prod identity tenant** (§3.A) — separate from dev; self-service sign-up off.
2. Capture the **prod resource tenant ID** (`az account show`) and deploy infra so the **prod UAMI**
   exists; record its principal/client IDs.
3. Create `cop-api-prod` (§3.B) with `access_as_user` + `Admin`/`Extract.Read` roles; record IDs.
4. Create `cop-spa-prod` (§3.C) with prod SPA origin(s); grant delegated consent.
5. Bootstrap your **direct `Admin` assignment** on `cop-api-prod` (§3.D).
6. Create `cop-graph-prod` (§3.E) **in the prod resource/corporate tenant** as a **multitenant** app
   with a FIC to the **prod UAMI** (same tenant); then **provision + admin-consent it into the prod
   identity tenant** with the four Graph app permissions; set `GRAPH_CLIENT_ID` to the new app and
   `GRAPH_TENANT_ID` to the prod identity tenant; record IDs.
7. _(Stage 7)_ Configure cross-tenant MFA trust + Conditional Access in the prod identity tenant,
   **app-scoped to `cop-api-prod` / `cop-spa-prod`** — follow §3.G.
8. _(Stage 9)_ Create `cop-adf-prod`, assign `Extract.Read`, store its certificate in Key Vault, add
   the appid to `entraAllowedApplications`.
9. Fill every **prod** cell in §2 and thread the non-secret IDs into
   `infra/environments/prod/main.bicepparam` (via `main.bicep` → `resources.bicep`).

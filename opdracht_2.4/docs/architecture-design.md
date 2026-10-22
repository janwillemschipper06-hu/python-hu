# Architecture & Technical Design

This document captures technical/architectural decisions. Functional scope (what the app does for admins and customers) lives in `docs/functional-design.md`.

## 1. Template Authoring

Requirement templates are authored as files in this git repository, not through an in-app editor. Admins are technical (BI background) and already comfortable with GitHub and GitHub Copilot, so authoring/editing templates happens via normal PRs.

### 1.1 File Layout

Each template is a folder containing one shared structure file and one content file per supported language:

```
templates/entra-app-registration/
  template.yml   ← shared structure: id, category, field definitions, estimated time, required role
  en.md          ← English instructions + field labels
  nl.md          ← Dutch instructions + field labels
  da.md          ← Danish instructions + field labels
  images/
    en/          ← screenshots for the English instructions
    nl/          ← screenshots for the Dutch instructions
    da/          ← screenshots for the Danish instructions
```

- `template.yml` holds everything that is **not** language-specific: field `key`, `type`, `required`, `category`, `estimatedTimeMinutes`, `requiredRole` (free text), and an internal `version`. A `secret` field is marked simply with `type: secret` and needs **no extra vault mapping** — its value is stored encrypted in the database, keyed by project/task/field (see §1.2.1).
- Each language `.md` file holds only translated content: title, "why required", numbered step-by-step instructions, "how to verify", "common mistakes", and the label text for each field (keyed by field `key`, e.g. `tenantSettingValue: "Confirm the setting value"`). Field render order follows the field order in `template.yml`.
- No inline field markers in the Markdown body — instructions render first, then all fields render together below, in the order defined in `template.yml`. This is simpler to write/review/translate than interleaving fields mid-paragraph.

### 1.1.1 Instruction Steps & Images

- Instructions are written as an ordered (numbered) Markdown list — the numbering is the step number the customer sees.
- Steps can embed images (screenshots) using standard Markdown image syntax, referencing files in the template's **per-language** `images/{lang}/` folder (e.g. `en.md` uses `![Click New registration](images/en/new-registration.png)`). Images are **per language, not shared** — a screenshot is taken of the UI in that language, so English, Dutch, and Danish screenshots of the same step are separate files. Each language's images still ride along in the same published version bundle as its `.md` file, so a step's screenshot is frozen with the same version as its text.

### 1.2 Field Types

Fixed enum, validated by CI:

- `text` — plain value, may be viewed/edited later by the customer.
- `secret` — sensitive value; customer can submit or replace, never view. Stored as **ciphertext in Azure SQL under application-layer envelope encryption** (AES-256-GCM per-value DEK wrapped by an HSM KEK in Key Vault); revealed only via the audited admin-reveal and pipeline-consume paths (see `docs/security-design.md` §3).
- `checkbox` — boolean confirmation.

There is no `file` type — file upload/evidence collection is not part of this application at all.

#### 1.2.1 Storage of `secret` fields

A `secret` field carries **no extra mapping block** — it is declared like any other field, only with `type: secret`:

```yaml
fields:
  - key: clientSecret
    type: secret
    required: true
```

- On submission the backend encrypts the value (AES-256-GCM under a per-value DEK wrapped by the Key Vault KEK) and stores the **ciphertext + nonce + wrapped DEK + metadata** in a **separate secrets table/schema** in Azure SQL, keyed by (project, task, `fieldKey`) — behind the EXECUTE-only stored-procedure boundary (`docs/adr/0002`, `docs/security-design.md` §3).
- There is no external vault, no folder/entry addressing, and no per-field vault mapping to author or validate. Replacing a secret overwrites its ciphertext in place (no plaintext history), and the daily/completion purge crypto-erases it (`security-design.md` §3.3).

### 1.3 Fixed Enums

Defined in a shared config file, validated by CI (reject unknown values):

- **Supported languages**: `en`, `nl`, `da`.

`category` (e.g. Microsoft Entra ID, Microsoft Fabric/Power BI, Azure, Azure DevOps/GitHub, Networking, Security & Compliance) is **free text, not a fixed enum** — same treatment as `requiredRole` — so admins can introduce a new category by just typing it, without a CI enum update.

`requiredRole` (which role on the customer side should do the task) is also free text — customer org role titles are outside our control, so an enum isn't useful there.

There is no risk-level concept — it was dropped as unnecessary.

### 1.4 No Task Dependencies

Templates do not declare dependencies on other templates. There is no "blocked until a prerequisite task is approved" concept — every assigned task is independently workable as soon as the project starts.

## 2. CI Validation

A CI check runs on every PR that touches `templates/`:

- Every template folder must contain a `.md` file for **every** supported language (`en`, `nl`, `da`). Missing a language file for a template fails the PR check — the deploy is blocked until it's added (content quality/accuracy of the translation is not machine-checked, only file presence).
- `template.yml` field `type` values must match the fixed enum (`text`/`secret`/`checkbox`) — unknown values fail the check. `category` is free text and is not enum-validated.
- A `secret` field requires only `type: secret` — there is **no** `secret:`/vault-mapping block to validate (§1.2.1); the CI check simply confirms the `type` is one of the fixed enum values.

This enforces completeness before merge, so nothing incomplete ever reaches `main`.

## 3. Publishing & Versioning

The application does **not** read template content directly from git at runtime. Reading from git directly would let unvalidated commits on `main` (e.g. a bad direct push) leak into production between merge and any post-merge validation. Instead:

1. PR opened against a template folder.
2. CI validates completeness/enum correctness (see above) — must pass before merge.
3. PR merged to `main`.
4. A deployment pipeline detects the change and publishes a new **immutable versioned bundle** (the whole template folder — `template.yml` + all language `.md` files + `images/` together) as a new version folder deployed as part of the frontend Static Web App's own static assets (see §5 Hosting & Compute) — there is no separate storage account for this. The whole folder is versioned as one atomic unit — there is no independent versioning of individual files (e.g. translating Danish again does not bump only "the Danish version"; it produces a new version of the whole template).
5. **The same pipeline step also writes `template.yml`'s field definitions into Azure SQL** — one row per field (`templateId`, `version`, `fieldKey`, `fieldType`, `required`, `displayOrder`), plus one row for the template version itself (`category`, `estimatedTimeMinutes`, `requiredRole`). No vault-mapping columns exist — a `secret` field is stored encrypted in the DB keyed by (project, task, field), with no folder/entry addressing (§1.2.1). This is what lets the backend Container App validate field submissions (§7, `docs/api-design.md`) without trusting the frontend/browser for schema — the browser never gets to declare what fields exist or what type they are, only the database (populated straight from the git-sourced `template.yml` by this pipeline) does.
6. **A published version folder is never edited or deleted in place.** The publish pipeline only ever adds a new version folder (`v1/`, `v2/`, `v3/`...); it must never modify or remove an existing one. This is what makes "frozen forever" (§3.1) actually hold — every future deploy of the app still ships every historical version folder alongside the newest, so a project frozen to `v1` keeps working even after `v3` is published and the app has been redeployed many times since.
7. Once published, a new template version becomes selectable for **new** project task assignments. Existing in-progress projects are unaffected.

### 3.1 Versioning Granularity

- Each template has its own independent version counter (e.g. `entra-app-registration` v1, v2, v3...). Editing one template does not bump the version of any other template.
- When an admin creates a project and selects a task, the project stores which exact template version was used at that moment.
- Template versions are **frozen forever** once assigned to a project — there is no "upgrade this task to the latest template version" action. If a template is fixed/improved later, only new projects pick up the change; existing assigned tasks keep the version they were created with, for consistency and clean audit history.

## 4. Prototype Validation

The template-rendering approach in this document was validated with a throwaway prototype (React reads `template.yml` + `.md`, renders the wizard, writes input to JSON). See `docs/prototype-lessons-learned.md` for the outcome and the practical lessons for building the real thing.

## 5. Hosting & Compute

- **Frontend**: Azure Static Web App. Hosts the React app (one application, two role-based views — admin and customer wizard, gated client-side by signed-in role) and the accumulating task-template version folders as static assets (§3). No separate Storage Account needed for template content — it ships as part of the SWA's own static assets.
- **Backend**: Azure Container Apps, hosting the Data API only (no UI). Separate from the frontend now that the frontend is a Static Web App.
- **Container Apps Environment (CAE)**: reused from the existing shared dev/prod CAEs already used by other projects — this project adds a new Container App into the existing environment, it does not provision a new CAE.
- **Container registry**: reuses the existing shared ACR — no new registry.
- **Identity for image pull**: the Container App pulls its image using a **user-assigned managed identity (UAMI)** provisioned in the app resource group (`id-cst-cop-<env>`). The UAMI is created first, so its `principalId` is known before the Container App exists; its `AcrPull` role assignment on the shared ACR is applied before the Container App provisions, and the whole stack deploys in a **single pass** — no ordered second step. The same UAMI is also granted `Key Vault Secrets User` on the app Key Vault, so all app-to-Azure access flows through one identity. (This reverses the earlier system-assigned + two-phase choice; see `docs/adr/0003-user-assigned-identity-single-pass-deploy.md`.)

## 6. Networking

- **VNet**: this project does **not** provision its own VNet. It reuses the existing shared dev and shared prod VNets already used by other projects (separate VNet per environment, already in place).
- **No new subnet required**: the Container App is added to the existing shared CAE (already VNet-integrated), and the new Azure SQL database is added to the existing shared SQL Server (already network-configured) — both inherit the existing network setup rather than needing new subnets or private endpoints of their own.
- **Frontend stays public.** The Static Web App is served publicly/globally as normal — its content (UI code, task-template instructions/images) is non-sensitive, so it needs no VNet integration or private endpoint.
- **Access via APIM, no direct public path to the Container App.** The Container App's ingress is set to **Internal only** — it is not reachable directly from the public internet. All API traffic (from the browser-hosted frontend, admin UI, and the ADF extraction API) goes through the existing **shared APIM instance** (reused from other projects, same pattern as the shared CAE/SQL Server), which is already VNet-integrated/peered into the same network and reaches the Container App privately. APIM is the only public entry point for the API; this project just adds its API routes/products to the shared instance rather than provisioning a new one.
- Outbound calls from the Container App to the shared SQL Server happen over the existing VNet integration.
- No separate Storage Account, and therefore no private endpoint for one, is needed for this project — see §7.

## 7. Data Storage

- **Azure SQL**: a new dedicated database is provisioned on the existing shared SQL Server (reused, not a new server). Holds all customer-specific and portal-managed data: customers, people/contacts, projects, tasks, task status/assignment, submitted non-secret field values, **encrypted secret values** (ciphertext in a separate secrets table/schema under application-layer envelope encryption — the KEK lives in Key Vault, never in the DB; see `docs/security-design.md` §3), project templates (see below), comments, notifications, and audit history.
- **Task template field metadata** is also indexed into Azure SQL (`templateId`, `version`, `fieldKey`, `fieldType`, `required`, `displayOrder`, plus one row per template version for `category`/`estimatedTimeMinutes`/`requiredRole`), written by the same publish pipeline that ships the version folder to the frontend Static Web App (§3). This is the backend Container App's sole authority for input validation — e.g. confirming task 43's `entra-secret` field exists for its frozen template version and is of type `secret` — independent of anything the browser sends. No vault-mapping columns exist (§1.2.1). See `docs/api-design.md` for the validation flow.
- **No Storage Account for template content.** Task templates (`template.yml`/`.md`/`images/`) are non-sensitive, generic content, so they ship as static assets in the frontend Static Web App — versioned as accumulating, never-edited folders (see §3). This removes the need for a separate storage account, private endpoint, or public/private access tradeoff for template content entirely.
- **Project templates are portal-managed, not git-authored** — unlike task templates. Admins create/edit them live in the app (name, description, bundled task-template id+version refs), so they're rows in Azure SQL rather than files in git. See `functional-design.md` §13.
- **No generated-report storage.** The per-project onboarding summary report (`functional-design.md` §4/§5) is generated on demand from Azure SQL data and rendered client-side — there's no PDF generation step or stored report artifact.

### 7.1 Data Access — Stored Procedures Only

- **All database access from the backend goes through stored procedures — never ad-hoc SQL.** No `SELECT`/`INSERT`/`UPDATE`/`DELETE` strings are composed in Python; every read and write calls a named stored procedure. This is the application-code counterpart to the EXECUTE-only *grant* boundary in `docs/adr/0002`, recorded as a decision in `docs/adr/0008`.
- **Two data-access primitives over one execution core.** The backend exposes
  `execute_procedure(proc, params) -> pandas.DataFrame` and `query_procedure(proc, model, params) ->
  list[Model]` (`api/app/core/db.py`), both built on a private `_run_procedure` helper that
  opens the managed-identity connection (§8), runs the named procedure with bound ODBC parameters,
  and fetches its result set (empty when the procedure returns none). `execute_procedure` returns the
  rows as a `pandas.DataFrame`; `query_procedure` validates them straight into a Pydantic model so a
  service can hand a result set to an API response without a hand-written column map. Services build
  their Pydantic/response models from those results — they never open a connection, hold a cursor, or
  build SQL themselves.
- **Allow-listed and injection-safe.** The primitive only runs procedures named in `ALLOWED_PROCS` — the procedure name is the one token that cannot be a bound parameter — and every argument is passed as a parameter marker.
- **Failures are logged at the data layer.** `_run_procedure` logs the failing procedure name and re-raises; the app's catch-all middleware (`api/app/core/errors.py`) then returns a JSON 500 with CORS headers intact. Adding a data path is therefore always: author a stored procedure, grant `EXECUTE`, and call `execute_procedure` or `query_procedure` — a deliberate, reviewable step.
- **Grants match the rule.** The Container App's SQL principal is granted `EXECUTE ON SCHEMA::onboarding` (no `db_datareader`, no direct table rights); ownership chaining lets the schema-owned procedures read/write the schema-owned tables. Stored procedures use `SET NOCOUNT ON` so their result set is exactly what the primitive fetches.

## 8. Identity & Authentication

- **All humans are B2B guests** in a **dedicated workforce Entra identity tenant** created for this portal (separate from the 9altitudes corporate directory and from the resource tenant). Access is **invite-only** — self-service sign-up is disabled.
- **Admins**: B2B guests homed in the **9altitudes corporate tenant** (they authenticate there with corporate MFA; the identity tenant honours it via cross-tenant inbound MFA trust). Admin authority is a **direct `Admin` app-role assignment** on their user (an `appRoleAssignment` on the API app; no group, no Entra ID P1 — see [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)), carried in the signed token — never a DB flag. Admins are invited/managed from the portal via Microsoft Graph.
- **Customers**: B2B guests invited (never self-registered) from their own organizations. A `User` row is created by the invite; access to a specific customer is controlled entirely by admin action — an admin links a `User` to a `Customer` (via `UserCustomers`) before that user can see anything, after out-of-band identity verification. A `User` can be linked to more than one `Customer` (e.g. an IT partner working with several). See `api-design.md` §"Access control & provisioning" and `docs/authentication-and-access.md` for the full model and endpoints.
- **ADF/reporting extraction API** (`functional-design.md` §14): a **separate client app registration** authenticating with a **certificate** (client-credentials) — no static API keys; the reporting role (`Extract.Read`) carries no secrets, and the provisioning pipeline uses a distinct `Secret.Consume` role. See `docs/authentication-and-access.md` §10.

## 9. API Design

The full API surface (endpoints, request/response shapes, auth per route) is specified in [`docs/api-design.md`](./api-design.md). Summary of the shape:

- **REST over HTTPS**, JSON, **URL path versioning starting at `v1`** (`/api/v1/...` — see `docs/api-design.md`).
- **Cursor/token-based pagination** for all list endpoints.
- One **Data API** backs both the Static Web App frontend (called from the browser via APIM) and the ADF extraction API (`functional-design.md` §14) — same backend, different auth per route (portal session vs. service-principal).
- Task template *content* (instructions/images) is never served through the API — the frontend Static Web App already has it as static assets (§3, §5). The API only ever returns structure (task list, status) and customer-specific data (submitted values), never template content itself.

## 10. Open Questions

- None. The deployment pipeline that publishes new task-template version folders runs on **Azure DevOps Pipelines** (see `docs/security-design.md` §15). Full security architecture — secret handling, identity hardening, network, and compliance — is specified in `docs/security-design.md`.

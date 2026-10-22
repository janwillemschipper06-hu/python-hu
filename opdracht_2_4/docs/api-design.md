# API Design

This document specifies the backend API surface. See `docs/architecture-design.md` for hosting/networking/storage
context, `docs/functional-design.md` for what the product does, and `docs/authentication-and-access.md` for the full
identity, authorization, and secret-handling design (the authority for the "Auth models" and "Access control"
sections below).

## Conventions

- **Protocol**: REST over HTTPS, JSON request/response bodies.
- **Entry point**: all calls (browser-hosted Static Web App frontend, and the ADF/machine callers) go through the
  shared APIM instance — the backend Container App itself has no direct public path (architecture-design.md §6).
  APIM is the single gateway for every route in this document.
- **Versioning**: URL path versioning, starting at `v1` (e.g. `/api/v1/...`). Bump the path segment (`/api/v2/...`)
  for breaking changes; additive/non-breaking changes don't require a bump.
- **Three routers, guarded at the router level.** Every route lives under one of three prefixes, each carrying a
  mandatory router-level guard (deny-by-default) so no endpoint can be accidentally under-protected
  (`authentication-and-access.md` §4, [ADR-0006](./adr/0006-three-router-authorization-and-adf-certificate.md)):
  - **`/api/v1/admin/*`** — admins only (`Admin` app-role claim); all-scope.
  - **`/api/v1/portal/*`** — a customer-scoped guest **or** an admin acting within the customer named in the request.
  - **`/api/v1/extract/*`** — machine callers only (service principal, certificate auth, APIM `appid` allowlist).
- **Pagination**: cursor/token-based for all list endpoints; a `nextCursor` field is returned when more results
  exist, pass it back as `?cursor=` on the next call.
- **Template content is never served by this API.** Task template instructions/images ship as static assets in the
  frontend Static Web App (architecture-design.md §3, §5). This API only returns structure (which tasks, their
  status) and customer-specific data (submitted values) — never template content.
- **Secrets** are stored by this API as **ciphertext under application-layer envelope encryption** (AES-256-GCM
  per-value DEK wrapped by an HSM KEK in Key Vault; `security-design.md` §3,
  [ADR-0007](./adr/0007-secrets-in-database-envelope-encryption.md)). In normal responses a secret is redacted as
  `· submitted ·`; the real value is returned **only** through two authenticated, audited paths: the admin
  **reveal** endpoint (`POST /admin/secrets/reveal`, §Secret reveal) and the machine **consume** endpoint
  (`POST /extract/secrets/consume`). Request/response bodies on secret submit/reveal/consume routes are **never
  logged**.
- **Browser security headers**: responses served to the browser SPA carry a strict Content-Security-Policy and the
  supporting security headers, and the SPA never places tokens in `localStorage`. The full policy is specified in
  `docs/security-design.md` §5.5.

## Auth models

Three distinct callers, three auth mechanisms on the same backend, mapped to the three routers above. All human
identities are **B2B guests** in a **dedicated workforce Entra identity tenant** (separate from the corporate
directory and the resource tenant) — admins are guested in from the 9altitudes corporate tenant, customers from
their own organizations; a **single API app registration** is the audience, and callers are distinguished by app
role (`authentication-and-access.md` §2).

| Caller | Router | Mechanism | Notes |
|---|---|---|---|
| Admin (9altitudes staff) | `/admin/*` and `/portal/*` | Identity-tenant **B2B guest** (home: corporate tenant); `Admin` app-role claim from a **direct app-role assignment** on their user | Full access to all customers/projects. Admin authority is the signed claim, never a DB flag. |
| Customer user | `/portal/*` | Identity-tenant **B2B guest**; scope from `UserCustomers` | **Invite-only** (self-service sign-up off). Sees a customer's project(s) only once an admin links their user — see "Access control & provisioning" below. |
| Machine / ADF | `/extract/*` | **Separate client app registration**, **certificate** (client-credentials); `Extract.Read` (reporting) or `Secret.Consume` (pipeline) app role | No static API keys; no user context. APIM validates `appid` against an allowlist. |

### Access control & provisioning (invite-only)

**Self-service sign-up is disabled.** A person becomes able to use the portal **only by an admin invitation** from
the admin view. All authentication stays 100% delegated to Entra; the backend never handles credentials or issues
its own tokens. No app-generated secret link/token is ever emailed — an earlier invite-token design was rejected
because a leaked link would let anyone impersonate the invitee. Access derives only from a **verified Entra identity
plus our own `Users`/`UserCustomers` rows**; the Entra B2B redemption link (Microsoft-managed) grants only guest
directory status, not portal access.

**Data model**: a `Users` table (one row per invited identity, with a `role` of `admin`/`user`), a `Customers`
table, and a `UserCustomers` mapping table (many-to-many — a user can be linked to more than one customer). Admin
authority is **not** the `Users.role` column; it is a **direct `Admin` app-role assignment** on the user (an
`appRoleAssignment` on the API app; no group — see
[ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)) and is carried in the signed token. The
`role` column may mirror it for display only.

The **Invite** is one atomic admin action: it issues an Entra B2B guest invitation via Microsoft Graph, creates or
reuses the `Users` row, and provisions scope — `UserCustomers` links (for `role=user`) or a **direct `Admin`
app-role assignment** (for `role=admin`). Re-inviting an existing email never duplicates the identity.

```
POST /api/v1/admin/invitations
  Auth: admin.
  Body: { email, role, customerIds?, primaryContactCustomerId?, taskAssignments? }
  Behavior: the single provisioning action (see above). Atomically issues the Graph B2B invitation, creates/reuses
        the Users row (role), and provisions scope. For role=user, `customerIds` are linked (and an optional
        primary-contact customer / initial task assignments recorded); for role=admin, the invitee is assigned the
        `Admin` app role directly (on the API app) and no customer link is made. Every user↔customer link emits a **high-signal security alert**
        and an audit entry (`docs/security-design.md` §10). No secret is emailed.

GET /api/v1/admin/invitations
  Auth: admin.
  Behavior: lists invitations with status (pending / redeemed / revoked).

POST /api/v1/admin/invitations/{id}/resend
  Auth: admin.
  Behavior: re-issues the Entra B2B invitation for a pending invite. No app secret involved.

DELETE /api/v1/admin/invitations/{id}
  Auth: admin.
  Behavior: revokes a pending (unredeemed) invitation.
```

**User & access management (ongoing)** — links and roles are managed freely, not a one-time approval queue:

```
GET /api/v1/admin/users
  Auth: admin.
  Behavior: lists all invited users (email, role, sign-up/redeemed date) and which customer(s) each is linked to.

POST /api/v1/admin/users/{userId}/customer-links
  Auth: admin.
  Body: { customerId }
  Behavior: links a user to a customer after out-of-band verification. Grants access to that customer's project(s).
        Emits a high-signal alert + audit entry (`docs/security-design.md` §10).

DELETE /api/v1/admin/users/{userId}/customer-links/{customerId}
  Auth: admin.
  Behavior: removes a user's link to a customer; revokes visibility into the corresponding project(s). Does not
        delete the user account.

POST /api/v1/admin/users/{userId}/role
  Auth: admin.
  Body: { role }
  Behavior: promote/demote by creating or removing the user's `Admin` app-role assignment via Graph (the authoritative admin
        source). Audited as a role change. CAE makes a demotion take near-real-time effect.

POST /api/v1/admin/users/{userId}/deactivate
  Auth: admin.
  Behavior: soft offboarding — removes the app-role assignment; CAE cuts access
        near-real-time. The Entra guest object is retained for audit.

DELETE /api/v1/admin/users/{userId}
  Auth: admin.
  Behavior: hard offboarding — blocks/removes the Entra guest object entirely.
```

## Task templates (read-only structure, not content)

```
GET /api/v1/admin/task-templates
  Auth: admin.
  Behavior: lists available task templates (id, latest version, category). Returns id+version refs only — content
        is rendered by the frontend from its own static assets.
```

## Project templates (portal-managed, Azure SQL — see architecture-design.md §7)

```
GET /api/v1/admin/project-templates
GET /api/v1/admin/project-templates/{id}
  Auth: admin only.
  Behavior: read project template rows — name, description, bundled task-template id+version refs.

POST /api/v1/admin/project-templates
PUT /api/v1/admin/project-templates/{id}
DELETE /api/v1/admin/project-templates/{id}
  Auth: admin only.
  Behavior: create/edit/delete a project template directly in the portal. See functional-design.md §13.
```

## Customers & projects

```
GET /api/v1/portal/customers/lookup?q=&limit=25
  Auth: Admin or PM. Read-only search over the external `ext.Customer` table (ADR-0013); returns `[{id, name}]`.
  There is no customer resource and no customer write endpoint. (The `/admin/customers*` routes below are
  superseded and removed; full sync is Stage 10 of `projects-implementation-plan.md`.)

GET /api/v1/admin/customers
POST /api/v1/admin/customers
GET /api/v1/admin/customers/{id}
  Auth: admin only.

GET /api/v1/admin/customers/{id}/users
  Auth: admin only.
  Behavior: lists users currently linked to this customer (linking an existing user *is* how a customer gains a
        user — see "Access control & provisioning" above).

GET  /api/v1/portal/projects?state=&type=&customer_id=
POST /api/v1/portal/projects
GET  /api/v1/portal/projects/{id}
PATCH /api/v1/portal/projects/{id}
DELETE /api/v1/portal/projects/{id}
GET  /api/v1/portal/projects/requesters
GET  /api/v1/portal/projects/{id}/definition
PUT  /api/v1/portal/projects/{id}/installation
PUT  /api/v1/portal/projects/{id}/migration
GET  /api/v1/portal/lookups?kind=
  Auth: reads (list/get) any portal role; everything else Admin or PM (`require_staff`).
  Visibility (enforced in the stored procedures, `onboarding.VisibleProject`): staff see every Project except
        another author's `Draft`; a customer user sees only assigned Projects that are Approved/InProgress/Ready/OnHold
        (not Draft, Requested or Cancelled). A hidden Project is a 404, never a 403. Customer users get
        `hours`, `request_notes`, `rejection_reason` and the ticket ids as null.
  POST: creates a `Draft` (body: customer_id, type, name, optional requester_oid, department_id, customer_type,
        deadline, hours, request_notes). Requester defaults to the caller; another requester must hold PM/Admin
        (`GET .../requesters` lists them). 422 for unknown customer, department or requester.
  PATCH: partial header update (type is immutable; `null` clears a nullable field). The author edits a `Draft`;
        after `Draft` only an Admin may edit (409 for a PM) and each edit is audited (`UpdateProject`, changed
        field names only). Admin-only `consultant_oid` (active Admin; cannot be cleared; 403 for a PM, 422 if the
        person is not an Admin) is set here and audited; approval in Stage 5 requires it to be set.
  DELETE: Admin only, and only the Admin's own `Draft` (204); 403 for PM/customer user, 409 once submitted. Hard delete, people/connectors cascade.
  lookups: active admin-managed dropdown options (`LookupOption`), staff only; editing them is a later stage.
  Definitions (Stage 4): `GET .../definition` (any portal role that can see the Project) returns
        `{type, installation | migration}`; the other is null. `PUT .../installation` / `PUT .../migration` (staff) is a
        **full replace** of that type's definition (omitted fields are cleared) and returns the same shape; the wrong
        type for the Project is 409. Every field is optional so a `Draft` can be half-filled; completeness is checked
        at submit (Stage 5). Same lock as PATCH (author in `Draft`, then Admin only, audited as
        `SaveProjectDefinition` with changed field names; 409 for a PM). Validation (422): each lookup id must be an
        active option of the right kind; `environment_connection_other` is required for an option that allows free
        text (Other) and rejected otherwise; `teams_channel_url` must be https; at most 3 `connectors`
        (`source_system_id`, `license_count` 1-5, `companies_to_extract`, `content_pack_ids`). Family rules per
        connector: `companies_to_extract` only for AX/F&O and NAV/BC; content packs only for AX/F&O, NAV/BC and CE,
        must be packs of that family, not excluded for that source system, no duplicates; SQL Server takes neither.
        Migration: `migration_type_id`, `migration_information`.
  People (Stage 5) and state actions (Stages 5-7) are not built yet.
```

## Tasks and submitted data

```
GET /api/v1/portal/projects/{projectId}/tasks
  Auth: admin, or a user linked to {projectId}'s customer.
  Behavior: one call returns the full task list for a project — task id, template id+version ref, status,
        assignee, due date. No template content merge.

GET /api/v1/portal/projects/{projectId}/data
  Auth: admin, or a user linked to {projectId}'s customer.
  Behavior: one batched call returns submitted field values for every task in the project (secrets redacted as
        `· submitted ·`). Avoids a per-task round-trip when rendering a whole project.

PUT /api/v1/portal/tasks/{taskId}/fields/{fieldKey}
  Auth: admin, or the assigned customer user.
  Body: { value }
  Behavior: saves one field value (or secret) at a time — autosave-friendly. The only write path for field values.
  Validation: the backend never trusts the browser for schema. On each call it looks up task {taskId}'s frozen
        templateId+version, then checks Azure SQL's indexed template-field metadata (architecture-design.md §7 —
        written by the publish pipeline from `template.yml`, not from the request) for a row matching {fieldKey}:
        - No matching row → 400 Bad Request (unknown field for this template version).
        - Row found → its `fieldType` (text/secret/checkbox) drives value validation (string vs boolean) and
          whether secret handling applies, regardless of what the client claims. For a `secret` field the value is
          **encrypted with AES-256-GCM under a DEK wrapped by the Key Vault KEK and stored as ciphertext** in the
          separate secrets schema (behind EXECUTE-only stored procedures); only ciphertext + nonce + wrapped DEK +
          metadata are persisted, never plaintext. Replacing a secret overwrites in place (no plaintext history).
          Request bodies on this route are never logged. See `docs/security-design.md` §3.

POST /api/v1/portal/tasks/{taskId}/submit
  Auth: admin, or the assigned customer user.
  Behavior: no body — flips task status to "Submitted" once fields are filled, for admin review.

POST /api/v1/admin/tasks/{taskId}/review
  Auth: admin only.
  Body: { decision: "approved" | "needs_changes", feedback? }
  Behavior: admin approves or rejects a submitted task (functional-design.md §7, §9).

GET /api/v1/portal/tasks/{taskId}/comments
POST /api/v1/portal/tasks/{taskId}/comments
  Auth: admin, or the assigned customer user.
  Behavior: comment thread on a task. Internal review notes are a separate, admin-only field/endpoint — never
        visible to customers (functional-design.md §6). No pagination — full thread in one call.
```

## Secret reveal (admin)

```
POST /api/v1/admin/secrets/reveal
  Auth: admin.
  Body: { secrets: [ { taskId, fieldKey } ] }     # one or many — bulk reveal is supported
  Behavior: server-side-decrypts and returns the plaintext secret value(s) for admin use, including **bulk**
        retrieval of many at once. There is no step-up re-auth, reason prompt, or one-time display — the control is
        the admin's MFA'd session plus an **immutable audit entry per revealed secret** (value-free) and anomaly
        alerting on reveal volume (`docs/security-design.md` §3.2, §10). Revealing marks each secret `opened`
        (eligible for the daily purge unless `pipeline-required`). Request/response bodies are never logged.
```

## ADF / machine extraction API (functional-design.md §14)

```
GET /api/v1/extract/projects?changedSince={timestamp}&cursor={cursor}
  Auth: machine caller, `Extract.Read` app role.
  Behavior: incremental extraction — for each project, its task list with current status plus a done/total count.
        Filtered by "changed since". **Carries no secret values.**

GET /api/v1/extract/notifications?changedSince={timestamp}&cursor={cursor}
  Auth: machine caller, `Extract.Read` app role.
  Behavior: full raw notification history (every notification sent, when, and to which user by `recipientUserId`).
        The raw `recipient` (email / Teams identifier) is **pseudonymized** — only the opaque `recipientUserId`
        crosses into the data warehouse (`docs/security-design.md` §13). **Carries no secret values.**

POST /api/v1/extract/secrets/consume
  Auth: machine caller, `Secret.Consume` app role (the onboarding/provisioning pipeline — distinct from the
        reporting `Extract.Read` role above).
  Body: { projectId }
  Behavior: server-side-decrypts and returns the secret value(s) the provisioning pipeline needs for a project,
        over TLS. Consumers never read the database directly (decryption is a single audited chokepoint). Each
        returned secret is marked `opened`/consumed and audited; `pipeline-required` secrets are purged only on
        onboarding completion, not on this read. Request/response bodies are never logged.
```

## Project summary / report

```
GET /api/v1/portal/projects/{projectId}/report
  Auth: admin, or a user linked to {projectId}'s customer. Machine callers are **not** accepted here — they use the
        `/extract/*` router only (keeping the interactive per-project route and the batch machine identity strictly
        separated).
  Behavior: single-call project summary — task list with statuses plus completion counts. Generated fresh from
        Azure SQL on every call (no stored artifact); rendered client-side.
```

## Schemas

The request/response contract is the **public wire contract**, independent of the Azure SQL schema (an
implementation detail behind the EXECUTE-only stored procedures — see `docs/adr/0002`). Types are written as Python
`TypedDict`s; optional keys use `NotRequired`, enums use `Literal`, and the list envelope is a generic `Page[T]`.

**Conventions** (apply to every endpoint):

- **Case**: field names are `camelCase`.
- **IDs**: GUID strings. **Timestamps**: ISO 8601 UTC (`2026-07-27T12:00:00Z`).
- **Optional fields are omitted** when absent (modeled as `NotRequired`, not `null`) — the one exception is
  `nextCursor`, which is always present and is explicit `null` on the last page.
- **Lists** return the `Page[T]` envelope; **single resources** are returned bare (unwrapped).
- **Errors**: every non-2xx response is `application/problem+json` (RFC 9457) — the `Problem` shape below.
- **Enums** are `snake_case` string tokens.

### Primitive & shared types

```python
from typing import Generic, Literal, NotRequired, TypedDict, TypeVar

Guid = str          # "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
IsoDateTime = str   # ISO 8601 UTC, "2026-07-27T12:00:00Z"
IsoDate = str       # calendar date, "2026-07-27" (due dates)

T = TypeVar("T")

# Envelope returned by every list endpoint.
class Page(TypedDict, Generic[T]):
    items: list[T]
    nextCursor: str | None      # pass back as ?cursor=; None on the last page

# Body of every non-2xx response. Media type: application/problem+json
class Problem(TypedDict):
    type: str                   # URI reference; "about:blank" when unspecified
    title: str                  # short, human-readable summary
    status: int                 # HTTP status code, duplicated for convenience
    detail: NotRequired[str]    # explanation specific to this occurrence
    instance: NotRequired[str]  # URI reference identifying this occurrence
```

### Enums

```python
TaskStatus = Literal[
    "not_started", "in_progress", "submitted",
    "needs_changes", "approved", "not_applicable",
]
ReviewDecision = Literal["approved", "needs_changes"]
FieldType = Literal["text", "secret", "checkbox"]
Role = Literal["admin", "user"]             # was "customer"; aligned with the Users table's role values
InvitationStatus = Literal["pending", "redeemed", "revoked"]
NotificationChannel = Literal["email", "teams"]
NotificationType = Literal[
    "task_due_soon", "task_overdue",
    "comment_added", "task_status_changed", "all_tasks_completed",
]
```

### Entity shapes

```python
class CustomerRef(TypedDict):
    id: Guid
    name: str

class User(TypedDict):
    id: Guid
    email: str                              # Entra-verified email
    role: Role                              # display mirror; admin authority is the Entra claim, not this column
    signedUpAt: NotRequired[IsoDateTime]    # omitted until the invitation is redeemed
    customers: list[CustomerRef]            # customers this user is linked to (may be empty; empty for admins)

class Invitation(TypedDict):
    id: Guid
    email: str
    role: Role
    status: InvitationStatus
    customers: list[CustomerRef]            # customers to be linked on redemption (empty for admin invites)
    invitedAt: IsoDateTime
    redeemedAt: NotRequired[IsoDateTime]

class TaskAssignmentInput(TypedDict):       # optional initial assignment carried on an invite
    taskId: Guid

class CustomerLink(TypedDict):              # result of linking a user to a customer
    userId: Guid
    customerId: Guid
    customerName: str
    linkedAt: IsoDateTime

class Customer(TypedDict):
    id: Guid
    name: str
    primaryContactUserId: NotRequired[Guid]  # omitted if none set
    createdAt: IsoDateTime

class TaskTemplateRef(TypedDict):           # task templates are git-authored; id is the git template id
    id: str                                 # e.g. "entra-app-registration"
    latestVersion: int
    category: str                           # free text (not enum-validated)

class TaskTemplateBinding(TypedDict):
    templateId: str
    version: int

class ProjectTemplate(TypedDict):           # portal-managed (Azure SQL), not git-authored
    id: Guid
    name: str
    description: str
    tasks: list[TaskTemplateBinding]
    createdAt: IsoDateTime
    updatedAt: IsoDateTime

class Project(TypedDict):                   # metadata only — not the task list
    id: Guid
    name: str
    customerId: Guid
    customerName: str
    projectTemplateId: NotRequired[Guid]    # omitted if created without a template
    dueDate: NotRequired[IsoDate]
    createdAt: IsoDateTime

class Task(TypedDict):                      # structure only — no template content
    id: Guid
    templateId: str
    templateVersion: int                    # frozen at assignment
    status: TaskStatus
    assigneeUserId: NotRequired[Guid]       # admin or customer user; omitted if unassigned
    dueDate: NotRequired[IsoDate]

class FieldValue(TypedDict):
    fieldKey: str
    fieldType: FieldType
    # text -> str, checkbox -> bool,
    # secret -> "· submitted ·" once stored, otherwise None (never the real value on this shape)
    value: str | bool | None
    submitted: bool                         # whether any value has ever been stored
    updatedAt: NotRequired[IsoDateTime]

class RevealedSecret(TypedDict):            # only returned by /admin/secrets/reveal and /extract/secrets/consume
    taskId: Guid
    fieldKey: str
    value: str                              # decrypted plaintext — bodies on these routes are never logged

class TaskData(TypedDict):                  # one task's values in the batched project-data call
    taskId: Guid
    fields: list[FieldValue]

class Comment(TypedDict):                   # customer-visible thread only (internal notes are separate)
    id: Guid
    taskId: Guid
    authorUserId: Guid
    authorName: str
    authorRole: Role
    body: str
    createdAt: IsoDateTime

class ReportTask(TypedDict):
    taskId: Guid
    templateId: str
    templateVersion: int
    status: TaskStatus

class ReportSummary(TypedDict):
    totalTasks: int
    completedTasks: int                     # count of "approved" tasks
    byStatus: dict[TaskStatus, int]

class ProjectReport(TypedDict):
    projectId: Guid
    projectName: str
    customerId: Guid
    customerName: str
    tasks: list[ReportTask]
    summary: ReportSummary

class ProjectExtract(TypedDict):            # one project in the incremental extraction feed
    projectId: Guid
    projectName: str
    customerId: Guid
    tasks: list[ReportTask]
    summary: ReportSummary
    changedAt: IsoDateTime

class Notification(TypedDict):
    id: Guid
    type: NotificationType
    channel: NotificationChannel
    recipient: str                          # email / Teams identifier; PSEUDONYMIZED (opaque) in the extract feed
    recipientUserId: NotRequired[Guid]      # present when the recipient maps to a known user; stable downstream key
    projectId: NotRequired[Guid]
    taskId: NotRequired[Guid]
    sentAt: IsoDateTime
```

### Request / response body per endpoint

`204` responses have no body. Every error is a `Problem` (above).

```
Provisioning & access (admin router)
POST   /admin/invitations                            req { email: str, role: Role,
                                                           customerIds: NotRequired[list[Guid]],
                                                           primaryContactCustomerId: NotRequired[Guid],
                                                           taskAssignments: NotRequired[list[TaskAssignmentInput]] }
                                                                                          -> 201 Invitation
GET    /admin/invitations                            -> 200 Page[Invitation]
POST   /admin/invitations/{id}/resend                (no body)                            -> 200 Invitation
DELETE /admin/invitations/{id}                       -> 204
GET    /admin/users                                  -> 200 Page[User]
POST   /admin/users/{userId}/customer-links          req { customerId: Guid }             -> 201 CustomerLink
DELETE /admin/users/{userId}/customer-links/{id}                                          -> 204
POST   /admin/users/{userId}/role                    req { role: Role }                   -> 200 User
POST   /admin/users/{userId}/deactivate              (no body)                            -> 204
DELETE /admin/users/{userId}                                                              -> 204

Task templates
GET    /admin/task-templates                         -> 200 Page[TaskTemplateRef]

Project templates
GET    /admin/project-templates                      -> 200 Page[ProjectTemplate]
GET    /admin/project-templates/{id}                 -> 200 ProjectTemplate
POST   /admin/project-templates                      req { name, description,
                                                           tasks: list[TaskTemplateBinding] }   -> 201 ProjectTemplate
PUT    /admin/project-templates/{id}                 req { name, description,
                                                           tasks: list[TaskTemplateBinding] }   -> 200 ProjectTemplate
DELETE /admin/project-templates/{id}                 -> 204

Customers & projects
GET    /admin/customers                              -> 200 Page[Customer]
POST   /admin/customers                              req { name: str }                    -> 201 Customer
GET    /admin/customers/{id}                          -> 200 Customer
GET    /admin/customers/{id}/users                    -> 200 Page[User]
GET    /admin/projects                               -> 200 Page[Project]
POST   /admin/projects                               req { customerId: Guid, name: str,
                                                           projectTemplateId: NotRequired[Guid],
                                                           dueDate: NotRequired[IsoDate] }     -> 201 Project
GET    /portal/projects/{id}                          -> 200 Project

Tasks & submitted data (portal router)
GET    /portal/projects/{projectId}/tasks             -> 200 { items: list[Task] }        # full list, not paginated
GET    /portal/projects/{projectId}/data              -> 200 { tasks: list[TaskData] }    # batched, secrets redacted
PUT    /portal/tasks/{taskId}/fields/{fieldKey}      req { value: str | bool }            -> 200 FieldValue
POST   /portal/tasks/{taskId}/submit                 (no body)                            -> 200 Task
POST   /admin/tasks/{taskId}/review                  req { decision: ReviewDecision,
                                                           feedback: NotRequired[str] }        -> 200 Task
GET    /portal/tasks/{taskId}/comments                -> 200 { items: list[Comment] }     # full thread, not paginated
POST   /portal/tasks/{taskId}/comments               req { body: str }                    -> 201 Comment

Secret reveal (admin router)
POST   /admin/secrets/reveal                         req { secrets: list[{ taskId: Guid, fieldKey: str }] }
                                                                                          -> 200 { revealed: list[RevealedSecret] }

Project summary / report (portal router)
GET    /portal/projects/{projectId}/report            -> 200 ProjectReport

Machine extraction (extract router)
GET    /extract/projects?changedSince=&cursor=        -> 200 Page[ProjectExtract]         # Extract.Read; no secrets
GET    /extract/notifications?changedSince=&cursor=   -> 200 Page[Notification]           # Extract.Read; no secrets
POST   /extract/secrets/consume                      req { projectId: Guid }              # Secret.Consume
                                                                                          -> 200 { secrets: list[RevealedSecret] }
```

## Open questions

- _None — request/response schemas are specified in "Schemas" above._

# Projects Implementation Plan

Staged build of [projects-design.md](./projects-design.md). **Every stage ends with a review gate**: stop,
summarize what changed, and wait for the owner's approval before starting the next stage. Use the
issue-tracker rules in `docs/agents/issue-tracker.md` (one work item per stage, New → Active → Closed).

## Resume protocol

1. Read `CONTEXT.md`, ADR-0013 and `projects-design.md`.
2. Find the first stage below whose status is not **Done**; read only that stage.
3. Update the status table at the end of each stage, in the same change.

## Working agreements

- Data access only through EXECUTE-only stored procedures (ADR-0002/0008); no raw SQL from the API.
- Each stage ships tests with the code (`api/tests`) and updates the docs it touches.
- Keep `old_projects/` out of git; never copy its Freshdesk key anywhere.
- Do not implement tasks/templates, the extract API or legacy import (out of scope).

## Stage index

| # | Stage | Status |
|---|---|---|
| 0 | Decisions and docs (this plan, ADR-0013, design) | Done |
| 1 | Remove the customer module; read-only customer lookup | Done (awaiting review) |
| 2 | Project core data model and lookups | Done (awaiting schema review) |
| 3 | Project CRUD, visibility, Draft rules | Done (awaiting review) |
| 4 | Installation and Migration definitions | Done (awaiting review) |
| 5 | People (users) on a Project and submit validation | Pending |
| 6 | Approve: Freshdesk ticket + invites (atomic) | Pending |
| 7 | Lifecycle actions (reject, hold, resume, cancel) and audit | Pending |
| 8 | Communication ticket linking and ticket search | Pending |
| 9 | Frontend | Pending |
| 10 | Docs sync and hardening | Pending |

## Stage 1: Remove the customer module; read-only customer lookup

- Drop `onboarding.Customer`, `UserCustomers`, procs `GetCustomer`, `ListCustomers`, `LinkUserCustomer`,
  `UnlinkUserCustomer`, `UnlinkAllUserCustomers`; adjust `DeleteUser`, `ListUsers`, `SetUserDeactivated`.
- Remove `api/app/modules/customers`, `api/tests/test_customers.py`, `CustomerTable.tsx`, customer parts of
  `api.ts` and `UserManagement.tsx`, and customer scope from invite (`users/schemas.py`, `repository.py`).
- Add proc `SearchCustomers` over `ext.Customer` (id + name only) and `GET /api/v1/customers/lookup`.
- Invite no longer links customers; assignment moves to Stage 6.
- Gate: app builds, tests green, no `UserCustomers` references outside archived docs.

## Stage 2: Project core data model and lookups

- Tables from design §5 (`Project`, `ProjectPerson`, label link, definitions, connector, packs, lookups),
  with constraints (state enum, 1–3 connectors, unique email per project).
- Seed lookups from the legacy form options (departments, source systems with family, content packs,
  installation types, Power BI licenses, environment connection, migration types, person labels).
- Procs for lookup read and Admin lookup CRUD.
- Gate: schema review (naming, constraints, seeds) before any API depends on it.
- Tables (deliberately close to the two legacy tables; 4 tables, 2 procs): `Project` (Installation and Migration
  definition columns on the same row, CHECKs keep them to the right `Type`), `ProjectPerson` (needed for invites
  and access scope; the three labels are yes/no flags), `ProjectConnector` (1-3 rows per Project, content packs
  as a JSON id list) and `LookupOption` (every admin-managed dropdown, one row per option, `Kind` says which).
- Procs: `ListLookupOptions`, `UpsertLookupOption`. Project read/save procs arrive in Stage 3+.
- Seeds: `Scripts/seed-lookups.sql` (from `post-deploy.sql`), insert-if-missing so Admin edits survive redeploys.
- Review notes: options are deactivated, never deleted; the API (not the database) validates that a lookup
  reference has the right `Kind`, that packs match the source-system family, and the per-family connector
  questions. Extras beyond design §5: `AllowsFreeText` ("Other" connection), `ExcludedSourceSystemId`
  (Advanced Manufacturing not for AX).
- Verified by building the SSDT project and exercising tables, procs, seeds and constraints on LocalDB; no
  API code or Python tests in this stage.

## Stage 3: Project CRUD, visibility, Draft rules

- Procs and endpoints: create, get, list, update, delete (Admin only, own Draft).
- Visibility enforced in procs: Draft author-only; PM/Admin all else; customer user via assignment and
  `Approved`+.
- Requester defaults to creator, overridable to another PM.
- Gate: authorization tests cover every role × state combination.
- Built: `VisibleProject` (single visibility rule) and procs `CreateProject`, `GetProject`, `ListProjects`,
  `UpdateProject`, `DeleteProject` return `(Outcome, ProjectId)` for writes (NotFound/Forbidden/Locked/NotDraft/
  Unknown*); the API maps outcomes to 404/403/409/422. API module `app/modules/projects` (+ read-only
  `lookups`, `PortalPrincipal.is_staff`). Header fields only; definitions are Stage 4.
- Decisions: hidden Project = 404; Draft edits are not audited, any edit after Draft (Admin only) is, atomically
  in the proc; requester override is validated against Entra roles in the API (`GET /projects/requesters`);
  a caller with no `Users` row (bootstrap Admin) gets one on first create via Graph email; customer users see
  Approved/InProgress/Ready/OnHold only (Cancelled revokes) with internal fields nulled.
- Verification: `api/tests/test_projects.py` (role gating, validation, merge, outcome mapping) and
  `database/Scripts/tests/project-visibility-tests.sql` (role × state matrix, locks, audit; run on LocalDB with a
  stand-in `ext.Customer`) — both green; ruff and mypy clean.

## Stage 4: Installation and Migration definitions

- Definition endpoints with per-type validation, connector family rules (only applicable pack fields).
- Locking: PM edits only in `Draft`; Admin edits afterwards with audit.
- Resolve open items 1 and 3 (design §8) before this stage's gate.
- Gate: validation matrix reviewed with real examples from the old form.
- Built: procs `SaveProjectDefinition` (full replace, connectors replaced as a set from JSON, same Draft/Admin-lock
  and audit rules as `UpdateProject`, `WrongType` outcome), `GetProjectDefinition`, `ListProjectConnectors`;
  endpoints `GET .../definition`, `PUT .../installation`, `PUT .../migration` (see `api-design.md`). Everything is
  optional on save so a Draft can be half-filled; completeness (≥1 connector, ≥1 environment, required fields)
  is the Stage 5 submit check.
- Decisions: open item 3 resolved as the **requester PM** (no extra field). Open item 1: the flag is only
  stored here; recommended rule is that `SignedSoftwareAgreement = false` **blocks approve** (Stage 6; the legacy
  flow put such installations On Hold) while PMs can still submit. Open item 2 (pre-fill from `ext.Customer`) is
  not needed yet. Only active lookup options can be saved; a later deactivation does not break reading.
- Verification: `api/tests/test_project_definitions.py` (role gating, type match, validation matrix);
  `database/Scripts/tests/project-definition-tests.sql` run on LocalDB against a scratch deploy of all
  `onboarding` objects. ruff, mypy and pytest are green.

## Stage 5: People on a Project and submit validation

- Add/remove/label people (name, email, labels); duplicate-email rule.
- `submit` action: full completeness check (definition, deadline, ≥1 person, each required label).
- No emails or Entra calls here.
- Gate: submit rules reviewed.

## Stage 6: Approve (Freshdesk ticket + invites, atomic)

- Freshdesk client (config: endpoint, group, email config, CC; API key from Key Vault). Idempotent via
  stored `RequestTicketId`.
- Reuse the existing invite service (Entra B2B, Graph): invite new emails, assign existing users, assign
  role per ADR-0012, write `ProjectPerson.UserId` and the assignment.
- Ordering and failure semantics per design §4; partial success is resumable, never duplicated.
- Consultant required (active Admin).
- Gate: failure-injection tests (ticket fails, invite fails, retry) reviewed; rotate the leaked Freshdesk
  key first (design §9).

## Stage 7: Lifecycle actions and audit

- `reject` (reason), `hold`, `resume`, `cancel` (revoke access), manual `Approved` → `In progress` and
  `Ready` until tasks exist.
- Every transition and Admin edit through `AppendAuditEvent`.
- Gate: state-machine test table reviewed.

## Stage 8: Communication ticket linking and ticket search

- `SearchTickets` proc over `ext.Tickets` (subject, status, id; Admin only), link/unlink on the Project,
  validating existence.
- Gate: review.

## Stage 9: Frontend

- Projects list and detail by role; PM/Admin create wizard (definition, people, submit); Admin approval screen
  (consultant, flagged people, errors surfaced); lookups admin; ticket search.
- Display-only squashed installation code.
- Gate: UX review, including accessibility and CSP rules in security-design §5.5.

## Stage 10: Docs sync and hardening

- Update `functional-design.md`, `api-design.md`, `security-design.md`,
  `authentication-and-access.md`, `architecture-design.md`, `entra-configuration.md` for the Project scope
  (remove customer-scoped wording); update the `copilot-instructions.md` map.
- Security review of the new endpoints and Freshdesk integration.
- Gate: final owner sign-off.

## Later (not planned here)

Tasks and templates (admin attaches after approval; definition drives task assignment), auto-`Ready`, the
Projects extract API and Power BI cutover, deadline-change notifications, legacy import if ever needed.

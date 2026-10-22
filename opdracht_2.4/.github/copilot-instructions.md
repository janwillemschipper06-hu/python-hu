# copilot-instructions.md

Guidance for AI agents working in this repository.

## Coding style: keep it simple

This team includes beginner coders. Always pick the simplest, most readable way, even if a more "clever" or idiomatic-advanced option exists.

- **FastAPI parameters:** use plain typed parameters with defaults (`state: ProjectState | None = None`). FastAPI reads them from the query string automatically. Do **not** add `Annotated[..., Query()]` or Pydantic "filter models" unless a constraint is genuinely needed (e.g. `limit` capped with `Query(ge=1, le=100)` for safety, or `Header(alias=...)`). Prefer plain params over a Query/Depends model even with several filters.
- **Enums:** pass `StrEnum` values straight through (they are `str`); don't unwrap with `.value if x else None`.
- Avoid extra abstraction, indirection or advanced typing features when a plain version works. If unsure, choose the version a junior developer reads fastest.

## Agent skills

### Issue tracker

**Before doing anything with issues/work items (creating, reading, commenting, changing state, or touching relationships), always read `docs/agents/issue-tracker.md` first.**

Issues live as Azure DevOps work items on the Ops - BI team board, managed via the `az boards` CLI. Agents auto-drive state New→Active (on claim) →Closed (on verified completion), and on resolving a blocker, comment the solution on every item it was blocking without removing the blocking link. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), represented as Azure DevOps work item tags. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Where to find what

These are **reference docs — read them on demand**, only when you actually need the information for the task at hand. Don't load them on every prompt. When you do need a topic, check `CONTEXT.md` (ubiquitous language) and the relevant ADR first, then open the design doc that owns it:

| Looking for… | Authoritative doc |
|---|---|
| Ubiquitous language / actor & secret vocabulary | `CONTEXT.md` |
| Load-bearing decisions & their rationale | `docs/adr/` (0001 write-through to external vault; 0002 EXECUTE-only stored-proc tenant isolation; 0003 user-assigned identity / single-pass deploy; 0004 Python + FastAPI backend; 0008 app data access via stored procedures only; 0010 authentication offloaded to the platform / Container Apps built-in auth, app authorizes only; 0011 admin authority is a direct `Admin` app-role assignment on the user — no Portal-Admins group / no Entra ID P1; 0012 four app roles Admin/PM/User/Extract.Read, sign-in requires guest + assigned role (assignment required); 0013 Project replaces Customer as the isolation/assignment scope) |
| What the product does — roles, tasks, task lifecycle/statuses, notifications, templates, extraction API | `docs/functional-design.md` |
| Hosting, networking, compute, storage, template authoring/publishing/versioning | `docs/architecture-design.md` |
| API surface — endpoints, auth per route, request/response schemas, enums | `docs/api-design.md` |
| Security & compliance — threat model, secret write-through, identity/MFA, SPA/token/CSP/XSS hardening (§5.5), authz & tenant isolation, network, egress, logging/alerting, backup/DR, NIS2 governance & accepted residual risks (§18) | `docs/security-design.md` |
| Authentication & access — identity topology, invite-only provisioning, three-router authorization, sign-in/MFA, secret storage/encryption, ADF identity (authoritative; supersedes security §3–§5) | `docs/authentication-and-access.md` |
| How to build the authentication design, stage by stage — the staged implementation/execution plan (Entra-manual vs agent-coding, review gates, cross-session progress) | `docs/authentication-implementation-plan.md` |
| Entra object inventory & per-environment runbook — every manual Entra object (app registrations, app roles, federated credential, Graph grants), what each does, why, dev→prod values, prod go-live checklist | `docs/entra-configuration.md` |
| Projects (installation/migration) — data model, lifecycle, visibility, Freshdesk ticket at approval, open items (replaces customer scope, ADR-0013) | `docs/projects-design.md` |
| How to build Projects, stage by stage with review gates | `docs/projects-implementation-plan.md` |
| Prototype outcome & practical build lessons | `docs/prototype-lessons-learned.md` |

`docs/security-design.md` is the **authority** wherever functional/architecture/API docs defer security mechanics (most importantly secret storage).

**Do not use `docs/archive/`.** Files there (e.g. `inital-plan.md`) are **superseded historical brainstorms** that contradict the current design — never implement from them.

**Keep this map current.** Whenever you add, remove, rename, move, or significantly re-scope a doc under `docs/` (including archiving one), update the table above and the `docs/agents/*` pointers in the same change, so this index never drifts from reality.

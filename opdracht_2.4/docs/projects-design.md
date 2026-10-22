# Projects Design

Authoritative design for **Projects** in the portal: the replacement of the former Microsoft Forms +
Power Automate + SQL installation/migration tracking. Decision rationale:
[ADR-0013](./adr/0013-project-replaces-customer-as-isolation-scope.md). Vocabulary: `CONTEXT.md`
(Project, Project definition, Project task, Customer, PM, Customer user). Build order:
[projects-implementation-plan.md](./projects-implementation-plan.md).

Source material (legacy, reference only): `old_projects/` (forms, tables, load procs, flows, ticket
template `safi.html`). Do not implement from it where this doc differs.

## 1. Scope

**In scope now:** Project data model, definition forms (Installation and Migration), lifecycle,
visibility and assignment, atomic approval (Freshdesk request ticket + invites), communication-ticket
linking, removal of the customer module.

**Out of scope (later):** Project tasks and templates (admin attaches a template with tasks after
approval; the definition will drive which tasks apply, to us or the customer), the reporting extract API for
Projects, auto-`Ready` when all tasks are approved, importing legacy rows (the 115 old installations are
not imported; the old Power BI report keeps reading the old tables), Freshdesk updates when a deadline moves.

## 2. Customer and tickets: external, read-only

| Object | Source | Use |
|---|---|---|
| `ext.Customer` (`CustomerConfigID`, `CustomerName`, …) | FO, external table | Customer dropdown on a Project and name display. Never written. Project stores `CustomerConfigID`. |
| `ext.Tickets` (`id`, `subject`, `status`, …) | Freshdesk staging, external table | Consultant searches subjects and statuses in the portal to link the communication ticket. Read-only. |

The portal never creates, edits or exposes endpoints for customers. All access is via stored procedures
(ADR-0008).

## 3. Roles and visibility

| Actor | Role | Can do |
|---|---|---|
| PM | `PM` | Create Projects, fill the definition, add people, submit `Draft` → `Requested`. Sees every Project except another author's `Draft`. |
| Admin | `Admin` | Everything a PM can; approve/reject, set consultant, edit anything (audited), hold/resume/cancel, link communication ticket, invite users. Sees every Project except another author's `Draft`. |
| Customer user | `User` | See assigned Projects that are `Approved` or later; (later) fill tasks. |

- A `Draft` is visible only to its author (PM or Admin).
- The consultant is always an Admin, stored on the Project, with no extra access.
- Customer-user scope = `ProjectUsers` rows, enforced inside EXECUTE-only stored procedures
  (ADR-0002/0013). Cancel or unassign revokes access immediately.

## 4. Lifecycle

```
Draft ──submit──► Requested ──approve──► Approved ──first task started──► In progress ──► Ready
  ▲                  │                      │              │                  │
  └────reject────────┘                      └──── On hold ◄┴──────────────────┘   (resume → previous)
                      Cancelled: any state after Requested (Admin)
```

| Transition | Who | Rules |
|---|---|---|
| `Draft` → `Requested` | PM/Admin (author) | Definition complete for the Project type; at least one person and at least one each of the labels Customer project manager, Functional, Technical; no duplicate email; deadline set. PM's definition locks. |
| `Requested` → `Draft` (reject) | Admin | Reason required; no ticket or invites exist yet. |
| `Requested` → `Approved` | Admin | **Atomic and blocking:** consultant required; create the Freshdesk request ticket; invite and assign all people (existing portal users are only assigned); then set state. Any failure leaves the Project `Requested` with the error shown; retries never duplicate what already succeeded. |
| `Approved` → `In progress` | automatic | When the first task is started (tasks are a later stage; manual Admin action until then). |
| `In progress` → `Ready` | Admin (manual for now) | Means all requirements are filled and reviewed so a consultant can start. Later: automatic when all tasks are approved. Does **not** mean the installation is done. |
| any after `Requested` → `On hold` | Admin | Resume returns to the previous state. Access kept, task changes blocked. |
| any after `Requested` → `Cancelled` | Admin | Revokes customer-user access, keeps data. |

Nothing is hard-deleted except an Admin deleting their own `Draft`. After `Requested` only an Admin edits
the definition, every edit audited via `AppendAuditEvent`.

## 5. Data model

Schema `onboarding`; all tables reached only through EXECUTE-only procedures. Names illustrative.

**`Project`**: `ProjectId`, `CustomerConfigID` (ext), `Type` (Installation | Migration), `Name`, `State`,
`PreviousState` (for hold), `RejectionReason`, `RequesterUserId` (the PM; defaults to the creator, may be
another PM), `CreatedByUserId`, `DepartmentId`, `CustomerType` (Direct 9altitudes-SmartInsights |
Indirect Dynalogic-Birds), `Deadline` (when the installation/migration must be **done**, Admin-editable),
`Hours`, `RequestNotes`, `ConsultantUserId` (Admin), `RequestTicketId`, `CommunicationTicketId`,
created/updated stamps.

**`InstallationDefinition`** (1:1, Installation only): preferred installation type, preferred Power BI
license, environments to install (Development, Test, Acceptance, Production), environment connection
mode (+ free text for Other), `AzureSubscriptionByUs`, `PowerBILicenseByUs`, `PowerBILicensesSold`,
checks (`AzureCostsInformed`, `SignedSoftwareAgreement`, `TeamsChannelAdded`), `TeamsChannelUrl`.

**`ProjectConnector`** (1–3 per Installation): source system, license count (1–5), companies to extract
(applies to AX/F&O and NAV/BC families), and `ProjectConnectorPack` rows linking content packs.
Which pack questions apply depends on the source-system **family** (AX/F&O, NAV/BC, CE, SQL Server = none);
the API validates only the applicable ones and rejects the rest.

**`MigrationDefinition`** (1:1, Migration only): migration type, free-text information (covers "Other").

**`ProjectPerson`**: `ProjectId`, name, email, `UserId` (NULL until invited) and `ProjectPersonLabel`
rows (Customer project manager, Functional, Technical; a person may hold several). All people get identical
access and the same invite; labels are informational. `ProjectUsers` for isolation is derived from rows with
a `UserId` (or the person table itself is the join).

**Physical layout (Stage 2):** the two definitions above are columns on `Project` (like the legacy
Installation/Migration tables), connectors are `ProjectConnector` rows with content packs as a JSON id list,
person labels are three flags on `ProjectPerson`, and all lookups below live in one `LookupOption` table
(`Kind` column).

**Admin-managed lookups:** Department, SourceSystem (with family), ContentPack (family, kind:
Kickstart/Additional/ISV), InstallationType, PowerBILicense, EnvironmentConnection, MigrationType,
PersonLabel. New options are added in the portal, not in code.

The legacy single code (`BC2ADLS-FABRIC`, `FO-SL-CL-PPU`, …) is **not stored**; the UI may squash
source system + installation type + Power BI license into it for display only.

## 6. Freshdesk request ticket (at Approve)

Created by the API (not Power Automate) through the Freshdesk `POST /api/v2/tickets/outbound_email`
endpoint, which emails the requester PM. Mapping, replicating the legacy flow:

| Field | Value |
|---|---|
| email (requester) | Project's requester PM |
| subject | `Installation Request: <Customer>` / `Migration Request: <Customer>` |
| description | HTML from the `safi.html` template: customer, customer type, requester, department, deadline, pointer to the Power BI report |
| cc_emails | `Planning.ba@9altitudes.com` (config) |
| status / priority | Open (2) / Low (1) (config) |
| type, `cf_category` | Installation or Migration |
| group_id, email_config_id | configuration, not Project data |
| `cf_begroting_uren` | Project hours |

Rules: blocking; idempotent (stores `RequestTicketId` as soon as the call succeeds and never creates a second
ticket for a Project); the Freshdesk API key lives in Key Vault, never in the repo or flow exports.
The consultant later links one **communication ticket** (`CommunicationTicketId`) by searching `ext.Tickets`;
the API validates that the id exists there.

## 7. API surface (summary; details go in `api-design.md` when built)

- `GET/POST /api/v1/projects`, `GET/PATCH /api/v1/projects/{id}` (role/visibility filtered).
- Definition endpoints per type; people add/remove/label.
- State actions: `submit`, `approve`, `reject`, `hold`, `resume`, `cancel`.
- `GET /api/v1/customers/lookup` is the only customer read: search by name for the dropdown (no write, no
  customer resource).
- `GET /api/v1/tickets/search` (Admin) for linking; `PUT /projects/{id}/communication-ticket`.
- Admin lookup CRUD for the managed lookups.
- Removed: all `/customers` endpoints, `UserCustomers` link/unlink in the user flows.

## 8. Open items (decide before the stage that needs them)

1. **Signed software agreement gate.** Legacy: no signed agreement ⇒ installation auto-`On Hold`. Proposed
   (Stage 4, awaiting owner confirmation): stored only; `false` **blocks approve** (Stage 6), not submit.
2. **FO customer flags.** `ext.Customer` has `AzureSubscriptionProvider` / `PBILicenseProvider`; decide
   whether the definition pre-fills from them or stays independent.
3. **Migration "assigned project manager (if applicable)".** Resolved (Stage 4): the requester PM; no separate field.
4. **Power BI report cutover** (old tables vs new Projects) after the extract API exists.
5. **Hours/deadline reminders and notifications**: none now.

## 9. Security notes

- `old_projects/` is untracked and contains a customer-data export (`Results.csv`) and Power Automate
  exports with an embedded Freshdesk API key. **Do not commit it**, and rotate that key before the portal
  takes over ticket creation.
- Invites and ticket creation are the only side effects of approval; neither email contains a secret.

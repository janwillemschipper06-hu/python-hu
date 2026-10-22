# Customer Onboarding Portal — Functional Design

## 1. Goal

A web portal that helps customers prepare all requirements before a Microsoft Fabric solution is installed. Today this preparation is time-consuming because customers skip instructions, miss details, or send sensitive information through insecure channels.

The portal replaces that with a guided, trackable, step-by-step wizard.

## 2. One Portal, Two Views

A single application with two role-based views:

- **Admin view** — used by our company to set up and manage onboarding projects.
- **Customer view (wizard)** — used by the customer to complete their assigned onboarding tasks.

## 3. Roles

Only two roles exist:

| Role | Can do |
|---|---|
| Admin | Everything: manage customers, projects, templates, invitations, reviews/approvals, and secrets. |
| User | See and work on their own assigned project only: fill in values, submit secrets/info write-only (cannot read back what they submitted). |

## 4. What Admins Can Do

- Create customers.
- Manage the users associated with a customer — inviting a user (as a B2B guest) and linking them to the customer (see Section 12 and `docs/api-design.md`).
- Create onboarding projects for a customer, optionally starting from a project template (see Section 14) that pre-selects a bundle of tasks.
- Select which requirements/tasks apply to a project (from a reusable template library).
- Adjust the task list per project: add a task from the template library that wasn't part of the initial selection, remove a task entirely so it doesn't show up for that customer, or mark a task as "not applicable" so it stays visible in the history but isn't required.
- Assign a specific admin as the project owner/point of contact (optional, since all admins can access all projects).
- Assign who is responsible for each individual task — either one of the customer's users or an admin (see Section 12).
- Set due dates.
- Invite a user to a customer and link them, so their project becomes visible to them. Invitation is the **only** way a user gets access — there is no self-registration; an admin sends a B2B guest invitation and must explicitly link the user to a customer before they see anything (see `docs/authentication-and-access.md` and `docs/architecture-design.md` for the authentication model).
- Revoke a customer's access.
- Track progress of every project and task.
- Review submitted task information.
- Approve or reject a submitted task, with feedback when rejecting.
- Retrieve (reveal) submitted secrets when needed (e.g. to hand off to deployment) — secrets are stored **encrypted in the portal database** (application-layer envelope encryption), and any admin can reveal them in-portal from an MFA'd session; every reveal is written to an immutable audit log. There is no external secret vault. See `docs/security-design.md` §3 and `docs/authentication-and-access.md` §11–12.
- View comments added by the customer, and add internal review notes.
- View an audit history of key actions on a project.
- Manage the requirement template library (create/edit reusable task definitions, per language).
- View/generate the final onboarding summary report once a project is complete (also visible to the customer).
- Receive Teams notifications (see Section 11) when a customer adds a comment or completes all tasks.

## 5. What Customers Can Do

- Accept an admin invitation (joining as a B2B guest — there is no self-registration) and, once an admin has linked their user to the customer, access their assigned project. See `docs/authentication-and-access.md` for the authentication model.
- See only their own onboarding project — nothing belonging to other customers.
- See the full list of required tasks and their status (not started, in progress, submitted, needs changes, approved, not applicable).
- Open a task and see: what's needed, why it's needed, step-by-step instructions, how to verify it, and common mistakes.
- Enter required non-sensitive values (e.g. tenant ID, workspace name).
- Submit a task for review.
- Add comments/questions on a task.
- Submit sensitive values (passwords, client secrets, API keys, etc.) as a one-time, write-only submission.
- Replace a previously submitted secret if a mistake was made (cannot view the old or new value afterward — only that a replacement happened).
- See task status update after admin review (approved / needs changes with feedback).
- Fix and resubmit a rejected task.
- See the project/task due date.
- Receive email notifications (see Section 11) for task status changes, comments, and upcoming/passed deadlines.
- View the wizard and templates in their own language (multi-language support, driven by language-specific templates).
- View/download the final onboarding summary report once the project is complete.

## 6. What Customers Cannot Do

- View secrets, passwords, or sensitive values they (or anyone) previously submitted.
- View internal review notes.
- Access any other customer's or project's data.
- Access any admin functionality.

## 7. Task Lifecycle

| Status | Meaning |
|---|---|
| Not started | Customer has not opened the task. |
| In progress | Customer has started but not submitted. |
| Submitted | Customer says the task is done. |
| Needs changes | Admin rejected the submission with feedback. |
| Approved | Admin verified the task. |
| Not applicable | Requirement was removed for this customer. |

There is no `Blocked` status: tasks have no inter-task dependencies (see `docs/architecture-design.md` §1.4), so every assigned task is independently workable.

## 8. What a Task Looks Like

Each task is built from a reusable template (available per language). See `docs/architecture-design.md` for how templates are authored, translated, versioned, and published.

Each task has:

- Title and category (e.g. Microsoft Entra ID, Microsoft Fabric/Power BI, Azure, Azure DevOps/GitHub, Networking, Security & Compliance).
- What's needed / why it's required.
- Estimated time to complete.
- Which role on the customer side should do it (e.g. "Power BI/Fabric Admin").
- Who is currently responsible for completing it — a specific customer user or an admin (see Section 12).
- **Numbered step-by-step instructions.** Each step is clearly numbered so the customer can follow and refer to them in order.
- **Images/screenshots.** Steps can include pictures (e.g. a screenshot of the exact button to click) to make instructions unambiguous.
- One or more input fields: plain text values and/or write-only secret values — each marked required or optional.
- How to verify the step was done correctly, and common mistakes to avoid.

Risk level and template version are internal concepts (see `docs/architecture-design.md`) and are **not** shown to the customer in the wizard.

Customer-entered field values and comments are treated as **plain text**: they are stored verbatim and rendered as inert text (never as HTML or Markdown) in both the customer and admin views, so a customer cannot inject active content that would execute in an admin's browser. See `docs/security-design.md` §5.5.

### Example Task Categories

- **Microsoft Entra ID**: create service account, create security group, assign users, create app registration, grant API permissions.
- **Microsoft Fabric/Power BI**: enable tenant settings, configure workspace settings, create capacities, assign workspace admins, configure gateway/data source credentials.
- **Azure**: create resource group, create Key Vault, create storage account, configure private endpoints, assign RBAC roles.
- **Azure DevOps/GitHub**: create project/repo, create service connection, create variable groups, configure pipeline permissions, add deployment identity.
- **Networking**: firewall allowlists, private endpoint approvals, DNS entries, gateway installation.
- **Security & Compliance**: confirm data residency, admin contacts, break-glass process, audit/logging requirements.

## 9. How Tasks Get Validated

- **Manual**: admin reviews the entered values and approves/rejects. This is the only in-scope validation approach for now.
- **Automated** (future capability, out of scope for now): the portal calls Microsoft APIs (Graph, Azure, Fabric, Power BI, DevOps, GitHub) to confirm a requirement is actually met (e.g. does the group exist, is the service principal created, are permissions granted) instead of relying on the customer's word plus a screenshot.

## 10. Typical Journey

1. Admin creates a customer and a project, selects the applicable tasks, and invites the customer.
2. Customer opens the wizard and sees their task list.
3. Customer works through tasks one at a time: reads instructions, enters values, submits sensitive values where required, and submits the task.
4. Admin reviews each submission and approves or requests changes.
5. Customer fixes and resubmits any rejected tasks.
6. Once all required tasks are approved, the project is ready for deployment and a final onboarding report can be produced.

## 11. Notifications

| Recipient | Channel | Triggered by |
|---|---|---|
| Customer (task assignee, or primary contact if unassigned) | Email | Task due date approaching or passed. |
| Customer (task assignee, or primary contact if unassigned) | Email | Admin adds a comment on a task. |
| Customer (task assignee, or primary contact if unassigned) | Email | Task status changes (approved / needs changes). |
| Admin (task assignee, if an admin is assigned) | Teams channel | Customer adds a comment on a task. |
| Admin | Teams channel | Customer completes all tasks in a project. |

All notifications sent are kept as a permanent history record (see Section 15).

**Notifications carry links, not content.** A notification never includes the body of a comment, a field value, or any customer-authored text — only a short "a new comment was added / your task status changed — open the portal" message plus a link to the relevant task. This prevents sensitive text a customer may paste into a comment from being exfiltrated into mailboxes/Teams channels outside the portal's controls. See `docs/security-design.md` §10.

## 12. Users & Task Assignment

- A customer can have multiple **users** associated with it, not just a single primary contact.
- Each task can be assigned to one responsible party: either one of the customer's users or an admin.
- Only admins can assign or reassign who is responsible for a task.
- Notifications for a task go to the specific user assigned to it (customer user or admin), instead of always going to a generic customer contact or all admins.
- If a task has no assignee, notifications fall back to the customer's primary contact (customer side) or all admins (admin side), as today.

## 13. Project Templates

- In addition to individual task templates (see `docs/architecture-design.md`), the portal supports **project templates**: a named, reusable bundle of task templates (e.g. "Fabric Standard Onboarding" = a fixed set of 20 tasks).
- Unlike task templates, project templates are **not** git-authored. Admins create and edit them live in the portal UI (name, description, and the list of bundled task-template id+version refs), stored in the application database — this lets admins add/adjust a project template without needing a PR.
- When creating a new project, an admin can optionally start from a project template, which pre-selects its bundled tasks for the project.
- After a project is created from a template, the task list remains fully adjustable — admins can still add, remove, or mark tasks as not applicable, exactly as when building a project from scratch.

## 14. Admin/Reporting Extraction API

- The portal exposes a data-extraction API intended for reporting: it is called on a schedule from Azure Data Factory (ADF), which feeds a data warehouse and Power BI dashboards for project managers. The same API also backs the admin app's own dashboard views.
- **Authentication**: a **separate client app registration** authenticating with a **certificate** (client-credentials OAuth2) — no static API keys and no managed identity (unreliable cross-tenant to a custom API). The reporting/dashboard role (`Extract.Read`) carries **no secrets**; the provisioning pipeline's secret retrieval uses a distinct `Secret.Consume` role on its own path (see `docs/authentication-and-access.md` §10 and `docs/api-design.md`).
- **Incremental extraction**: the API supports filtering by a "changed since" timestamp so ADF only pulls new or changed records on each run, rather than a full snapshot every time.
- **Project/task status data**: for each project, returns the list of tasks with their current status, plus a summary count of how many tasks are done out of the total.
- **Notifications data**: returns the full, raw notification history (every notification sent, to whom, and when) — filtering and aggregation for reporting purposes is handled downstream in Power BI, not by the API itself.

## 15. Open Questions

None currently — all prior open questions have been resolved.

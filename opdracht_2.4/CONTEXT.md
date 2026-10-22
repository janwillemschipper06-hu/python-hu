# Customer Onboarding Portal

A web portal that guides customers through the requirements they must prepare before a
Microsoft Fabric solution is installed, and lets 9altitudes staff track and review that work.

## Language

### Actors

**Admin**:
9altitudes staff member with full access to all customers, projects, and templates. A **B2B guest**
of the dedicated identity tenant, homed in the 9altitudes corporate tenant, whose admin authority
comes from a **direct `Admin` app-role assignment** on their user (on the API app) — carried in
the signed token, never from a database flag. Invited and managed from the portal admin view.
_Avoid_: agent, operator, internal user, tenant member

**PM**:
9altitudes staff member who creates **Projects** and proposes their deadline. Sees every Project
(not only assigned ones) but, unlike an Admin, cannot approve a Project. Holds the `PM` app role.
_Avoid_: project manager (as a customer-side contact)

**Customer user**:
A person invited into the portal as a **B2B guest** of the identity tenant and assigned by an admin
to one or more **Projects** (not to Customers). Self-service sign-up is disabled, so a
customer user exists only by admin invitation. The only actor that fills in a project's onboarding
tasks. Each carries a label (Customer project manager, Functional, Technical) that is informational
only, with identical access. Never called "PM", which is reserved for the 9altitudes role.
_Avoid_: contact, person, client

### Work

**Project**:
A single piece of work (an installation or a migration) for one **Customer**. The unit that tasks,
templates, deadlines and user assignment hang off. Created by a PM or Admin; Admin approves it.
Access and isolation are scoped to the Project, never to the Customer. Lifecycle: `Draft` (visible
only to its author, a PM or Admin) → `Requested` (submitted by the PM) → `Approved` (Admin approves or
moves the deadline) → `In progress` (customer work started) → `Ready` (all requirements filled and
reviewed, so a consultant can start; says nothing about the installation itself being done).
_Avoid_: installation, migration, engagement, onboarding

**Project definition**:
The structured answers that describe what a Project is: requester and department, customer contacts,
customer type, connectors (source system, license count, content packs), installation type, Power BI
license, environments, required checks, hours and deadline. Filled in by a PM or Admin while the Project
is `Draft`; locked for the PM after submit. It is *not* a task. It determines which tasks the Project
needs and for whom (9altitudes or customer). The old single "installation type" code is a display-only
squash of these answers.
_Avoid_: form, request form, installation record

**Project task**:
A requirement that must be completed for a Project (an account, a secret, an action), assigned to
9altitudes or to the customer. Derived from the Project definition, via a template. Distinct from the
Project definition.
_Avoid_: question, requirement (as a generic)

**Consultant**:
The Admin assigned to a Project at approval (required) who carries out the installation or migration.
Always an Admin; gets no access beyond Admin. Links the one **communication ticket** to the Project.
_Avoid_: installer, assignee

**Request ticket**:
The Freshdesk ticket the portal creates when an Admin approves a Project (blocking), emailing the
requester PM. Distinct from the **communication ticket**, which the consultant links afterwards.
_Avoid_: installation ticket

**Customer**:
The organization a Project is for. Owned by FO (the source system) and only referenced in the portal
as a read-only external table; the portal never creates or edits one. Its sole purpose is to be the
parent a Project is assigned to.
_Avoid_: client, account, tenant

**Service principal**:
The non-interactive Entra identity used by Azure Data Factory to call the reporting extraction API
(`/api/v1/extract/*`, `Extract.Read` app role). A **separate client app registration that
authenticates with a certificate** (client-credentials). Never a human.
_Avoid_: API key, bot

**Identity tenant**:
The dedicated, standard **workforce Entra tenant** created for this portal that holds all human
identities **as B2B guests** — admins invited from the 9altitudes corporate tenant (their home
directory) and customer users from their own organizations; there are no member humans. Separate
from both the 9altitudes corporate directory and the tenant hosting the application's Azure
resources.
_Avoid_: External ID tenant, CIAM tenant, B2C tenant

**Invite**:
The single admin action that grants access: atomically it issues an Entra B2B guest invitation,
creates/reuses the `Users` row (role), and assigns the role as a direct Entra app-role assignment. It
does not link the person to any customer — Project assignment happens when a Project is approved
(ADR-0013). It never emails a secret that grants access — access
derives only from a verified Entra identity plus our own rows.
_Avoid_: invite link, invite token, sign-up

**Admin app-role assignment**:
The direct assignment of the `Admin` app role to an admin's **user** on the API app registration
(`cop-api-dev`) — an Entra `appRoleAssignment`, *not* a group. It *is* admin authority: an assigned
user's token carries `roles: ["Admin"]`. Created/removed from the portal via Microsoft Graph
(`AppRoleAssignment.ReadWrite.All`); the first admin is bootstrapped (and recovered) by assigning the
role in the `cop-api-dev` enterprise app. Assigning the role to a **group** would need Entra ID P1 and
is not used (see [ADR-0011](docs/adr/0011-admin-app-role-assigned-directly-to-users.md)).
_Avoid_: Portal-Admins group, admin role table, admin flag

### Secret handling

**Secret**:
A sensitive value submitted by a customer (password, client secret, API key). Stored in the portal
database as **ciphertext only** under application-layer envelope encryption, decryptable
server-side by the backend for the onboarding pipeline (machine retrieval) or an admin reveal. Never
returned in plaintext except through those authenticated, audited paths.
_Avoid_: password (too narrow), credential

**DEK / KEK**:
The two-tier envelope keys protecting a Secret. The **DEK** (Data Encryption Key) is a random
256-bit key that AES-256-GCM-encrypts one secret value; the **KEK** (Key Encryption Key) is the
HSM-backed key in Key Vault Premium that **wraps** the DEK. The backend's managed identity can
wrap/unwrap but not export the KEK; the database never holds the KEK.
_Avoid_: master key, root key

**Opened**:
The Secret lifecycle state entered when a value is **revealed to an admin or consumed by the
pipeline**. An opened secret is eligible for purge (short grace) unless marked `pipeline-required`.
States: `stored` → `opened` → `purged`.
_Avoid_: read, accessed, used

**Purge**:
Crypto-erasing a Secret's ciphertext so the value is unrecoverable, keeping only value-free audit
metadata. Runs **daily** for opened secrets and on **onboarding completion** for any secret even if
never opened. Replacement of a secret overwrites in place (no plaintext history).
_Avoid_: delete, expire, archive

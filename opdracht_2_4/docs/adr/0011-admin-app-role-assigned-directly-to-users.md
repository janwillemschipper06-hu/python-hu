# Admin authority is a direct `Admin` app-role assignment on the user, managed via Graph

**Status:** accepted (supersedes the group mechanism in
[ADR-0005](./0005-dedicated-workforce-tenant-invite-only-access.md))

Admin authority is a **direct `Admin` app-role assignment on the individual user** — an Entra
`appRoleAssignment` on the API app's service principal (`cop-api-dev`) — created and removed **from
the portal via Microsoft Graph**. There is **no `Portal-Admins` security group**. The access token
still carries `roles: ["Admin"]` exactly as before, so no backend, guard, or token-shape change
follows from this decision; only the **provisioning mechanism** changes.

## Context

[ADR-0005](./0005-dedicated-workforce-tenant-invite-only-access.md) anchored admin authority in an
Entra **`Portal-Admins` security group** mapped to the **`Admin` app role**. Assigning an app role to
a **group** requires **Entra ID P1**, which the dev identity tenant does **not** have — and which we
do **not** want to make a prerequisite for production either, for a small, known set of admins.

Assigning the same app role **directly to a user** (or to a service principal) requires **no premium
license** and is fully supported by Microsoft Graph. The authority still lives in the **signed token**
(`roles: ["Admin"]`), so ADR-0005's core property — *admin is in Entra, never a DB flag* — is
preserved; only the assignment target changes from *group* to *user*.

## Considered options

- **Buy Entra ID P1 and keep the group-based model.** Rejected: a licensing cost and dependency taken
  on purely to assign a role to a handful of admins, with no other need for P1 features.
- **Direct `Admin` app-role assignment on each user, via Graph (chosen).** No license dependency;
  the portal creates/deletes an `appRoleAssignment` per admin. Promote/demote is one Graph call.
- **DB admin flag.** Rejected for the same reason as ADR-0005/ADR-0002: the DB/operator layer is
  untrusted, so authority must be a signed-token claim, not a database row.

## Decision

- **Assignment:** the portal backend creates an app-role assignment via Microsoft Graph, e.g.
  `POST /servicePrincipals/{cop-api-dev-sp-id}/appRoleAssignedTo` with
  `{ principalId: <user oid>, resourceId: <cop-api-dev sp oid>, appRoleId: <Admin role id> }`.
  Demotion deletes that assignment. Every human is still a **B2B guest**; only admins additionally
  receive the app-role assignment (customers receive `UserCustomers` links instead).
- **Graph permission:** the backend needs **`AppRoleAssignment.ReadWrite.All`** (application
  permission, admin-consented) in place of the previously-anticipated `GroupMember.ReadWrite.All`.
  B2B invitation (`User.Invite.All`) and directory read to resolve users are unchanged.
- **Bootstrap / manual fallback:** the first admin (and any out-of-band recovery) is assigned in the
  Entra admin center — **Enterprise applications → `cop-api-dev` → Users and groups → Add assignment
  → Users → select the user → role Portal Admin**. This is the chicken-and-egg bootstrap that was
  previously the group-owner role.

## Consequences

- **No Entra ID P1 dependency** in dev or prod; the reference-table `Portal-Admins` group row is
  dropped rather than deferred.
- The **Invite** action (ADR-0005; `authentication-and-access.md` §3.2) provisions an admin by
  creating the app-role assignment, not by adding group membership. **Promote/demote** (Stage 6)
  create/delete that assignment.
- **`AppRoleAssignment.ReadWrite.All` is tenant-wide and high-privilege** — it can grant any app role
  for any application in the tenant. Accepted as the supported path for this dedicated, single-purpose
  identity tenant: it is an **app-only, admin-consented** permission held by the backend's identity,
  and app-role-assignment changes are **audited** (`authentication-and-access.md` §12). Revisit if a
  tighter Graph scoping model becomes available.
- **No code change:** guards still check `roles: ["Admin"]` (`api/app/core/security.py`); the `Users`
  table still only *mirrors* the role for display.
- A **P1 group-based model remains a possible future optimization** if P1 is ever adopted for other
  reasons, but it is **not used** and the `Portal-Admins` term is retired from the design.

Full design in [authentication-and-access.md](../authentication-and-access.md).

# Four Entra app roles; sign-in requires guest status AND an assigned role

**Status:** accepted (extends [ADR-0011](./0011-admin-app-role-assigned-directly-to-users.md): the
direct-assignment mechanism now applies to every portal role, not just `Admin`)

Every identity that can call the API holds **exactly one app role** on the API app (`cop-api-<env>`),
assigned **directly** via Microsoft Graph. The API trusts only the signed token's `roles` claim.

| Role value | Holder | Meaning |
|---|---|---|
| `Admin` | human (guest) | Administration, including inviting users and changing roles |
| `PM` | human (guest) | Project manager |
| `User` | human (guest) | Default portal user |
| `Extract.Read` | ADF client app (machine) | Read-only reporting extract (ADR-0009/0010) |

## Decisions

- **Two prerequisites to sign in:** the person must be an invited B2B **guest** *and* hold one of the
  three human roles. Enforced by Entra itself: the API's service principal has
  **"Assignment required" = true**, so a guest with no role cannot obtain a token for the API at all.
  The API additionally rejects (403) a token carrying none of `Admin`/`PM`/`User` on the portal
  router (defense in depth).
- **Roles live only in Entra.** There is no role column in the database (the former
  `Users.RoleMirror` was dropped as it could drift). The admin user list reads current roles live
  from Graph (`appRoleAssignedTo`). A DB or SQL bug cannot grant privilege (see
  `docs/authentication-and-access.md` §2.2).
- **One role per user.** Changing a role assigns the new role first, then removes the others, so a
  user is never role-less mid-change. Deactivate removes all roles.
- **Role GUIDs are pinned** (identical in every environment) in
  `scripts/entra/Provision-IdentityTenant.ps1` and mirrored as constants in
  `api/app/integrations/graph.py` (`PORTAL_ROLES`). The former `GRAPH_ADMIN_APP_ROLE_ID` /
  `entraAdminAppRoleId` per-environment config is removed.
- **No authorization data other than the role lives in this layer.** What a `PM` or `User` may see
  or do is the application's concern, built on the verified `roles` claim.

## Adding a role

1. Add it to `$apiAppRoles` in the provisioning script with a new pinned GUID and re-run the script
   (it re-applies the app roles idempotently).
2. Add the value + GUID to `PORTAL_ROLES` in `graph.py`, a member to `Role` in
   `modules/users/schemas.py`, and a constant/guard in `core/security.py`.
3. Update the table above.

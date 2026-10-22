# Entra provisioning — identity tenant

`Provision-IdentityTenant.ps1` builds **every Microsoft Entra object the portal needs in the
identity tenant**, idempotently, so **dev and prod are provisioned the same way**. Re-running never
duplicates objects — existing ones are reused.

## What it creates (identity tenant)

| Object | Notes |
|---|---|
| `cop-api-<env>` app + SP | Audience app. App roles **Admin** + **Extract.Read** and the **access_as_user** scope, all with **pinned GUIDs** so dependent config never churns. The SP object ID is the `GRAPH_API_SP_OBJECT_ID` / `entraApiSpObjectId`. |
| `cop-spa-<env>` app + SP | Public SPA client (PKCE redirect URIs), delegated to `access_as_user`, **pre-authorized** so users get no consent prompt. |
| `cop-graph-<env>` **SP only** | The app **registration** lives in the **resource/corporate tenant** (created by IT, with the federated credential to the UAMI). This script only provisions its SP here and grants the **four Microsoft Graph application permissions directly on the SP** (option 4 — nothing is consented in the resource tenant). |
| Bootstrap admin *(optional, `-BootstrapAdminEmail`)* | Invites a B2B guest and assigns the **Admin** app role directly on the `cop-api` SP (ADR-0011). |
| `cop-adf-<env>` *(always created)* | Stage 9 ADF reporting machine client + its **Extract.Read** application app-role assignment on the `cop-api` SP, and (with `-AdfCertPath`) its certificate. |

> **No admin group — by design.** There is deliberately **no `Portal-Admins` group**. Assigning an app
> role to a group needs Entra ID P1, which this tenant neither has nor requires. Admin authority is a
> **direct `Admin` app-role assignment on the user** (ADR-0011) — that's the bootstrap-admin step, and
> from Stage 5 the portal creates/removes these assignments itself via Graph.

### Coverage by plan stage (Entra work only)

| Stage | Entra work | In this script |
|---|---|---|
| 1 | cop-api (Admin role, `access_as_user`, identifier URI) + bootstrap admin; cop-spa (redirect URIs, public-client, delegated API access) | ✅ |
| 4 | finalised SPA redirect URIs | ✅ (`-SpaRedirectUris`) |
| 5 | cop-graph SP + `User.Invite.All` + `AppRoleAssignment.ReadWrite.All` | ✅ |
| 6 | cop-graph SP + `User.ReadWrite.All` + `User.Read.All` | ✅ (all four granted together) |
| 9 | `Extract.Read` role on cop-api + cop-adf client + assignment + cert | ✅ (role + client always; cert via `-AdfCertPath`) |
| 7 | Conditional Access + cross-tenant inbound MFA trust | ❌ **requires Entra ID P1** (tenant is Free) — do once licensed |

**Not touched** (resource tenant / deploy-time): the `cop-graph` app registration + its federated
credential, the user-assigned managed identity (UAMI), and the Container Apps built-in auth (EasyAuth)
config / `allowedApplications` ADF allowlist (those are infra/bicep, not Entra objects).

## Prerequisites

- **Global Administrator** (or Privileged Role Administrator) in the identity tenant — required to
  grant the Graph application permissions and the Admin role.
- Microsoft Graph PowerShell: `Install-Module Microsoft.Graph -Scope CurrentUser`

## Run it

```powershell
# DEV (defaults)
./Provision-IdentityTenant.ps1

# DEV + bootstrap the first admin
./Provision-IdentityTenant.ps1 -BootstrapAdminEmail 'you@9altitudes.com'

# DEV + also create the Stage 9 ADF reporting client (optionally with its certificate)
./Provision-IdentityTenant.ps1 -AdfCertPath 'C:\path\to\cop-adf-dev.cer'

# PROD (override the per-environment inputs)
./Provision-IdentityTenant.ps1 `
    -IdentityTenantId '<prod identity tenant id>' `
    -EnvSuffix 'prod' `
    -SpaRedirectUris @('https://<prod-spa-origin>') `
    -GraphAppClientId '<prod cop-graph client id from the resource tenant>' `
    -InviteRedirectUrl 'https://<prod-spa-origin>'
```

The script prints a **summary block** of every resulting ID at the end.

## After running — update config (important)

Recreating `cop-api` / `cop-spa` yields **new client IDs**. The **pinned** app-role and scope GUIDs
do **not** change, but you must update these and redeploy:

- `infra/environments/<env>/main.bicepparam`: `entraApiClientId`, `entraApiAudience`,
  `entraApiSpObjectId`, `entraSpaClientId` (and `entraGraphClientId` if the resource-tenant app changed).
- Frontend build variable `VITE_SPA_CLIENT_ID` (the `cop-spa` client ID).
- **Redeploy** so Container Apps built-in auth (EasyAuth) validates tokens against the new app.

Then record the new IDs in `docs/entra-configuration.md` §2 and the plan's reference table, and run an
**Invite** test on dev to confirm Graph provisioning works end to end.

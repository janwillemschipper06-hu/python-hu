# Deploy — Customer Onboarding Portal (minimum deploy)

This is the **walking skeleton**: every Azure resource in Bicep, a minimal
FastAPI API, and a Static Web App wired to it through the shared APIM gateway.
It exists so the development cycle can start against real infrastructure.

## What gets deployed

| Layer | Resource | Name (`{prefix}-{workload}-{env}` = `cst-cop-dev`) |
|-------|----------|-----------------------------------------------------|
| Identity | User-assigned managed identity | `id-cst-cop-dev` |
| Compute | Container App (internal ingress) — the Data API | `ca-cst-cop-dev` |
| Frontend | Static Web App (React/Vite SPA) | `stapp-cst-cop-dev` |
| Data | SQL database on the **shared** SQL server | `sqldb-cst-cop-dev` |
| Secrets | Key Vault (RBAC, empty for now) | `kv-cst-cop-dev` |
| Observability | Log Analytics + Application Insights | `log-/appi-cst-cop-dev` |

The **shared** SQL server, ACR, and Container App Environment are referenced as
existing resources (owned by `9A-Ops-BI-Shared-Infra`) and are never modified by
this deployment.

## Architecture decisions

- **Single-pass deploy with a user-assigned identity** — [docs/adr/0003](adr/0003-user-assigned-identity-single-pass-deploy.md).
- **Python + FastAPI backend** — [docs/adr/0004](adr/0004-backend-python-fastapi.md).
- **Internal-only ingress**; the browser reaches the API through APIM, not the
  Container App directly — [architecture-design.md §6](architecture-design.md).

## Pipeline (Azure DevOps)

`.devops/pipelines/deploy.yml` orchestrates:

```
DetectChanges → BuildImages → Infra → Database → ContainerApp → StaticWebApp
```

- **BuildImages** builds and pushes `cop-api:<BuildId>` to the shared ACR *before*
  Infra, so the Container App revision provisions healthy on port `8001`/`/health`.
- **Infra** deploys the Bicep as a subscription-scoped deployment stack named
  `cop-<env>`, then persists its outputs to the `ba-9a-cop-<env>` variable group.
- **Database** builds the SQL project (`database/`) to a DACPAC, publishes it to
  `sqldb-cst-cop-<env>` with `sqlpackage`, then creates the contained SQL user for
  the app's user-assigned managed identity `id-cst-cop-<env>` (granted
  `db_datareader`). The post-deploy script seeds static demo customer rows.
- **ContainerApp** repoints the app at the freshly built image (used on app-only
  reruns where Infra is skipped). It runs after Database so the app's SQL user
  exists before the API connects.
- **StaticWebApp** builds the SPA with `VITE_API_BASE_URL` and deploys `frontend/dist`.

`dev` deploys from `develop`; `prod` deploys once a change lands on `main`.

## One-time setup you must provide

> **Concrete variable-group values** (the actual `rg-cst-shared-dev`,
> `crcstshareddev.azurecr.io`, `sharedCaeId`, subscription IDs, etc.) live in
> [docs/ado-variable-groups.md](ado-variable-groups.md). The `shared*` values are
> written automatically by the shared-infra pipeline — you don't type them.

The pipeline expects these to already exist:

1. **Service connection** — an ARM service connection referenced by the
   `azureSubscription` variable (define it in the variable group).

2. **Variable group `ba-9a-shared-dev`** (published by `9A-Ops-BI-Shared-Infra`):
   `sharedResourceGroupName`, `sharedSqlServerName`, `sharedSqlServerFqdn`,
   `sharedAcrName`, `sharedAcrLoginServer`, `sharedCaeId`, and `azureSubscription`.

3. **Variable group `ba-9a-cop-dev`** (create it; the infra stage fills in the
   deployment outputs). Set manually up front:
   - `VITE_API_BASE_URL` → `https://api-himal-dev.9altitudes.com/cop`
   - `azureSubscription` (if not in the shared group)

   The infra stage writes back: `staticWebAppDeploymentToken` (secret),
   `sqlServerFqdn`, `sqlDatabaseName`, `acrLoginServer`, `containerAppName`,
   `resourceGroupName`.

4. **APIM route (wired by hand, out of Bicep scope)** — expose the internal
   Container App at `https://api-himal-dev.9altitudes.com/cop`. The app's
   `ROOT_PATH=/cop` makes Swagger/OpenAPI resolve behind that prefix.

5. **SQL access for the deploy identity** — the Database stage connects to the
   shared SQL server with the `azureSubscription` service principal, so that
   principal must be a **SQL Entra admin** (directly or via the admin group) on
   the shared server — a one-time grant owned by `9A-Ops-BI-Shared-Infra`. The
   app's contained user is created `WITH SID` (derived from the managed
   identity's client/application id — Azure SQL matches managed identities by
   client id), so **no Directory Readers** grant is required on the shared SQL
   server's identity.

## Local development

```bash
# API
python -m venv .venv && .venv/Scripts/pip install -r api/requirements.txt httpx pytest
.venv/Scripts/python -m pytest api/tests

# Frontend
cd frontend && npm install && npm run dev
```

Validate the Bicep without an Azure connection:

```bash
az bicep build --file infra/main.bicep
```

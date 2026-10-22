# ADO variable groups — concrete values

This is the copy-paste reference for the Azure DevOps variable groups the
Onboarding Portal pipeline (`.devops/pipelines/deploy.yml`) consumes. Values are
derived from `9A-Ops-BI-Shared-Infra` (`infra/main.bicep` naming
`{prefix}-{workload}-{env}` with `prefix=cst`, shared `workload=shared`) and its
`docs/ado-setup.md`.

> **Key point:** you do **not** hand-type the `shared*` values. The
> `9A-Ops-BI-Shared-Infra` pipeline *writes* them into `ba-9a-shared-<env>`
> automatically after its first successful deploy. The values below are what
> they resolve to today — use them to **verify**, not to seed.

The portal pipeline pulls from **two** groups (see `templates/variables.yml`):

| Group | Owner | You set by hand | Auto-populated |
|-------|-------|-----------------|----------------|
| `ba-9a-shared-<env>` | 9A-Ops-BI-Shared-Infra | `azureSubscription`, `location` | all `shared*` |
| `ba-9a-cop-<env>` | this repo | `VITE_API_BASE_URL` | the infra-stage outputs |

---

## 1. `ba-9a-shared-dev` (already exists — owned by shared-infra)

You only make sure this group exists, is **authorized for the portal pipeline**
(Library → group → *Pipeline permissions* → add the portal pipeline), and that
the shared-infra pipeline has run once for `dev`.

Set by hand (already set for the shared repo):

| Variable | Value |
|----------|-------|
| `azureSubscription` | *name of the existing **dev** ARM service connection* → BA Dev-Test sub `7b357485-7303-484f-89a7-c98145c9114e` (confirm the exact connection name in ADO → Project settings → Service connections) |
| `location` | `swedencentral` |

Auto-written by shared-infra (do **not** set by hand — shown for verification):

| Variable | Value |
|----------|-------|
| `sharedResourceGroupName` | `rg-cst-shared-dev` |
| `sharedSqlServerName` | `sql-cst-shared-dev` |
| `sharedSqlServerFqdn` | `sql-cst-shared-dev.database.windows.net` |
| `sharedAcrName` | `crcstshareddev` |
| `sharedAcrLoginServer` | `crcstshareddev.azurecr.io` |
| `sharedCaeName` | `cae-cst-shared-dev` |
| `sharedCaeId` | `/subscriptions/7b357485-7303-484f-89a7-c98145c9114e/resourceGroups/rg-cst-shared-dev/providers/Microsoft.App/managedEnvironments/cae-cst-shared-dev` |
| `sharedLogAnalyticsWorkspaceId` | `/subscriptions/7b357485-7303-484f-89a7-c98145c9114e/resourceGroups/rg-cst-shared-dev/providers/Microsoft.OperationalInsights/workspaces/log-cst-shared-dev` |

> The portal consumes `sharedResourceGroupName`, `sharedSqlServerName`,
> `sharedSqlServerFqdn`, `sharedAcrName`, `sharedAcrLoginServer`, `sharedCaeId`
> and `azureSubscription`. The extra `shared*` vars are harmless.

---

## 2. `ba-9a-cop-dev` (create this — owned by this repo)

Must exist **before the first pipeline run** — the infra stage does a GET+PUT
against it and fails with *"Variable group not found"* if it is absent. The
pipeline **Build Service** identity needs **Administrator** on this group
(Library → group → Security) so it can write the outputs back.

Set by hand up front:

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://api-himal-dev.9altitudes.com/cop` |

Auto-written by the portal infra stage (do **not** set by hand):

| Variable | Notes |
|----------|-------|
| `staticWebAppDeploymentToken` | secret |
| `sqlServerFqdn` | = shared SQL FQDN |
| `sqlDatabaseName` | `sqldb-cst-cop-dev` |
| `acrLoginServer` | = shared ACR login server |
| `containerAppName` | `ca-cst-cop-dev` |
| `resourceGroupName` | `rg-cst-cop-dev` |

Create it:

```bash
az pipelines variable-group create \
  --name ba-9a-cop-dev \
  --authorize true \
  --variables VITE_API_BASE_URL="https://api-himal-dev.9altitudes.com/cop"
```

---

## 3. Prod values (`ba-9a-shared-prod` / `ba-9a-cop-prod`)

Same naming with `env=prod`, region `westeurope`, BA Prod subscription
`5af2476c-d6da-452e-a777-915d766aea73`.

`ba-9a-shared-prod` — set by hand: `azureSubscription` (prod ARM service
connection → sub `5af2476c-…`), `location=westeurope`. Auto-written:

| Variable | Value |
|----------|-------|
| `sharedResourceGroupName` | `rg-cst-shared-prod` |
| `sharedSqlServerName` | `sql-cst-shared-prod` |
| `sharedSqlServerFqdn` | `sql-cst-shared-prod.database.windows.net` |
| `sharedAcrName` | `crcstsharedprod` |
| `sharedAcrLoginServer` | `crcstsharedprod.azurecr.io` |
| `sharedCaeName` | `cae-cst-shared-prod` |
| `sharedCaeId` | `/subscriptions/5af2476c-d6da-452e-a777-915d766aea73/resourceGroups/rg-cst-shared-prod/providers/Microsoft.App/managedEnvironments/cae-cst-shared-prod` |
| `sharedLogAnalyticsWorkspaceId` | `/subscriptions/5af2476c-d6da-452e-a777-915d766aea73/resourceGroups/rg-cst-shared-prod/providers/Microsoft.OperationalInsights/workspaces/log-cst-shared-prod` |

`ba-9a-cop-prod` — set by hand: `VITE_API_BASE_URL` →
`https://api-himal.9altitudes.com/cop` *(confirm the prod hostname — dev uses the
`-dev` suffix; prod almost certainly drops it, but verify the APIM gateway host)*.

---

## 4. Values that are **not** derivable from source (get them from ADO)

| What | Where to get it |
|------|-----------------|
| `azureSubscription` exact **service-connection name** | ADO → Project settings → Service connections (the connection targeting sub `7b357485-…` for dev / `5af2476c-…` for prod). The subscription IDs are known; the connection *name* is a control-plane label. |
| `staticWebAppDeploymentToken` | Generated at deploy time; the pipeline writes it into `ba-9a-cop-<env>`. Never set by hand. |
| Prod APIM hostname for `VITE_API_BASE_URL` | Confirm on the APIM instance / DNS. |

## 5. Order of operations

1. Run `9A-Ops-BI-Shared-Infra` for `dev` → populates `ba-9a-shared-dev`.
2. Create `ba-9a-cop-dev` with `VITE_API_BASE_URL`; grant Build Service
   **Administrator** on it; authorize both groups for the portal pipeline.
3. Run the portal pipeline.
4. Wire APIM `/cop` → the internal Container App by hand
   (`ROOT_PATH=/cop` handles the prefix).

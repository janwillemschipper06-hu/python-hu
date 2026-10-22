using '../../main.bicep'

// General
param prefix = 'cst'
param workload = 'cop'
param environment = 'dev'
param location = 'swedencentral'

// Shared foundational infrastructure (rg-cst-shared-dev) — published by
// 9A-Ops-BI-Shared-Infra into the ba-9a-shared-dev variable group and injected
// at deploy time via environment variables.
param sharedResourceGroupName = readEnvironmentVariable('SHARED_RESOURCE_GROUP_NAME', '')
param sharedSqlServerName = readEnvironmentVariable('SHARED_SQL_SERVER_NAME', '')
param sharedSqlServerFqdn = readEnvironmentVariable('SHARED_SQL_SERVER_FQDN', '')
param sharedAcrName = readEnvironmentVariable('SHARED_ACR_NAME', '')
param sharedAcrLoginServer = readEnvironmentVariable('SHARED_ACR_LOGIN_SERVER', '')
param sharedCaeId = readEnvironmentVariable('SHARED_CAE_ID', '')

// The pipeline builds and pushes the real API image to the shared ACR before
// the infra deploy, so the container app references it and configures the
// registry with the app identity for the pull.
param useAcrRegistry = true

// Container App (dev sizing)
param containerCpu = '0.5'
param containerMemory = '1Gi'
param containerMaxReplicas = 3

// Shared APIM subnet allowed to reach the Container App ingress (deny all else).
param apimSubnetCidr = '10.194.101.0/29'

// Entra authentication (identity tenant) — non-secret identifiers from
// docs/authentication-implementation-plan.md (Stage 1 Entra reference values).
// Consumed by Container Apps built-in auth (EasyAuth) in resources.bicep, which
// validates every token at the edge and injects the caller's claims (ADR-0010).
param entraTenantId = '0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52'
param entraApiAudience = 'api://884c1ef6-d4ec-4098-9f56-2f2192e60d62'
// Application (client) ID of the API app registration (cop-api-dev) — the
// EasyAuth Entra provider registration client ID.
param entraApiClientId = '884c1ef6-d4ec-4098-9f56-2f2192e60d62'
// The identity tenant is a dedicated, standard workforce Entra tenant (ADR-0005),
// so tokens are issued from the standard workforce host. Keep this host so the
// configured issuer matches tokens acquired by the Stage 4 SPA (and any Stage 1
// test token) against login.microsoftonline.com.
param entraAuthorityHost = 'login.microsoftonline.com'
// Additional machine-caller appid allowlist (Container Apps built-in auth),
// enforced alongside the always-included SPA client ID (entraSpaClientId below)
// so the interactive SPA is admitted without being listed here. Empty until the
// ADF reporting client (cop-adf-dev) is created and added in Stage 9.
param entraAllowedApplications = ['fbe02bce-ee96-4121-beb9-ee72d2af4d07']
// Application (client) ID of the SPA app registration (cop-spa-dev, public
// client) the browser signs in with via MSAL. Persisted to the ba-9a-cop-dev
// variable group by the infra stage and baked into the frontend build as
// VITE_SPA_CLIENT_ID (docs/authentication-implementation-plan.md, Stage 1/4).
param entraSpaClientId = 'e91fba5f-0584-4d6e-a399-6562d7bff9fb'

// Stage 5 invite-time provisioning via Microsoft Graph (docs/entra-configuration.md
// §3.E). The backend authenticates as the dedicated, secretless cop-graph-dev app
// (federated to the user-assigned managed identity) to call the identity tenant's
// Graph. Non-secret identifiers.
//
// Application (client) ID of cop-graph-dev.
param entraGraphClientId = '2e499fff-f1cf-46e7-b082-c79fe38fc972'
// Object ID of the cop-api-dev *service principal* (Enterprise Applications entry)
// in the identity tenant — the appRoleAssignedTo target for granting the Admin
// app role (ADR-0011). From identity tenant -> Enterprise applications ->
// cop-api-dev -> Properties -> Object ID.
param entraApiSpObjectId = 'fed094f0-b689-4507-9f43-fd3dc0406c1a'

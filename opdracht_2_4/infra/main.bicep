// ---------------------------------------------------------------------------
// Customer Onboarding Portal — minimum deploy.
// Target scope: subscription (needed to create the resource group).
//
// Provisions ONLY the project-specific resources and references the shared
// platform (SQL server / ACR / CAE) as existing — see architecture-design.md
// §5–§7. Modelled on 9A-Ops-BI-Advanced-Monitoring, collapsed to a single Data
// API + single Static Web App, a user-assigned identity (docs/adr/0003), and
// VNet-scoped Container App ingress (§6).
// ---------------------------------------------------------------------------

targetScope = 'subscription'

// ---------------------------------------------------------------------------
// Parameters – General
// ---------------------------------------------------------------------------

@description('Naming prefix (e.g. company abbreviation).')
param prefix string

@description('Workload or application name.')
param workload string

@allowed(['dev', 'prod'])
@description('Deployment environment.')
param environment string

@description('Azure region for all resources.')
param location string = 'swedencentral'

@description('Location for Static Web App — only available in centralus, eastus2, westus2, westeurope, eastasia.')
param staticWebAppLocation string = 'westeurope'

@description('Set to true once the shared ACR image pipeline has published the real image; false uses the public placeholder for template validation.')
param useAcrRegistry bool = false

@minValue(90)
@maxValue(730)
@description('Log Analytics retention in days for security and incident evidence.')
param logAnalyticsRetentionInDays int = 365

// ---------------------------------------------------------------------------
// Parameters – Shared foundational infrastructure (rg-cst-shared-{env})
// Published by the 9A-Ops-BI-Shared-Infra pipeline into the
// ba-9a-shared-{env} variable group and injected at deploy time.
// ---------------------------------------------------------------------------

@description('Resource group holding the shared SQL server / ACR / CAE.')
param sharedResourceGroupName string

@description('Name of the shared SQL server (app database is created on it).')
param sharedSqlServerName string

@description('Fully qualified domain name of the shared SQL server.')
param sharedSqlServerFqdn string

@description('Name of the shared Azure Container Registry.')
param sharedAcrName string

@description('Login server of the shared Azure Container Registry.')
param sharedAcrLoginServer string

@description('Resource ID of the shared Container App Environment.')
param sharedCaeId string

// ---------------------------------------------------------------------------
// Parameters – SQL Database
// ---------------------------------------------------------------------------

@description('SKU name for the SQL database (e.g. S0 for Standard tier).')
param sqlSkuName string = 'S0'

@description('Maximum database size in GB.')
param sqlMaxSizeGb int = 30

// ---------------------------------------------------------------------------
// Parameters – Container App
// ---------------------------------------------------------------------------

@description('CPU cores allocated to the container.')
param containerCpu string = '0.5'

@description('Memory allocated to the container (e.g. 1Gi).')
param containerMemory string = '1Gi'

@description('Maximum number of container replicas.')
param containerMaxReplicas int = 3

@description('CIDR of the shared APIM subnet allowed to reach the Container App ingress. The ingress denies all other sources. Differs per environment.')
param apimSubnetCidr string

@description('Fully qualified API image reference (e.g. myacr.azurecr.io/cop-api:<tag>). Built and pushed to ACR before this deployment so the container app revision provisions healthy on its real ingress port. Defaults to a public placeholder for template validation only.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Set to false to skip role assignment creation (e.g. when the deploying principal lacks Microsoft.Authorization/roleAssignments/write).')
param deployRoleAssignments bool = true

// ---------------------------------------------------------------------------
// Parameters – Entra authentication (identity tenant)
// Non-secret identifiers produced by the human's Entra setup (see
// docs/authentication-implementation-plan.md, Stage 1). Consumed by the
// Container Apps built-in auth (EasyAuth) config in resources.bicep, which
// validates every token at the platform edge and injects the caller's claims
// for the app to authorize (docs/adr/0010). tenantId/audience/clientId are
// required by resources.bicep (fail-closed): a deployment that leaves them
// blank fails instead of shipping an app with no platform auth.
// ---------------------------------------------------------------------------

@description('Directory (tenant) ID of the portal identity (Entra) tenant that issues access tokens. Required to deploy — a blank value fails the deployment (fail-closed).')
param entraTenantId string = ''

@description('Application ID URI of the API app registration (e.g. api://<client-id>) — the required token audience. Required to deploy — a blank value fails the deployment (fail-closed).')
param entraApiAudience string = ''

@description('Application (client) ID of the API app registration — the Container Apps built-in auth Entra provider registration client ID. Required to deploy — a blank value fails the deployment (fail-closed), so no environment can ship without platform auth.')
param entraApiClientId string = ''

@description('OIDC authority host for the identity (Entra) tenant. The identity tenant is a dedicated, standard workforce Entra tenant (ADR-0005), so this is the standard workforce host.')
param entraAuthorityHost string = 'login.microsoftonline.com'

@description('Additional (machine-caller) client application IDs allowed to call the API (e.g. the ADF reporting client), enforced by Container Apps built-in auth allowedApplications alongside the always-included SPA client ID. Empty in Stage 1; the ADF appid is added in Stage 9.')
param entraAllowedApplications array = []

@description('Application (client) ID of the SPA app registration (public client) the browser signs in with via MSAL. Consumed by resources.bicep (added to the Container Apps built-in auth allowedApplications allowlist so interactive SPA tokens are admitted) and also surfaced as a deployment output persisted to the ba-9a-cop-<env> variable group so the frontend (Vite) build bakes it in as VITE_SPA_CLIENT_ID. Non-secret (docs/authentication-implementation-plan.md, Stage 1/4).')
param entraSpaClientId string = ''

@description('Application (client) ID of the dedicated Graph provisioning app registration (cop-graph-<env>) in the identity tenant. The backend authenticates as this app — secretless, via a federated credential trusting the user-assigned managed identity — to call Microsoft Graph for invite-time provisioning (Stage 5; docs/entra-configuration.md §3.E). Blank disables Graph provisioning.')
param entraGraphClientId string = ''

@description('Object ID of the service principal (enterprise application) for the API app registration in the identity tenant — the appRoleAssignedTo target for granting a user the Admin app role at invite time (ADR-0011). Blank disables admin-role assignment.')
param entraApiSpObjectId string = ''

// ---------------------------------------------------------------------------
// Variables – Naming (matches Azure/naming/azurerm module conventions)
// ---------------------------------------------------------------------------

var suffix = '${prefix}-${workload}-${environment}'

var names = {
  resourceGroup: 'rg-${suffix}'
  logAnalyticsWorkspace: 'log-${suffix}'
  applicationInsights: 'appi-${suffix}'
  sqlDatabase: 'sqldb-${suffix}'
  containerApp: 'ca-${suffix}'
  staticWebApp: 'stapp-${suffix}'
  keyVault: 'kv-${suffix}'
  userAssignedIdentity: 'id-${suffix}'
}

// Path prefix the shared APIM gateway mounts this app under and strips before
// forwarding (https://api-himal-<env>.9altitudes.com/<workload>). FastAPI's
// root_path is set to it so Swagger/OpenAPI resolve behind the gateway.
var apiRootPath = '/${workload}'

var tags = {
  workload: workload
  environment: environment
  managed_by: 'bicep'
}

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: names.resourceGroup
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Module – App user-assigned managed identity (app resource group)
// Created first so its principalId is available to the AcrPull assignment
// below before the Container App provisions (docs/adr/0003).
// ---------------------------------------------------------------------------

module identity 'modules/identity.bicep' = {
  name: 'identity-${suffix}'
  scope: rg
  params: {
    name: names.userAssignedIdentity
    location: location
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module – AcrPull for the app UAMI on the shared ACR (shared resource group)
// Must complete before resources.bicep provisions the Container App.
// ---------------------------------------------------------------------------

module acrPull 'modules/acr-pull.bicep' = {
  name: 'acr-pull-${suffix}'
  scope: resourceGroup(sharedResourceGroupName)
  params: {
    sharedAcrName: sharedAcrName
    uamiPrincipalId: identity.outputs.principalId
    deployRoleAssignments: deployRoleAssignments
  }
}

// ---------------------------------------------------------------------------
// Module – App resources inside the app resource group
// dependsOn acrPull so the Container App can pull its first image.
// ---------------------------------------------------------------------------

module resources 'resources.bicep' = {
  name: 'resources-${suffix}'
  scope: rg
  dependsOn: [acrPull]
  params: {
    location: location
    staticWebAppLocation: staticWebAppLocation
    useAcrRegistry: useAcrRegistry
    tags: tags
    names: names
    environment: environment
    logAnalyticsRetentionInDays: logAnalyticsRetentionInDays
    containerCpu: containerCpu
    containerMemory: containerMemory
    containerMaxReplicas: containerMaxReplicas
    apimSubnetCidr: apimSubnetCidr
    apiRootPath: apiRootPath
    entraTenantId: entraTenantId
    entraApiAudience: entraApiAudience
    entraApiClientId: entraApiClientId
    entraAuthorityHost: entraAuthorityHost
    entraAllowedApplications: entraAllowedApplications
    entraSpaClientId: entraSpaClientId
    entraGraphClientId: entraGraphClientId
    entraApiSpObjectId: entraApiSpObjectId
    deployRoleAssignments: deployRoleAssignments
    containerImage: containerImage
    sharedAcrLoginServer: sharedAcrLoginServer
    sharedCaeId: sharedCaeId
    sharedSqlServerFqdn: sharedSqlServerFqdn
    sqlDatabaseName: names.sqlDatabase
    uamiId: identity.outputs.id
    uamiPrincipalId: identity.outputs.principalId
    uamiClientId: identity.outputs.clientId
  }
}

// ---------------------------------------------------------------------------
// Module – App SQL database on the shared SQL server (shared resource group)
// Diagnostics are routed to the app's own Log Analytics workspace.
// ---------------------------------------------------------------------------

module database 'modules/database.bicep' = {
  name: 'database-${suffix}'
  scope: resourceGroup(sharedResourceGroupName)
  params: {
    location: location
    tags: tags
    sharedSqlServerName: sharedSqlServerName
    sqlDatabaseName: names.sqlDatabase
    sqlSkuName: sqlSkuName
    sqlMaxSizeGb: sqlMaxSizeGb
    logAnalyticsWorkspaceId: resources.outputs.logAnalyticsWorkspaceId
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output resourceGroupName string = rg.name
output sqlServerFqdn string = sharedSqlServerFqdn
output sqlDatabaseName string = database.outputs.sqlDatabaseName
output containerRegistryLoginServer string = sharedAcrLoginServer
output containerAppName string = resources.outputs.containerAppName
output containerAppInternalFqdn string = resources.outputs.containerAppInternalFqdn
output containerAppUrl string = resources.outputs.containerAppUrl
output containerAppIdentityPrincipalId string = resources.outputs.containerAppIdentityPrincipalId

@description('Client (application) id of the app user-assigned managed identity. Used to build the SID of its contained SQL user — Azure SQL matches a managed identity by client id, not object id.')
output containerAppIdentityClientId string = identity.outputs.clientId

@description('Application Insights connection string.')
output applicationInsightsConnectionString string = resources.outputs.applicationInsightsConnectionString

output staticWebAppName string = resources.outputs.staticWebAppName
output staticWebAppDefaultHostname string = resources.outputs.staticWebAppDefaultHostname

// ---------------------------------------------------------------------------
// Frontend (Vite) build-time values — non-secret Entra identifiers sourced here
// from the bicepparam (single source of truth) and persisted by the infra stage
// into the ba-9a-cop-<env> variable group, which the Static Web App build reads
// as VITE_* (the build can run without Infra, so the variable group is the
// hand-off). This replaces hand-maintaining these entries in the variable group.
// ---------------------------------------------------------------------------

@description('Identity (Entra) tenant ID the SPA authenticates against (frontend VITE_ENTRA_TENANT_ID).')
output entraTenantId string = entraTenantId

@description('SPA app registration client ID the browser signs in with (frontend VITE_SPA_CLIENT_ID).')
output entraSpaClientId string = entraSpaClientId

@description('Delegated API scope the SPA requests; its token audience must equal the API audience (frontend VITE_API_SCOPE).')
output entraApiScope string = '${entraApiAudience}/access_as_user'

@description('Static Web App deployment token. Store this as a secret — do not log or expose it.')
@secure()
output staticWebAppDeploymentToken string = resources.outputs.staticWebAppDeploymentToken

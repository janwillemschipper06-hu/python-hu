// ---------------------------------------------------------------------------
// All app resources deployed inside the app resource group.
// Called from main.bicep with scope set to the resource group.
//
// Single Data API (architecture-design.md §5, api-design.md §9): one internal
// Container App fronted by the shared APIM, plus one Static Web App and the
// per-app observability + Key Vault. No admin app and no self-issued JWT — the
// portal delegates all authentication to the identity (Entra) tenant, validated
// at the platform edge by Container Apps built-in auth (api-design.md, ADR-0010).
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

param location string

@description('Location for Static Web App — limited to centralus, eastus2, westus2, westeurope, eastasia.')
param staticWebAppLocation string = 'westeurope'

@description('Set to true once the shared ACR image pipeline has published the real image; false uses the public placeholder for template validation.')
param useAcrRegistry bool = false

param tags object
param names object
param environment string

@minValue(90)
@maxValue(730)
@description('Log Analytics retention in days for security and incident evidence.')
param logAnalyticsRetentionInDays int

@description('Login server of the shared Azure Container Registry.')
param sharedAcrLoginServer string

@description('Resource ID of the shared Container App Environment.')
param sharedCaeId string

@description('Fully qualified domain name of the shared SQL server.')
param sharedSqlServerFqdn string

@description('Name of the app database on the shared SQL server (used for the SQL_DATABASE env var).')
param sqlDatabaseName string

@description('Resource ID of the app user-assigned managed identity.')
param uamiId string

@description('Principal ID of the app user-assigned managed identity.')
param uamiPrincipalId string

@description('Client ID of the app user-assigned managed identity. Passed to the API as AZURE_CLIENT_ID so its managed-identity SQL token request targets this specific identity.')
param uamiClientId string

param containerCpu string
param containerMemory string
param containerMaxReplicas int

@description('CIDR of the shared APIM subnet allowed to reach the Container App ingress. All other sources are denied.')
param apimSubnetCidr string

@description('Path prefix the public APIM gateway mounts this app under and strips before forwarding (e.g. /cop). FastAPI needs it so Swagger/OpenAPI resolve behind the gateway.')
param apiRootPath string

@description('Directory (tenant) ID of the portal identity (Entra) tenant that issues access tokens. Used to build the OpenID issuer the Container Apps built-in auth (EasyAuth) provider validates tokens against. Required — the auth config is always created (fail-closed).')
@minLength(1)
param entraTenantId string

@description('Application ID URI of the API app registration (e.g. api://<client-id>). Container Apps built-in auth requires every portal token to carry this as its audience (allowedAudiences). Required — the auth config is always created (fail-closed).')
@minLength(1)
param entraApiAudience string

@description('Application (client) ID of the API app registration. Used as the Container Apps built-in auth (EasyAuth) Microsoft Entra provider registration client ID. Required — the auth config is always created (fail-closed); a blank value fails the deployment rather than shipping an unauthenticated app.')
@minLength(1)
param entraApiClientId string

@description('OIDC authority host for the identity (Entra) tenant. The identity tenant is a dedicated, standard workforce Entra tenant (ADR-0005), so this is the standard workforce host.')
param entraAuthorityHost string = 'login.microsoftonline.com'

@description('Additional (machine-caller) client application IDs allowed to call the API — e.g. the ADF reporting client — enforced by Container Apps built-in auth (allowedApplications) alongside the always-included SPA client ID (entraSpaClientId). Empty in Stage 1; the ADF appid is added in Stage 9 (ADR-0010).')
param entraAllowedApplications array = []

@description('Application (client) ID of the SPA app registration (public client) the browser signs in with via MSAL. Added to the Container Apps built-in auth allowedApplications allowlist so interactive (delegated) SPA tokens are admitted — without it the platform rejects every browser call with 403. Optional: when blank and no machine callers are configured, the app allowlist is omitted and all platform-validated callers reach the app (which still authorizes by role).')
param entraSpaClientId string = ''

@description('Application (client) ID of the dedicated Graph provisioning app registration (cop-graph-<env>) in the identity tenant. The backend authenticates as this app — secretless, via a federated credential trusting the user-assigned managed identity — to call Microsoft Graph for invite-time provisioning (Stage 5; docs/entra-configuration.md §3.E). Optional: blank disables Graph provisioning (the invitations endpoint fails closed).')
param entraGraphClientId string = ''

@description('Object ID of the service principal (enterprise application) for the API app registration in the identity tenant. Target of the appRoleAssignedTo call that grants a user the Admin app role (ADR-0011). Required for admin invitations; blank disables admin-role assignment.')
param entraApiSpObjectId string = ''

@description('Set to false to skip role assignment creation (e.g. when the deploying principal lacks Microsoft.Authorization/roleAssignments/write).')
param deployRoleAssignments bool = true

@description('Fully qualified API image reference (e.g. myacr.azurecr.io/cop-api:<tag>). Built and pushed to ACR before this deployment so the container app revision provisions healthy on its real ingress port. Defaults to a public placeholder for template validation only.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var apiTargetPort = 8001

var diagnosticSettingName = 'send-to-log-analytics'
var staticWebAppDiagnosticLogCategories = [
  'StaticSiteDiagnosticLogs'
  'StaticSiteHttpLogs'
]

// ---------------------------------------------------------------------------
// Log Analytics & Application Insights
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logAnalyticsWorkspace
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logAnalyticsRetentionInDays
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: names.applicationInsights
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------------
// Azure Key Vault
// ---------------------------------------------------------------------------
//
// Created empty for now. It will hold the write-only external-secret-vault
// credential (docs/adr/0001) and other portal config later. The UAMI is granted
// Key Vault Secrets User here so the Container App can read those secrets once
// they exist; its AcrPull grant on the shared ACR is handled by
// modules/acr-pull.bicep before this module deploys.

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.keyVault
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 90
  }
}

resource keyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployRoleAssignments) {
  name: guid(keyVault.id, uamiId, 'key-vault-secrets-user')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Container App — the single Data API
// Deployed into the shared Container App Environment (sharedCaeId).
//
// Ingress is limited to the VNet (architecture-design.md §6): no direct public
// path. `external: true` on the internal (VNet-integrated) shared environment
// means "Limited to VNet" — reachable from anywhere in the VNet, but never the
// public internet. This is what lets the VNet-integrated shared APIM forward to
// it privately (with `external: false` the app would only be reachable from
// other apps in the same Container Apps Environment). The UAMI (docs/adr/0003)
// is the sole identity — created before this app so its AcrPull grant is
// already in place.
// ---------------------------------------------------------------------------

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.containerApp
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiId}': {}
    }
  }
  dependsOn: [keyVaultSecretsUserRoleAssignment]
  properties: {
    managedEnvironmentId: sharedCaeId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'static-webapp-url'
          value: 'https://${staticWebApp.properties.defaultHostname}'
        }
      ]
      registries: useAcrRegistry
        ? [
            {
              server: sharedAcrLoginServer
              identity: uamiId
            }
          ]
        : []
      ingress: {
        targetPort: apiTargetPort
        transport: 'http'
        allowInsecure: false
        // "Limited to VNet" — private to the VNet, not the public internet.
        external: true
        // Only the shared APIM subnet may reach the app; every other source is
        // denied (an empty allow-list of one entry = deny-all-others). APIM is
        // the single front door for the API.
        ipSecurityRestrictions: [
          {
            name: 'allow-apim-${environment}'
            action: 'Allow'
            ipAddressRange: apimSubnetCidr
            description: 'Shared APIM subnet — the only permitted ingress source.'
          }
        ]
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: {
            cpu: json(containerCpu)
            memory: containerMemory
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
            {
              name: 'SQL_SERVER'
              value: sharedSqlServerFqdn
            }
            {
              name: 'SQL_DATABASE'
              value: sqlDatabaseName
            }
            {
              // Client ID of the user-assigned managed identity. The API adds
              // it to its AAD token request for https://database.windows.net/
              // so the correct identity is used (a container app can carry more
              // than one, making the choice ambiguous without this).
              name: 'AZURE_CLIENT_ID'
              value: uamiClientId
            }
            {
              name: 'STATIC_WEBAPP_URL'
              secretRef: 'static-webapp-url'
            }
            {
              // Path prefix the public APIM gateway (api-<...>/cop) mounts this
              // app under and strips before forwarding. FastAPI needs it so the
              // Swagger UI at /cop/docs fetches /cop/openapi.json instead of
              // /openapi.json (which APIM does not route -> 404).
              name: 'ROOT_PATH'
              value: apiRootPath
            }
            {
              // Identity (Entra) tenant the Graph provisioning app lives in and
              // whose Graph the backend provisions against (Stage 5). The token
              // exchange is minted here, not in the resource tenant.
              name: 'GRAPH_TENANT_ID'
              value: entraTenantId
            }
            {
              // Dedicated, secretless Graph provisioning app (cop-graph-<env>).
              // The backend authenticates as this app via a federated credential
              // trusting the user-assigned managed identity (no stored secret).
              name: 'GRAPH_CLIENT_ID'
              value: entraGraphClientId
            }
            {
              // Service principal (enterprise app) object ID of the API app in
              // the identity tenant — the appRoleAssignedTo target for granting
              // the app roles (ADR-0012).
              name: 'GRAPH_API_SP_OBJECT_ID'
              value: entraApiSpObjectId
            }
            {
              // OIDC authority host for the identity tenant; the token exchange
              // posts the client assertion here. Reuses the built-in auth host.
              name: 'GRAPH_AUTHORITY_HOST'
              value: entraAuthorityHost
            }
          ]
          probes: [
            {
              // Gives cold starts (minReplicas: 0 outside prod, heavier
              // ODBC-driver image) up to 2 minutes to bind the port before the
              // platform kills the container for a probe failure.
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: apiTargetPort
              }
              periodSeconds: 5
              failureThreshold: 24
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: apiTargetPort
              }
              periodSeconds: 10
              failureThreshold: 3
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: apiTargetPort
              }
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 1 : 0
        maxReplicas: containerMaxReplicas
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Container Apps built-in authentication (EasyAuth) — platform token validation
// ---------------------------------------------------------------------------
//
// Authentication is offloaded to the platform (docs/adr/0010): the Container App
// validates every inbound Entra token (signature, issuer, audience, expiry) and
// injects the validated claims as the X-MS-CLIENT-PRINCIPAL header. The app
// trusts that principal and performs authorization only — it does no token
// cryptography.
//
// - API/bearer mode: unauthenticated callers get 401, never a login redirect
//   (unauthenticatedClientAction: Return401), so browsers/machines bring their
//   own token (the SPA acquires one via MSAL in Stage 4).
// - /health and /api/v1/ping stay open (excludedPaths) so the platform health
//   probes and the post-deploy smoke test are never challenged.
// - The Microsoft Entra provider validates against the identity tenant's issuer
//   and the API audience. allowedApplications gates EVERY caller by azp/appid
//   (interactive and machine alike), so it always includes the SPA client ID
//   plus any machine callers (the ADF reporting client is added in Stage 9) —
//   kept here in our Bicep rather than in the shared APIM (ADR-0010).
// - No client secret is configured: validating caller-supplied bearer tokens
//   needs only the issuer, client ID, and audience; the interactive login flow
//   (which would need a secret) is not used.
//
// The auth config is created unconditionally (fail-closed): entraTenantId,
// entraApiAudience, and entraApiClientId are required (@minLength(1)), so a
// deployment with any of them blank fails rather than shipping an app with no
// platform auth in front of it.

var entraOpenIdIssuer = 'https://${entraAuthorityHost}/${entraTenantId}/v2.0'

// Client applications whose tokens the platform admits. Container Apps built-in
// auth matches `allowedApplications` against the `azp`/`appid` of EVERY inbound
// token — interactive *and* machine — so the SPA must be listed or the platform
// returns 403 on every browser call (and an empty list admits nothing: it is
// deny-all, not allow-all). We therefore always include the SPA client ID
// alongside any machine callers (entraAllowedApplications, e.g. the Stage 9 ADF
// reporting client). When neither is configured the list is empty and the
// authorization policy is omitted entirely, so every platform-validated caller
// reaches the app, which still authorizes by role (require_admin /
// require_portal_user / require_extract_client).
var allowedCallerApplications = union(
  empty(entraSpaClientId) ? [] : [entraSpaClientId],
  entraAllowedApplications
)

// A v2 access token carries the API's client-ID (GUID) as its `aud`; a v1 token
// carries the App ID URI (api://<client-id>). Both forms are listed so the
// config tolerates either token version and never silently 403s on an audience
// mismatch (ADR-0010).
var entraTokenAudiences = [
  entraApiClientId
  entraApiAudience
]

// Omit defaultAuthorizationPolicy when there is nothing to allow — an empty
// allowedApplications array would otherwise deny every caller.
var entraValidation = empty(allowedCallerApplications)
  ? {
      allowedAudiences: entraTokenAudiences
    }
  : {
      allowedAudiences: entraTokenAudiences
      defaultAuthorizationPolicy: {
        allowedApplications: allowedCallerApplications
      }
    }

resource containerAppAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  name: 'current'
  parent: containerApp
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'Return401'
      excludedPaths: [
        '/health'
        '/api/v1/ping'
      ]
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: entraOpenIdIssuer
          clientId: entraApiClientId
        }
        validation: entraValidation
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Azure Static Web App
// ---------------------------------------------------------------------------
//
// Pure static host for the React SPA (one app, two role-based views). It never
// proxies to the Container App: the browser calls the APIM gateway directly
// (architecture-design.md §6). VITE_API_BASE_URL is a build-time value supplied
// by the deploy pipeline, not managed here.

resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: names.staticWebApp
  location: staticWebAppLocation
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

resource staticWebAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingName
  scope: staticWebApp
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      for category in staticWebAppDiagnosticLogCategories: {
        category: category
        enabled: true
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output logAnalyticsWorkspaceId string = logAnalytics.id
output containerAppName string = containerApp.name
output containerAppInternalFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppIdentityPrincipalId string = uamiPrincipalId
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
output staticWebAppName string = staticWebApp.name
output staticWebAppDefaultHostname string = staticWebApp.properties.defaultHostname

@description('Static Web App deployment token. Store this as a secret — do not log or expose it.')
@secure()
output staticWebAppDeploymentToken string = staticWebApp.listSecrets().properties.apiKey

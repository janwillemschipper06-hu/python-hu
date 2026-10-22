// ---------------------------------------------------------------------------
// AcrPull role assignment for the app UAMI on the SHARED Container Registry.
//
// Scoped to the shared resource group (via module scope in main.bicep) because
// a role assignment's `scope` can only target a resource in the current
// deployment scope. The shared ACR lives in rg-cst-shared-{env}, a different
// resource group than the app's, so the assignment must be created from a
// module deployed into the shared resource group.
// ---------------------------------------------------------------------------

@description('Name of the existing shared Azure Container Registry.')
param sharedAcrName string

@description('Principal ID of the app user-assigned managed identity.')
param uamiPrincipalId string

@description('Set to false to skip role assignment creation (e.g. during preflight validation when the deploying principal lacks Microsoft.Authorization/roleAssignments/write).')
param deployRoleAssignments bool = true

var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull built-in role
)

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: sharedAcrName
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployRoleAssignments) {
  name: guid(containerRegistry.id, uamiPrincipalId, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

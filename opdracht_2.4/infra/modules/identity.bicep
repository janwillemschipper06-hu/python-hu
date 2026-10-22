// ---------------------------------------------------------------------------
// User-assigned managed identity for the Customer Onboarding Portal API.
// Deployed in the app resource group.
//
// Extracted into its own module so its principalId is available to the
// shared-scoped AcrPull role-assignment module BEFORE the Container App in
// resources.bicep provisions — avoiding the deadlock where the Container App
// cannot pull its first image because the role assignment granting it access
// is not yet ready. See docs/adr/0003.
// ---------------------------------------------------------------------------

param name string
param location string
param tags object

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = uami.id
output principalId string = uami.properties.principalId
output clientId string = uami.properties.clientId

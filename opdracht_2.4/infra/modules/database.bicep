// ---------------------------------------------------------------------------
// Customer Onboarding Portal SQL database on the SHARED SQL server.
//
// Scoped to the shared resource group (via module scope in main.bicep) because
// an Azure SQL database MUST be co-located in the same resource group as its
// parent server. The shared server lives in rg-cst-shared-{env}; this app owns
// its own database on that server.
//
// The database is created empty. The managed-identity DB user and the
// EXECUTE-only stored procedures (docs/adr/0002) are provisioned as a later
// step and are intentionally out of scope for this minimum deploy — the
// skeleton /health endpoint does not touch SQL.
//
// Database diagnostics are sent to the APP's Log Analytics workspace (not the
// shared one) so per-app SQL security/audit evidence stays with the app.
// ---------------------------------------------------------------------------

param location string
param tags object

@description('Name of the existing shared SQL server.')
param sharedSqlServerName string

@description('Name of the app database to create on the shared server.')
param sqlDatabaseName string

@description('SKU name for the SQL database (e.g. S0 for Standard tier).')
param sqlSkuName string

@description('Maximum database size in GB.')
param sqlMaxSizeGb int

@description('Resource ID of the app Log Analytics workspace for database diagnostics.')
param logAnalyticsWorkspaceId string

var diagnosticSettingName = 'send-to-log-analytics'
var sqlDatabaseDiagnosticLogCategories = [
  'SQLSecurityAuditEvents'
  'Errors'
  'Deadlocks'
  'Timeouts'
  'Blocks'
]

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' existing = {
  name: sharedSqlServerName
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  tags: tags
  sku: {
    name: sqlSkuName
  }
  properties: {
    maxSizeBytes: sqlMaxSizeGb * 1073741824 // GB to bytes
    zoneRedundant: false
    requestedBackupStorageRedundancy: 'Local'
  }
}

resource sqlDatabaseDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingName
  scope: sqlDatabase
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      for category in sqlDatabaseDiagnosticLogCategories: {
        category: category
        enabled: true
      }
    ]
  }
}

output sqlDatabaseName string = sqlDatabase.name

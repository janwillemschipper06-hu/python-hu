using '../../main.bicep'

// General
param prefix = 'cst'
param workload = 'cop'
param environment = 'prod'
param location = 'westeurope'

// Shared foundational infrastructure (rg-cst-shared-prod) — published by
// 9A-Ops-BI-Shared-Infra into the ba-9a-shared-prod variable group and injected
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

// Container App (prod sizing)
param containerCpu = '1.0'
param containerMemory = '2Gi'
param containerMaxReplicas = 5

// Shared APIM subnet allowed to reach the Container App ingress (deny all else).
// TODO: prod APIM subnet CIDR is unknown — currently reusing the dev range as a
// placeholder. Update to the real prod subnet before the first prod deploy.
param apimSubnetCidr = '10.194.101.0/29'

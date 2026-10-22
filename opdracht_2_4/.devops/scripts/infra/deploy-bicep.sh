#!/bin/bash
# Deploy the Bicep infrastructure as a subscription-scoped deployment stack.
# Creates or updates the stack; resources removed from the template are deleted
# on subsequent runs (action-on-unmanage deleteResources).
#
# This stack also manages resources in the shared resource group (the app SQL
# database on the shared server + the AcrPull role assignment on the shared
# ACR). The shared SQL server / ACR / CAE themselves are referenced as existing
# resources owned by the 9A-Ops-BI-Shared-Infra stack, so they are never touched
# by this stack's unmanage actions.
#
# Exports outputs as Azure DevOps pipeline variables.

set -euo pipefail

LOCATION="${1:?Location is required (e.g., westeurope)}"
ENVIRONMENT="${2:?Environment is required (e.g., dev or prod)}"

STACK_NAME="cop-${ENVIRONMENT}"

# The real container image is built and pushed to ACR before this stage so the
# container app revision provisions healthy on its real ingress port. When set,
# it overrides the Bicep placeholder default; otherwise Bicep falls back to the
# public placeholder (template stays valid for local/manual runs).
IMAGE_PARAMS=()
if [[ -n "${CONTAINER_IMAGE:-}" ]]; then
  IMAGE_PARAMS+=("containerImage=$CONTAINER_IMAGE")
fi

DEPLOY_OUTPUT=$(az stack sub create \
  --name "$STACK_NAME" \
  --location "$LOCATION" \
  --template-file "infra/main.bicep" \
  --parameters "infra/environments/$ENVIRONMENT/main.bicepparam" \
  --parameters ${IMAGE_PARAMS[@]+"${IMAGE_PARAMS[@]}"} \
  --action-on-unmanage deleteResources \
  --deny-settings-mode none \
  --yes \
  --query "outputs" \
  -o json)

# @secure() outputs are redacted by ARM — retrieve the token directly from the
# resource instead of from deployment outputs.
STATIC_WEB_APP_NAME=$(echo "$DEPLOY_OUTPUT" | jq -r '.staticWebAppName.value')
RESOURCE_GROUP=$(echo "$DEPLOY_OUTPUT" | jq -r '.resourceGroupName.value')
STATIC_TOKEN=$(az staticwebapp secrets list \
  --name "$STATIC_WEB_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query 'properties.apiKey' \
  -o tsv)

echo "##vso[task.setvariable variable=staticWebAppDeploymentToken;isSecret=true]$STATIC_TOKEN"

CONTAINER_APP_URL=$(echo "$DEPLOY_OUTPUT" | jq -r '.containerAppUrl.value')
echo "##vso[task.setvariable variable=containerAppUrl]$CONTAINER_APP_URL"

echo "##vso[task.setvariable variable=resourceGroupName]$RESOURCE_GROUP"

SQL_SERVER_FQDN=$(echo "$DEPLOY_OUTPUT" | jq -r '.sqlServerFqdn.value')
echo "##vso[task.setvariable variable=sqlServerFqdn]$SQL_SERVER_FQDN"

SQL_DATABASE_NAME=$(echo "$DEPLOY_OUTPUT" | jq -r '.sqlDatabaseName.value')
echo "##vso[task.setvariable variable=sqlDatabaseName]$SQL_DATABASE_NAME"

ACR_LOGIN_SERVER=$(echo "$DEPLOY_OUTPUT" | jq -r '.containerRegistryLoginServer.value')
echo "##vso[task.setvariable variable=acrLoginServer]$ACR_LOGIN_SERVER"

CONTAINER_APP_NAME=$(echo "$DEPLOY_OUTPUT" | jq -r '.containerAppName.value')
echo "##vso[task.setvariable variable=containerAppName]$CONTAINER_APP_NAME"

# Frontend (Vite) build-time values — non-secret Entra identifiers sourced from
# the bicepparam (single source of truth). Exported here so the "Update variable
# group" step persists them into ba-9a-cop-<env>, from where the Static Web App
# stage reads them as VITE_* (that stage can run without Infra).
echo "Param file entraSpaClientId: $(grep -E '^param entraSpaClientId' "infra/environments/$ENVIRONMENT/main.bicepparam")"
echo "Stack outputs: entraSpaClientId=$(echo "$DEPLOY_OUTPUT" | jq -r '.entraSpaClientId.value') entraApiScope=$(echo "$DEPLOY_OUTPUT" | jq -r '.entraApiScope.value')"
VITE_ENTRA_TENANT_ID=$(echo "$DEPLOY_OUTPUT" | jq -r '.entraTenantId.value')
echo "##vso[task.setvariable variable=viteEntraTenantId]$VITE_ENTRA_TENANT_ID"

VITE_SPA_CLIENT_ID=$(echo "$DEPLOY_OUTPUT" | jq -r '.entraSpaClientId.value')
echo "##vso[task.setvariable variable=viteSpaClientId]$VITE_SPA_CLIENT_ID"

VITE_API_SCOPE=$(echo "$DEPLOY_OUTPUT" | jq -r '.entraApiScope.value')
echo "##vso[task.setvariable variable=viteApiScope]$VITE_API_SCOPE"

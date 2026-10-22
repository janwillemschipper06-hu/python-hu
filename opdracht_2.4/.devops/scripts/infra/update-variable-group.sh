#!/bin/bash
# Update the Azure DevOps variable group with deployment outputs so later stages
# (and app-only reruns that skip Infra) can read the resource names/token.

set -euo pipefail

ENVIRONMENT="${1:?Environment is required (e.g., dev or prod)}"
STATIC_WEB_APP_TOKEN="${STATIC_WEB_APP_TOKEN:?STATIC_WEB_APP_TOKEN environment variable is required}"
SQL_SERVER_FQDN="${SQL_SERVER_FQDN:?SQL_SERVER_FQDN environment variable is required}"
SQL_DATABASE_NAME="${SQL_DATABASE_NAME:?SQL_DATABASE_NAME environment variable is required}"
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:?ACR_LOGIN_SERVER environment variable is required}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:?CONTAINER_APP_NAME environment variable is required}"
RESOURCE_GROUP_NAME="${RESOURCE_GROUP_NAME:?RESOURCE_GROUP_NAME environment variable is required}"
VITE_ENTRA_TENANT_ID="${NEW_VITE_ENTRA_TENANT_ID:?NEW_VITE_ENTRA_TENANT_ID environment variable is required}"
VITE_SPA_CLIENT_ID="${NEW_VITE_SPA_CLIENT_ID:?NEW_VITE_SPA_CLIENT_ID environment variable is required}"
VITE_API_SCOPE="${NEW_VITE_API_SCOPE:?NEW_VITE_API_SCOPE environment variable is required}"
SYSTEM_ACCESS_TOKEN="${SYSTEM_ACCESS_TOKEN:?SYSTEM_ACCESS_TOKEN environment variable is required}"
ORG_URL="${ORG_URL:?ORG_URL environment variable is required}"
PROJECT="${PROJECT:?PROJECT environment variable is required}"

GROUP_NAME="ba-9a-cop-$ENVIRONMENT"
PROJECT_ENCODED="${PROJECT// /%20}"

if [ -z "$STATIC_WEB_APP_TOKEN" ]; then
  echo "##[error]staticWebAppDeploymentToken is empty — Bicep may not have exported this output."
  exit 1
fi

ENCODED_TOKEN=$(printf ":%s" "$SYSTEM_ACCESS_TOKEN" | base64 -w 0)

# Fetch the current variable group definition.
GROUP=$(curl -fsSL \
  -H "Authorization: Basic $ENCODED_TOKEN" \
  -H "Content-Type: application/json" \
  "${ORG_URL}${PROJECT_ENCODED}/_apis/distributedtask/variablegroups?groupName=${GROUP_NAME}&api-version=7.1")

GROUP_ID=$(echo "$GROUP" | jq -r '.value[0].id')

if [ "$GROUP_ID" = "null" ] || [ -z "$GROUP_ID" ]; then
  echo "##[error]Variable group '${GROUP_NAME}' not found."
  exit 1
fi

# variableGroupProjectReferences is required by the PUT API; default to the
# current project if absent in the GET response.
UPDATED_DEF=$(echo "$GROUP" | jq \
  --arg token "$STATIC_WEB_APP_TOKEN" \
  --arg sql_fqdn "$SQL_SERVER_FQDN" \
  --arg sql_db "$SQL_DATABASE_NAME" \
  --arg acr "$ACR_LOGIN_SERVER" \
  --arg ca_name "$CONTAINER_APP_NAME" \
  --arg rg_name "$RESOURCE_GROUP_NAME" \
  --arg vite_tenant "$VITE_ENTRA_TENANT_ID" \
  --arg vite_spa "$VITE_SPA_CLIENT_ID" \
  --arg vite_scope "$VITE_API_SCOPE" \
  --arg project "$PROJECT" \
  --arg group_name "$GROUP_NAME" '
  .value[0].variables.staticWebAppDeploymentToken = {"value": $token, "isSecret": true}
  | .value[0].variables.sqlServerFqdn = {"value": $sql_fqdn, "isSecret": false}
  | .value[0].variables.sqlDatabaseName = {"value": $sql_db, "isSecret": false}
  | .value[0].variables.acrLoginServer = {"value": $acr, "isSecret": false}
  | .value[0].variables.containerAppName = {"value": $ca_name, "isSecret": false}
  | .value[0].variables.resourceGroupName = {"value": $rg_name, "isSecret": false}
  | .value[0].variables.VITE_ENTRA_TENANT_ID = {"value": $vite_tenant, "isSecret": false}
  | .value[0].variables.VITE_SPA_CLIENT_ID = {"value": $vite_spa, "isSecret": false}
  | .value[0].variables.VITE_API_SCOPE = {"value": $vite_scope, "isSecret": false}
  | .value[0]
  | .variableGroupProjectReferences //= [{"name": $group_name, "description": "", "projectReference": {"id": null, "name": $project}}]
')

echo "Persisting: VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID VITE_SPA_CLIENT_ID=$VITE_SPA_CLIENT_ID VITE_API_SCOPE=$VITE_API_SCOPE"

RESPONSE=$(curl -sS -w "\n%{http_code}" -X PUT \
  -H "Authorization: Basic $ENCODED_TOKEN" \
  -H "Content-Type: application/json" \
  "${ORG_URL}${PROJECT_ENCODED}/_apis/distributedtask/variablegroups/${GROUP_ID}?api-version=7.1" \
  -d "$UPDATED_DEF")

HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_STATUS" != "200" ]; then
  echo "##[error]Failed to update variable group. HTTP $HTTP_STATUS: $BODY"
  exit 1
fi

# Read the group back and fail loudly if the persisted values differ from what we wrote.
STORED_SCOPE=$(echo "$BODY" | jq -r '.variables.VITE_API_SCOPE.value')
STORED_SPA=$(echo "$BODY" | jq -r '.variables.VITE_SPA_CLIENT_ID.value')
if [ "$STORED_SCOPE" != "$VITE_API_SCOPE" ] || [ "$STORED_SPA" != "$VITE_SPA_CLIENT_ID" ]; then
  echo "##[error]Variable group read-back mismatch: stored scope='$STORED_SCOPE' spa='$STORED_SPA'."
  exit 1
fi

echo "Variable group '${GROUP_NAME}' updated with deployment outputs."

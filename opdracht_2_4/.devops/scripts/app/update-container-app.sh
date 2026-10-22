#!/bin/bash
# Update the Container App to the freshly built image tag. Used on app-only
# reruns where the Infra stage is skipped but a new image was pushed.

set -euo pipefail

CONTAINER_APP_NAME="${1:?Container App name is required}"
RESOURCE_GROUP="${2:?Resource group is required}"
ACR_LOGIN_SERVER="${3:?ACR login server is required}"
BUILD_ID="${4:?Build ID is required}"
IMAGE_NAME="${5:-cop-api}"

az containerapp update \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:$BUILD_ID"

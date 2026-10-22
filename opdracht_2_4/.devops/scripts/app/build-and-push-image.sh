#!/bin/bash
# Build and push the API container image to the shared Azure Container Registry.
# Runs on a self-hosted agent inside the hub VNet so traffic to the private ACR
# endpoint resolves via the hub DNS resolver (no public access needed).

set -euo pipefail

ACR_LOGIN_SERVER="${1:?ACR login server is required}"
BUILD_ID="${2:?Build ID is required}"
DOCKERFILE_PATH="${3:-api/Dockerfile}"
CONTEXT_PATH="${4:-api}"
IMAGE_NAME="${5:-cop-api}"

ACR_NAME="${ACR_LOGIN_SERVER%.azurecr.io}"

az acr login --name "$ACR_NAME"

docker build \
  -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$BUILD_ID" \
  -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" \
  -f "$DOCKERFILE_PATH" \
  "$CONTEXT_PATH"

docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$BUILD_ID"
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"

#!/bin/bash
# Preview Bicep deployment changes (what-if) without deploying.

set -euo pipefail

LOCATION="${1:?Location is required (e.g., westeurope)}"
ENVIRONMENT="${2:?Environment is required (e.g., dev or prod)}"

# Match the image reference used by the actual deployment so the preview is
# accurate; fall back to the Bicep placeholder default when unset.
IMAGE_PARAMS=()
if [[ -n "${CONTAINER_IMAGE:-}" ]]; then
  IMAGE_PARAMS+=("containerImage=$CONTAINER_IMAGE")
fi

az deployment sub what-if \
  --location "$LOCATION" \
  --template-file "infra/main.bicep" \
  --parameters "infra/environments/$ENVIRONMENT/main.bicepparam" \
  --parameters ${IMAGE_PARAMS[@]+"${IMAGE_PARAMS[@]}"}

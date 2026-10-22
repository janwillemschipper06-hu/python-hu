#!/bin/bash
# Validate the Bicep template with the environment parameter file.
# Role assignments are skipped here (deployRoleAssignments=false) because the
# validation principal may lack Microsoft.Authorization/roleAssignments/write;
# the real deploy creates them.

set -euo pipefail

LOCATION="${1:?Location is required (e.g., westeurope)}"
ENVIRONMENT="${2:?Environment is required (e.g., dev or prod)}"

az deployment sub validate \
  --location "$LOCATION" \
  --template-file "infra/main.bicep" \
  --parameters "infra/environments/$ENVIRONMENT/main.bicepparam" \
  --parameters deployRoleAssignments=false

#!/bin/bash
# Detect changed folders in the repository.
# Determines which components changed (infra, database, api, frontend) so the
# pipeline can run only the relevant stages. Manual runs bypass this and run
# every stage.

set -euo pipefail

# For PRs, diff against the target branch; for CI, diff against the previous commit.
if [ -n "${SYSTEM_PULLREQUEST_TARGETBRANCH:-}" ]; then
  BASE="origin/$SYSTEM_PULLREQUEST_TARGETBRANCH"
else
  BASE="HEAD~1"
fi

echo "Comparing against: $BASE"

CHANGED=$(git diff --name-only "$BASE" HEAD 2>/dev/null || echo "")
echo "Changed files:"
echo "$CHANGED"

INFRA=false
DATABASE=false
API=false
FRONTEND=false

if echo "$CHANGED" | grep -q "^infra/"; then
  INFRA=true
fi
if echo "$CHANGED" | grep -q "^database/"; then
  DATABASE=true
fi
if echo "$CHANGED" | grep -q "^api/"; then
  API=true
fi
if echo "$CHANGED" | grep -q "^frontend/"; then
  FRONTEND=true
fi

echo "Infra changed: $INFRA"
echo "Database changed: $DATABASE"
echo "API changed: $API"
echo "Frontend changed: $FRONTEND"

# Output for Azure DevOps pipeline.
echo "##vso[task.setvariable variable=infraChanged;isOutput=true]$INFRA"
echo "##vso[task.setvariable variable=databaseChanged;isOutput=true]$DATABASE"
echo "##vso[task.setvariable variable=apiChanged;isOutput=true]$API"
echo "##vso[task.setvariable variable=frontendChanged;isOutput=true]$FRONTEND"

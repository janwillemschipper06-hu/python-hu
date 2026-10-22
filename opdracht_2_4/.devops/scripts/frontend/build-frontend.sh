#!/bin/bash
# Build the frontend (Vite): install dependencies and produce the static bundle
# in <dir>/dist for the Static Web App deploy.

set -euo pipefail

FRONTEND_DIR="${1:-.}"

cd "$FRONTEND_DIR"

echo "Installing dependencies..."
npm ci

echo "Building Vite app..."
npm run build

echo "Frontend build complete. Output in $FRONTEND_DIR/dist"

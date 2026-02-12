#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_CMD="docker compose"
if command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
fi

if [ ! -f ".env" ]; then
  echo ".env not found. Copy .env.example to .env first." >&2
  exit 1
fi

PROJECT_NAME="$(grep -E '^COMPOSE_PROJECT_NAME=' .env | cut -d= -f2- || true)"
PROJECT_NAME="${PROJECT_NAME:-costmatrix}"

echo "Stopping stack '${PROJECT_NAME}'..."
${COMPOSE_CMD} -p "${PROJECT_NAME}" -f docker-compose.yml down

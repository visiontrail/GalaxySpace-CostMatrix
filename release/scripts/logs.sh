#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_CMD="docker compose"
if command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
fi

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-costmatrix}"
if [ -f ".env" ]; then
  PROJECT_NAME="$(grep -E '^COMPOSE_PROJECT_NAME=' .env | cut -d= -f2- || true)"
fi

SERVICE="${1:-}"

echo "Streaming logs for project '${PROJECT_NAME}'${SERVICE:+ service '${SERVICE}'}..."
if [ -n "${SERVICE}" ]; then
  ${COMPOSE_CMD} -p "${PROJECT_NAME}" -f docker-compose.yml logs -f "${SERVICE}"
else
  ${COMPOSE_CMD} -p "${PROJECT_NAME}" -f docker-compose.yml logs -f
fi

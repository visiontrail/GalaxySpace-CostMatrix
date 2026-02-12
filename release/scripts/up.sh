#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_CMD="docker compose"
if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
  echo "Docker Compose is required but not found." >&2
  exit 1
fi
if ! command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi

if [ ! -f ".env" ]; then
  echo ".env not found. Copy .env.example to .env and adjust values, then re-run." >&2
  exit 1
fi

# Ensure persistent dirs exist
mkdir -p data/uploads data/data data/logs config

# Load images (offline-friendly)
"${ROOT_DIR}/scripts/load-images.sh"

PROJECT_NAME="$(grep -E '^COMPOSE_PROJECT_NAME=' .env | cut -d= -f2- || true)"
PROJECT_NAME="${PROJECT_NAME:-costmatrix}"

echo "Bringing up stack with project name '${PROJECT_NAME}'..."
${COMPOSE_CMD} -p "${PROJECT_NAME}" -f docker-compose.yml up -d

echo "Current status:"
${COMPOSE_CMD} -p "${PROJECT_NAME}" -f docker-compose.yml ps

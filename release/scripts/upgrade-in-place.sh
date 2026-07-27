#!/usr/bin/env bash
set -euo pipefail

NEW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-}"

usage() {
  echo "Usage: $0 <existing-deployment-directory>" >&2
  echo "Example: $0 /opt/costmatrix" >&2
}

read_env_value() {
  local file="$1"
  local key="$2"
  awk -F= -v key="${key}" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${file}"
}

if [ -z "${TARGET_DIR}" ]; then
  usage
  exit 1
fi

TARGET_DIR="$(cd "${TARGET_DIR}" && pwd)"

if [ "${TARGET_DIR}" = "${NEW_ROOT}" ]; then
  echo "The new release directory and existing deployment directory must differ." >&2
  exit 1
fi

for required in \
  "${NEW_ROOT}/docker-compose.yml" \
  "${NEW_ROOT}/.env.example" \
  "${NEW_ROOT}/images" \
  "${TARGET_DIR}/docker-compose.yml" \
  "${TARGET_DIR}/.env" \
  "${TARGET_DIR}/data" \
  "${TARGET_DIR}/config"; do
  if [ ! -e "${required}" ]; then
    echo "Required upgrade path is missing: ${required}" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker is required and the daemon must be running." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required." >&2
  exit 1
fi

NEW_TAG="$(read_env_value "${NEW_ROOT}/.env.example" IMAGE_TAG)"
NEW_BACKEND_IMAGE="$(read_env_value "${NEW_ROOT}/.env.example" BACKEND_IMAGE)"
NEW_FRONTEND_IMAGE="$(read_env_value "${NEW_ROOT}/.env.example" FRONTEND_IMAGE)"

if [ -z "${NEW_TAG}" ] || [ -z "${NEW_BACKEND_IMAGE}" ] || [ -z "${NEW_FRONTEND_IMAGE}" ]; then
  echo "The new release .env.example does not contain complete image settings." >&2
  exit 1
fi

BACKUP_DIR="${TARGET_DIR}/.upgrade-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"
cp "${TARGET_DIR}/.env" "${BACKUP_DIR}/.env"
cp "${TARGET_DIR}/docker-compose.yml" "${BACKUP_DIR}/docker-compose.yml"
cp -R "${TARGET_DIR}/scripts" "${BACKUP_DIR}/scripts"

echo "Loading images for ${NEW_TAG}..."
for tarball in "${NEW_ROOT}/images/"*.tar; do
  [ -e "${tarball}" ] || continue
  docker load -i "${tarball}"
done

echo "Updating deployment files in ${TARGET_DIR}; preserving .env secrets, config/, and data/..."
cp "${NEW_ROOT}/docker-compose.yml" "${TARGET_DIR}/docker-compose.yml"
cp -R "${NEW_ROOT}/scripts/." "${TARGET_DIR}/scripts/"

UPDATED_ENV="${BACKUP_DIR}/.env.updated"
awk \
  -v image_tag="${NEW_TAG}" \
  -v backend_image="${NEW_BACKEND_IMAGE}" \
  -v frontend_image="${NEW_FRONTEND_IMAGE}" \
  '
  /^IMAGE_TAG=/ { print "IMAGE_TAG=" image_tag; next }
  /^BACKEND_IMAGE=/ { print "BACKEND_IMAGE=" backend_image; next }
  /^FRONTEND_IMAGE=/ { print "FRONTEND_IMAGE=" frontend_image; next }
  { print }
  ' "${TARGET_DIR}/.env" > "${UPDATED_ENV}"
cp "${UPDATED_ENV}" "${TARGET_DIR}/.env"

PROJECT_NAME="$(read_env_value "${TARGET_DIR}/.env" COMPOSE_PROJECT_NAME)"
PROJECT_NAME="${PROJECT_NAME:-costmatrix}"

rollback() {
  echo "Upgrade failed; restoring the previous compose and image settings..." >&2
  cp "${BACKUP_DIR}/.env" "${TARGET_DIR}/.env"
  cp "${BACKUP_DIR}/docker-compose.yml" "${TARGET_DIR}/docker-compose.yml"
  (
    cd "${TARGET_DIR}"
    "${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml up -d
  ) || true
}

cd "${TARGET_DIR}"
"${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml config >/dev/null

if ! "${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml up -d; then
  rollback
  exit 1
fi

healthy=0
for _ in $(seq 1 60); do
  backend_id="$("${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml ps -q backend)"
  frontend_id="$("${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml ps -q frontend)"

  if [ -n "${backend_id}" ] && [ -n "${frontend_id}" ]; then
    backend_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${backend_id}")"
    frontend_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${frontend_id}")"
    if [ "${backend_health}" = "healthy" ] && [ "${frontend_health}" = "healthy" ]; then
      healthy=1
      break
    fi
  fi
  sleep 2
done

if [ "${healthy}" != "1" ]; then
  "${COMPOSE[@]}" -p "${PROJECT_NAME}" -f docker-compose.yml ps >&2 || true
  rollback
  exit 1
fi

echo "Upgrade to ${NEW_TAG} completed successfully."
echo "Rollback metadata: ${BACKUP_DIR}"

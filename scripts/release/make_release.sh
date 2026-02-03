#!/usr/bin/env bash
set -euo pipefail

# Build production images, package them (offline-ready), and assemble a deployable bundle.
# Usage:
#   VERSION=20260129 ./scripts/release/make_release.sh
#   REGISTRY=registry.local/ ./scripts/release/make_release.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v docker &>/dev/null; then
  echo "Docker is required." >&2
  exit 1
fi

VERSION="${VERSION:-$(date +%Y%m%d)-$(git rev-parse --short HEAD 2>/dev/null || echo local)}"
REGISTRY="${REGISTRY:-}"
BACKEND_IMAGE="${REGISTRY}costmatrix-backend"
FRONTEND_IMAGE="${REGISTRY}costmatrix-frontend"

OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT_DIR}/release/packages}"
PKG_NAME="costmatrix-${VERSION}"
PKG_DIR="${OUTPUT_ROOT}/${PKG_NAME}"
IMG_DIR="${PKG_DIR}/images"
CONFIG_DIR="${PKG_DIR}/config"
SCRIPT_DST="${PKG_DIR}/scripts"

echo "Building release version: ${VERSION}"
rm -rf "${PKG_DIR}"
mkdir -p "${IMG_DIR}" "${CONFIG_DIR}" "${SCRIPT_DST}"

echo "1) Build backend image (${BACKEND_IMAGE}:${VERSION})"
docker build -f backend/Dockerfile.prod -t "${BACKEND_IMAGE}:${VERSION}" .

echo "2) Build frontend image (${FRONTEND_IMAGE}:${VERSION})"
docker build -f frontend/Dockerfile -t "${FRONTEND_IMAGE}:${VERSION}" frontend

echo "3) Save images for offline install"
docker save "${BACKEND_IMAGE}:${VERSION}" -o "${IMG_DIR}/backend-${VERSION}.tar"
docker save "${FRONTEND_IMAGE}:${VERSION}" -o "${IMG_DIR}/frontend-${VERSION}.tar"

echo "4) Assemble release bundle at ${PKG_DIR}"
cp release/docker-compose.release.yml "${PKG_DIR}/docker-compose.yml"
cp release/DEPLOY.md "${PKG_DIR}/DEPLOY.md"
cp -r release/scripts/* "${SCRIPT_DST}/"

# Provide ready-to-use env files with the built image tag baked in
cat > "${PKG_DIR}/.env" <<EOF
COMPOSE_PROJECT_NAME=costmatrix
IMAGE_TAG=${VERSION}
BACKEND_IMAGE=${BACKEND_IMAGE}
FRONTEND_IMAGE=${FRONTEND_IMAGE}
BACKEND_PORT=8000
FRONTEND_PORT=8180
APP_NAME=CostMatrix
APP_VERSION=1.0.0
DEBUG=false
ALLOWED_ORIGINS=http://localhost:8180
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEFAULT_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD_FILE=/app/config/initial_admin_password.txt
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=200
EOF

cat > "${PKG_DIR}/.env.example" <<EOF
COMPOSE_PROJECT_NAME=costmatrix
IMAGE_TAG=${VERSION}
BACKEND_IMAGE=${BACKEND_IMAGE}
FRONTEND_IMAGE=${FRONTEND_IMAGE}
BACKEND_PORT=8000
FRONTEND_PORT=8180
APP_NAME=CostMatrix
APP_VERSION=1.0.0
DEBUG=false
ALLOWED_ORIGINS=http://localhost:8180
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEFAULT_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD_FILE=/app/config/initial_admin_password.txt
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=200
EOF

# Bundle default config (can be overridden by IT)
cp -r config/. "${CONFIG_DIR}/"

echo "5) Create data placeholders"
mkdir -p "${PKG_DIR}/data/uploads" "${PKG_DIR}/data/data" "${PKG_DIR}/data/logs"

echo "Release package ready: ${PKG_DIR}"
echo "To ship: tar -czf ${PKG_NAME}.tar.gz -C ${OUTPUT_ROOT} ${PKG_NAME}"

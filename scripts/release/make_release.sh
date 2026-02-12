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
SKIP_SMOKE_TEST="${SKIP_SMOKE_TEST:-0}"

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

if [ "${SKIP_SMOKE_TEST}" != "1" ]; then
  echo "3) Run backend smoke tests"
  docker run --rm "${BACKEND_IMAGE}:${VERSION}" python -c "import app.main;print('ok')"
  docker run --rm \
    -e ALLOWED_ORIGINS='http://localhost:8180,http://localhost:5173' \
    "${BACKEND_IMAGE}:${VERSION}" \
    python -c "import app.main;print('ok-csv')"
  docker run --rm \
    -e ALLOWED_ORIGINS='["http://localhost:8180","http://localhost:5173"]' \
    "${BACKEND_IMAGE}:${VERSION}" \
    python -c "import app.main;print('ok-json')"
  docker run --rm \
    -e DB_TYPE='mysql' \
    -e DB_HOST='127.0.0.1' \
    -e DB_PORT='3306' \
    -e DB_NAME='costmatrix' \
    -e DB_USER='root' \
    -e DB_PASSWORD='change_me' \
    -e DB_CHARSET='utf8mb4' \
    "${BACKEND_IMAGE}:${VERSION}" \
    python -c "from app.db.database import DB_BACKEND;assert DB_BACKEND=='mysql';print('ok-mysql-config')"

  echo "3.1) Run backend runtime smoke test (multi-worker startup)"
  SMOKE_CONTAINER="costmatrix-backend-smoke-${VERSION//[^a-zA-Z0-9_.-]/-}"
  docker rm -f "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${SMOKE_CONTAINER}" \
    -e ALLOWED_ORIGINS='http://localhost:8180,http://localhost:5173' \
    "${BACKEND_IMAGE}:${VERSION}" >/dev/null

  READY=0
  for _ in $(seq 1 40); do
    if docker exec "${SMOKE_CONTAINER}" python -c "import urllib.request,sys;sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/').status==200 else sys.exit(1)" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 1
  done

  if [ "${READY}" != "1" ]; then
    echo "Backend runtime smoke test failed: service did not become healthy." >&2
    docker logs "${SMOKE_CONTAINER}" || true
    docker rm -f "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
    exit 1
  fi

  if docker logs "${SMOKE_CONTAINER}" 2>&1 | grep -q "Application startup failed"; then
    echo "Backend runtime smoke test failed: startup errors detected in logs." >&2
    docker logs "${SMOKE_CONTAINER}" || true
    docker rm -f "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
    exit 1
  fi

  docker rm -f "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
else
  echo "3) Skip backend smoke tests (SKIP_SMOKE_TEST=1)"
fi

echo "4) Save images for offline install"
docker save -o "${IMG_DIR}/costmatrix-backend-${VERSION}.tar" "${BACKEND_IMAGE}:${VERSION}"
docker save -o "${IMG_DIR}/costmatrix-frontend-${VERSION}.tar" "${FRONTEND_IMAGE}:${VERSION}"

echo "5) Assemble release bundle at ${PKG_DIR}"
cp release/docker-compose.release.yml "${PKG_DIR}/docker-compose.yml"
cp release/DEPLOY.md "${PKG_DIR}/DEPLOY.md"
cp -r release/scripts/* "${SCRIPT_DST}/"
chmod +x "${SCRIPT_DST}/"*.sh

# Generate .env.example from release template with current tag/image names.
awk \
  -v image_tag="${VERSION}" \
  -v backend_image="${BACKEND_IMAGE}" \
  -v frontend_image="${FRONTEND_IMAGE}" \
  '
  /^IMAGE_TAG=/ { print "IMAGE_TAG=" image_tag; next }
  /^BACKEND_IMAGE=/ { print "BACKEND_IMAGE=" backend_image; next }
  /^FRONTEND_IMAGE=/ { print "FRONTEND_IMAGE=" frontend_image; next }
  { print }
  ' release/.env.release.example > "${PKG_DIR}/.env.example"

# Bundle default config (can be overridden by IT)
cp -r config/. "${CONFIG_DIR}/"

echo "6) Create data placeholders"
mkdir -p "${PKG_DIR}/data/uploads" "${PKG_DIR}/data/data" "${PKG_DIR}/data/logs"

echo "7) Create compressed archive"
TARBALL="${OUTPUT_ROOT}/${PKG_NAME}.tar.gz"
rm -f "${TARBALL}"
tar -czf "${TARBALL}" -C "${OUTPUT_ROOT}" "${PKG_NAME}"

echo ""
echo "Release package ready:"
echo "  Directory: ${PKG_DIR}"
echo "  Archive:   ${TARBALL}"
echo ""
echo "Target host deployment:"
echo "  cd ${PKG_NAME}"
echo "  cp .env.example .env"
echo "  ./scripts/up.sh"

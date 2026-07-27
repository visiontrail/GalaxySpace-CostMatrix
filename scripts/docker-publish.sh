#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

usage() {
  cat <<'USAGE'
用法:
  scripts/docker-publish.sh <dockerhub_namespace> [tag]

示例:
  scripts/docker-publish.sh galaxyspaceai v1.0.0
  IMAGE_TAG=2026.07.27 scripts/docker-publish.sh galaxyspaceai

发布镜像:
  <namespace>/costmatrix-backend:<tag>
  <namespace>/costmatrix-frontend:<tag>
  同时推送 latest 标签，除非设置 PUSH_LATEST=false。
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

require_docker

NAMESPACE="${DOCKERHUB_NAMESPACE:-${1:-}}"
TAG="${IMAGE_TAG:-${2:-latest}}"
PUSH_LATEST="${PUSH_LATEST:-true}"

if [ -z "${NAMESPACE}" ]; then
  usage
  echo
  echo "缺少 DockerHub namespace，例如 galaxyspaceai。" >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

echo "构建 ${NAMESPACE}/costmatrix-backend:${TAG} ..."
docker build \
  -f backend/Dockerfile.prod \
  -t "${NAMESPACE}/costmatrix-backend:${TAG}" \
  .

echo "构建 ${NAMESPACE}/costmatrix-frontend:${TAG} ..."
docker build \
  -f frontend/Dockerfile \
  -t "${NAMESPACE}/costmatrix-frontend:${TAG}" \
  frontend

if [ "${PUSH_LATEST}" = "true" ]; then
  docker tag \
    "${NAMESPACE}/costmatrix-backend:${TAG}" \
    "${NAMESPACE}/costmatrix-backend:latest"
  docker tag \
    "${NAMESPACE}/costmatrix-frontend:${TAG}" \
    "${NAMESPACE}/costmatrix-frontend:latest"
fi

docker push "${NAMESPACE}/costmatrix-backend:${TAG}"
docker push "${NAMESPACE}/costmatrix-frontend:${TAG}"

if [ "${PUSH_LATEST}" = "true" ]; then
  docker push "${NAMESPACE}/costmatrix-backend:latest"
  docker push "${NAMESPACE}/costmatrix-frontend:latest"
fi

echo "DockerHub 发布完成。"

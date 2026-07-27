#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "未找到 Docker Compose。请安装 Docker Desktop 或 docker compose 插件。" >&2
  exit 1
fi

compose() {
  "${COMPOSE[@]}" -f "${COMPOSE_FILE}" "$@"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 Docker。请先安装 Docker Desktop 或 Docker Engine。" >&2
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon 未运行，请先启动 Docker。" >&2
    exit 1
  fi
}

ensure_env_file() {
  if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    echo "已从 .env.example 创建本地 .env。"
  fi
}

ensure_data_dirs() {
  mkdir -p \
    "${PROJECT_ROOT}/data/uploads" \
    "${PROJECT_ROOT}/data/data" \
    "${PROJECT_ROOT}/data/logs"
}

print_endpoints() {
  local frontend_port="${FRONTEND_PORT:-8180}"
  local backend_port="${BACKEND_PORT:-8000}"
  echo
  echo "访问入口："
  echo "  前端: http://localhost:${frontend_port}"
  echo "  后端健康检查: http://localhost:${backend_port}/api/health"
  echo "  API 文档: http://localhost:${frontend_port}/docs"
}

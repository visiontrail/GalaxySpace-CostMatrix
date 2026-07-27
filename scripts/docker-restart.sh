#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_docker
ensure_env_file
ensure_data_dirs
cd "${PROJECT_ROOT}"

echo "重新构建并更新 CostMatrix 本地容器..."
compose up -d --build --wait

echo
compose ps
print_endpoints

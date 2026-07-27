#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_docker
cd "${PROJECT_ROOT}"

compose down
echo "CostMatrix 已停止；宿主机 data/ 目录保持不变。"

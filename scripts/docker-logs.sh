#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_docker
cd "${PROJECT_ROOT}"

if [ "$#" -gt 0 ]; then
  compose logs -f "$@"
else
  compose logs -f
fi

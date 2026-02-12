#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG_DIR="${ROOT_DIR}/images"

if ! command -v docker &>/dev/null; then
  echo "Docker is required but not found." >&2
  exit 1
fi

if [ ! -d "${IMG_DIR}" ] || [ -z "$(ls -A "${IMG_DIR}" 2>/dev/null)" ]; then
  echo "No images found in ${IMG_DIR}. Ensure the release package is complete." >&2
  exit 1
fi

echo "Loading Docker images from ${IMG_DIR}..."
for tarball in "${IMG_DIR}"/*.tar; do
  [ -e "${tarball}" ] || continue
  echo "  -> ${tarball}"
  docker load -i "${tarball}"
done

echo "Images loaded."

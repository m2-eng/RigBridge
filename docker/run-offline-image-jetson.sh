#!/usr/bin/env bash
# Zweck: RigBridge-Image aus einem TAR-Archiv laden und auf Jetson/Linux starten.



set -euo pipefail

if [[ $# -lt 1 || $# -gt 6 ]]; then
  echo "Usage: $0 <tar-path> [image-name] [tag] [container-name] [host-port] [bind-address]"
  echo "Example: $0 ./docker/offline/rigbridge-local-test.tar rigbridge local-test rigbridge 8080 127.0.0.1"
  exit 1
fi

TAR_PATH="$1"
IMAGE_NAME="${2:-rigbridge}"
TAG="${3:-local-test}"
CONTAINER_NAME="${4:-rigbridge}"
HOST_PORT="${5:-8080}"
BIND_ADDRESS="${6:-127.0.0.1}"
FULL_IMAGE_TAG="${IMAGE_NAME}:${TAG}"

if [[ ! -f "$TAR_PATH" ]]; then
  echo "Tar file not found: $TAR_PATH" >&2
  exit 1
fi

CONFIG_SOURCE="$PWD/config.json"
THEME_SOURCE="$PWD/theme.css"

if [[ ! -f "$CONFIG_SOURCE" ]]; then
  echo "Missing config.json in current directory: $CONFIG_SOURCE" >&2
  exit 1
fi

if [[ ! -f "$THEME_SOURCE" ]]; then
  echo "Missing theme.css in current directory: $THEME_SOURCE" >&2
  exit 1
fi

echo "Loading Docker image from ${TAR_PATH}..."
docker load -i "$TAR_PATH"

echo "Stopping and removing existing container ${CONTAINER_NAME} (if present)..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker compose down 2>/dev/null || true

echo "Starting container ${CONTAINER_NAME} from ${FULL_IMAGE_TAG} on ${BIND_ADDRESS}:${HOST_PORT}..."
export RIGBRIDGE_IMAGE="${FULL_IMAGE_TAG}"
export API_PORT="${HOST_PORT}"
export BIND_ADDRESS="${BIND_ADDRESS}"

docker compose up -d

echo "Container is running. Open: http://${BIND_ADDRESS}:${HOST_PORT}"

#!/bin/bash
# build-local-image.sh - Build and export Docker image for Jetson/ARM64

# Default parameter values
IMAGE_NAME="${1:-rigbridge}"
TAG="${2:-local-test}"
TAR_PATH="${3}"

# Exit on error
set -e

FULL_IMAGE_TAG="${IMAGE_NAME}:${TAG}"

# Generate default tar path if not provided
if [ -z "$TAR_PATH" ]; then
    SAFE_TAG=$(echo "$TAG" | tr -cs '[:alnum:]._-' '-')
    TAR_PATH="docker/offline/${IMAGE_NAME}-${SAFE_TAG}.tar"
fi

# Create tar directory if it doesn't exist
TAR_DIR=$(dirname "$TAR_PATH")
if [ -n "$TAR_DIR" ] && [ ! -d "$TAR_DIR" ]; then
    mkdir -p "$TAR_DIR"
fi

echo "Building Docker image ${FULL_IMAGE_TAG} (target: runtime) for ARM64..."
docker build --no-cache --target runtime --platform linux/arm64 -t "$FULL_IMAGE_TAG" .

echo "Exporting image ${FULL_IMAGE_TAG} to ${TAR_PATH}..."
docker save -o "$TAR_PATH" "$FULL_IMAGE_TAG"

if [[ -f "/etc/nv_tegra_release" || -d "/proc/device-tree/nvidia,dtsfilename" ]]; then
    echo "Jetson-System erkannt. Lade Image..."
    docker load -i ./docker/cnt/rigbridge-local-test.tar
fi

echo "Done. Offline image package created: ${TAR_PATH}"
echo "Load on target machine with: docker load -i ${TAR_PATH}"

#!/bin/bash
# This script runs the Kafka (Gradle) build inside our pre-built Docker container.
set -euo pipefail

echo "=== Starting Kafka Build in Docker for ${COMMIT_SHA:0:7} ==="

# We create a persistent gradle cache volume to speed up builds
# This is the same strategy as your elasticsearch project
docker volume create --name=gradle-cache || true

# The build command to run inside the container
# We build, but skip tests (-x test) to just check compilation
# --- FIX: Removed 'generateSources' ---
BUILD_COMMAND="git checkout -f ${COMMIT_SHA} && ./gradlew build -x test"

# Run the build in a container
if docker run --rm --dns=8.8.8.8 \
    -v "${PROJECT_DIR}:/repo" \
    -v "gradle-cache:/root/.gradle" \
    -w /repo \
    "${BUILDER_IMAGE_TAG}" \
    bash -c "${BUILD_COMMAND}"
then
    echo "Success" > "${BUILD_STATUS_FILE}"
else
    echo "Fail" > "${BUILD_STATUS_FILE}"
fi

echo "=== Build finished for ${COMMIT_SHA:0:7} ==="
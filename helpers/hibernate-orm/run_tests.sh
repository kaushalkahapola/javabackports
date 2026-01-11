#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

IMAGE_TAG="${IMAGE_TAG_TO_BUILD:-hibernate-orm-${COMMIT_SHA:0:7}}"

if [ "${TEST_TARGETS}" == "ALL" ]; then
    GRADLE_CMD="./gradlew test --rerun-tasks"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    GRADLE_CMD="./gradlew ${TEST_TARGETS} --rerun-tasks"
fi

DOCKER_CMD="docker"
${DOCKER_CMD} volume create gradle-cache-hibernate 2>/dev/null || true
${DOCKER_CMD} volume create gradle-wrapper-hibernate 2>/dev/null || true

echo "--- Executing: ${GRADLE_CMD} ---"

if ${DOCKER_CMD} run --rm \
    -v "${PROJECT_DIR}:/repo" \
    -v "gradle-cache-hibernate:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-hibernate:/home/gradle/.gradle/wrapper" \
    -w /repo \
    "${IMAGE_TAG}" \
    bash -c "set -e; \
    git config --global --add safe.directory /repo; \
    ${GRADLE_CMD} -i; \
    RET=\$?; \
    echo \"--- Debug: finding build directories ---\"; \
    find /repo -type d -name \"build\" -maxdepth 3; \
    echo \"--- Debug: Listing all XML files ---\"; \
    find /repo -name \"*.xml\"; \
    exit \$RET"; then
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi

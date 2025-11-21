#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target Tasks: ${TEST_TARGETS}"

# 1. Configure Test Command
if [ "${TEST_TARGETS}" == "ALL" ]; then
    # Run all tests. NOTE: This is very heavy for Kafka.
    # You might want to restrict this to core modules if it's too slow.
    GRADLE_CMD="./gradlew test"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    # Run specific targets
    GRADLE_CMD="./gradlew ${TEST_TARGETS}"
fi

echo "--- Starting Test Execution ---"
echo "--- Command: ${GRADLE_CMD} ---"

# 2. Run Tests
# We use the same 'gradle-cache' volume from the build step
docker volume create gradle-cache 2>/dev/null || true

# We reuse the builder image
if docker run --rm \
    -v "${PROJECT_DIR}:/repo" \
    -v "gradle-cache:/root/.gradle" \
    -w /repo \
    "${BUILDER_IMAGE_TAG}" \
    bash -c "git checkout -f ${COMMIT_SHA} && ${GRADLE_CMD}"; then
    
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi
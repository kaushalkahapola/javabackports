#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

# 1. Reconstruct the Docker Image Tag
# Elasticsearch builds its own image per commit.
# The tag format in main.py is: {repo_name}-{build_type}-{short_sha}
# We passed BUILD_TYPE ("fixed" or "buggy") in the env vars.

IMAGE_TAG="elasticsearch-${BUILD_TYPE}-${COMMIT_SHA:0:7}"

echo "--- Using Docker Image: ${IMAGE_TAG} ---"

# 2. Configure Test Command
if [ "${TEST_TARGETS}" == "ALL" ]; then
    GRADLE_CMD="./gradlew test"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    GRADLE_CMD="./gradlew ${TEST_TARGETS}"
fi

# 3. Run Tests in Docker
# We reuse the gradle-cache volume we created during the build
docker volume create --name=gradle-cache || true

echo "--- Executing: ${GRADLE_CMD} ---"

# Note: The Dockerfile for ES already sets WORKDIR /repo and user 'gradle'
# FIX: Explicitly set the user to 'gradle' to prevent the "can not run elasticsearch as root" error.
if docker run --rm \
    --user gradle \
    -v "gradle-cache:/home/gradle/.gradle" \
    "${IMAGE_TAG}" \
    bash -c "${GRADLE_CMD}"; then
    
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi

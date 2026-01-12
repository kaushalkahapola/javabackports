#!/bin/bash
# run_tests.sh for grpc-java
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

IMAGE_TAG="${IMAGE_TAG:-grpc-java-${BUILD_TYPE}-${COMMIT_SHA:0:7}}"

docker volume create gradle-cache-grpc-java 2>/dev/null || true
docker volume create gradle-wrapper-grpc-java 2>/dev/null || true

if [ "${TEST_TARGETS}" == "ALL" ]; then
    GRADLE_CMD="./gradlew test -PskipAndroid=true -PskipCodegen=true"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    GRADLE_CMD="./gradlew ${TEST_TARGETS} -PskipAndroid=true -PskipCodegen=true"
fi

echo "--- Executing: ${GRADLE_CMD} ---"

if docker run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "gradle-cache-grpc-java:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-grpc-java:/home/gradle/.gradle/wrapper" \
    -v "${PROJECT_DIR}:/repo" \
    -w /repo \
    "${IMAGE_TAG}" \
    ${GRADLE_CMD}; then
    echo "Success" > "$TEST_STATUS_FILE"
else
    echo "Fail" > "$TEST_STATUS_FILE"
fi


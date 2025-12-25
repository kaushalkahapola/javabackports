#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

# 1. Reconstruct the Docker Image Tag
IMAGE_TAG="${IMAGE_TAG:-hive-${BUILD_TYPE}-${COMMIT_SHA:0:7}}"

echo "--- Using Docker Image: ${IMAGE_TAG} ---"

# 2. Configure Test Command
if [ "${TEST_TARGETS}" == "ALL" ]; then
    MVN_CMD="mvn test -B -DfailIfNoTests=false"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    # Replace spaces with commas for Maven
    CLEAN_TARGETS=$(echo "${TEST_TARGETS}" | tr ' ' ',')
    # Use -Dtest for specific tests.
    MVN_CMD="mvn test -Dtest=${CLEAN_TARGETS} -B -DfailIfNoTests=false"
fi

# Determine if we need sudo for docker
DOCKER_CMD="docker"
if ! docker info > /dev/null 2>&1; then
    if sudo docker info > /dev/null 2>&1; then
        echo "Docker requires sudo. Using 'sudo docker'."
        DOCKER_CMD="sudo docker"
    else
        echo "Warning: Docker command failed and sudo check failed. Continuing with 'docker' but expect errors."
    fi
fi

# 3. Run Tests in Docker
# Create persistent Maven cache volume if it doesn't exist
${DOCKER_CMD} volume create maven-cache-hive 2>/dev/null || true

echo "--- Executing: ${MVN_CMD} ---"

# Note: The Dockerfile for Hive already sets WORKDIR /repo and user 'maven'
if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "maven-cache-hive:/home/maven/.m2" \
    -v "${BUILD_DIR}:/repo/build_outputs" \
    "${IMAGE_TAG}" \
    bash -c "${MVN_CMD}; \
    MVN_EXIT_CODE=\$?; \
    mkdir -p /repo/build_outputs/target/surefire-reports; \
    find . -name 'TEST-*.xml' -not -path '*/build_outputs/*' -exec cp {} /repo/build_outputs/target/surefire-reports/ \;; \
    exit \$MVN_EXIT_CODE"; then
    
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi

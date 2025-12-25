#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

# 1. Reconstruct the Docker Image Tag
IMAGE_TAG="${IMAGE_TAG:-flow-${BUILD_TYPE}-${COMMIT_SHA:0:7}}"

echo "--- Using Docker Image: ${IMAGE_TAG} ---"

# 2. Configure Test Command
# Check for modules to exclude dynamically
EXCLUSION_FLAGS=""
MODULES_TO_CHECK="flow-test-npm-bytecode-scanning-production flow-test-npm-bytecode-scanning-fallback-production flow-test-root-context-npm"

if [ -d "${PROJECT_DIR}" ]; then
    pushd "${PROJECT_DIR}" > /dev/null
    for mod in $MODULES_TO_CHECK; do
        # Check if pom.xml containing this artifactId exists
        if grep -r -q "<artifactId>${mod}</artifactId>" . 2>/dev/null; then
            if [ -z "$EXCLUSION_FLAGS" ]; then
                EXCLUSION_FLAGS="-pl '!com.vaadin:${mod}"
            else
                EXCLUSION_FLAGS="${EXCLUSION_FLAGS},!com.vaadin:${mod}"
            fi
        fi
    done
    popd > /dev/null
fi

# Close the single quote if exclusion flags were added
if [ ! -z "$EXCLUSION_FLAGS" ]; then
    EXCLUSION_FLAGS="${EXCLUSION_FLAGS}'"
fi

if [ "${TEST_TARGETS}" == "ALL" ]; then
    MVN_CMD="mvn test -B -DfailIfNoTests=false ${EXCLUSION_FLAGS}"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    # Replace spaces with commas for Maven
    CLEAN_TARGETS=$(echo "${TEST_TARGETS}" | tr ' ' ',')
    MVN_CMD="mvn test -Dtest=${CLEAN_TARGETS} -B -DfailIfNoTests=false ${EXCLUSION_FLAGS}"
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
${DOCKER_CMD} volume create maven-cache-flow 2>/dev/null || true

echo "--- Executing: ${MVN_CMD} ---"

# Note: The Dockerfile for Flow already sets WORKDIR /repo and user 'maven'
if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "maven-cache-flow:/home/maven/.m2" \
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

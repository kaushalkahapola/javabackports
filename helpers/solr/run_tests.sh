#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

IMAGE_TAG="${IMAGE_TAG:-solr-${BUILD_TYPE}-${COMMIT_SHA:0:7}}"

echo "--- Using Docker Image: ${IMAGE_TAG} ---"

# Configure Test Command
if [ "${TEST_TARGETS}" == "ALL" ]; then
    GRADLE_CMD="./gradlew test -Pvalidation.git.failOnModified=false -Pvalidation.errorprone=false"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    # Gradle test filters
    # TEST_TARGETS is space separated "module:test --tests ClassName"
    # We simply pass it through as it's already formatted by get_test_targets.py
    GRADLE_CMD="./gradlew ${TEST_TARGETS} -Pvalidation.git.failOnModified=false -Pvalidation.errorprone=false"
fi

DOCKER_CMD="docker"
if ! docker info > /dev/null 2>&1; then
    if sudo docker info > /dev/null 2>&1; then
        echo "Docker requires sudo. Using 'sudo docker'."
        DOCKER_CMD="sudo docker"
    else
        echo "Warning: Docker command failed and sudo check failed. Continuing with 'docker' but expect errors."
    fi
fi

${DOCKER_CMD} volume create gradle-cache-solr 2>/dev/null || true
${DOCKER_CMD} volume create gradle-wrapper-solr 2>/dev/null || true

echo "--- Executing: ${GRADLE_CMD} ---"

if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "gradle-cache-solr:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-solr:/home/gradle/.gradle/wrapper" \
    -v "${BUILD_DIR}:/repo/build_outputs" \
    "${IMAGE_TAG}" \
    bash -c "${GRADLE_CMD}; \
    GRADLE_EXIT_CODE=\$?; \
    mkdir -p /repo/build_outputs/build; \
    rsync -a --include='*/' --include='TEST-*.xml' --exclude='*' /repo/solr/ /repo/build_outputs/build/ || echo 'Rsync failed'; \
    find /repo/build_outputs -name 'TEST-*.xml'; \
    exit \$GRADLE_EXIT_CODE"; then
    
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi

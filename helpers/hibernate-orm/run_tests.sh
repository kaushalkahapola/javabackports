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
    TEST_CMD="${GRADLE_CMD} -i"
    
    # Try running tests
    if ${TEST_CMD} > test_output.log 2>&1; then
       cat test_output.log
       RET=0
    else
       RET=\$?
       cat test_output.log
       # Check for JDK requirement failure
       if grep -q "requires at least JDK 25" test_output.log; then
           echo "--- Detected JDK 25 requirement. Retrying tests with JDK 25... ---"
           export JAVA_HOME=/opt/java/jdk-25
           export PATH="${JAVA_HOME}/bin:${PATH}"
           ${TEST_CMD}
           RET=\$?
       fi
    fi \
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

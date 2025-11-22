#!/bin/bash
set -e

echo "=== Running Tests for ${COMMIT_SHA:0:7} ==="
echo "Target Modules: ${TEST_TARGETS}"

# 1. Configure Test Command
if [ "${TEST_TARGETS}" == "ALL" ]; then
    # Run standard unit tests for everything (skipping broken modules)
    # We skip integration tests (ITs) as they usually require a running cluster
    MAVEN_ARGS="-pl '!web-console,!distribution'"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    # Run tests ONLY for the affected modules
    # -pl module1,module2 -am (also make dependencies) is safer, 
    # but for pure unit tests, just -pl is usually enough and faster.
    MAVEN_ARGS="-pl ${TEST_TARGETS}"
fi

echo "--- Starting Test Execution ---"
echo "--- Command: mvn test ${MAVEN_ARGS} ---"

# 2. Run Tests
# We use the same 'maven-repo' volume from the build step
docker volume create maven-repo 2>/dev/null || true

# We reuse the builder image
# We mount the repo and the maven cache
if docker run --rm \
    -v "${PROJECT_DIR}:/repo" \
    -v "maven-repo:/root/.m2/repository" \
    -w /repo \
    "${BUILDER_IMAGE_TAG}" \
    bash -c "git checkout -f ${COMMIT_SHA} && mvn test ${MAVEN_ARGS} -DfailIfNoTests=false -Dmaven.javadoc.skip=true -Dcheckstyle.skip=true"; then
    
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi
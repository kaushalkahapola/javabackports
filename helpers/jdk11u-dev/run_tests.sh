#!/bin/bash
# This script runs on the HOST. It starts Docker to run the tests.
set -euo pipefail

echo "=== Starting JDK 11 Tests in Docker for ${COMMIT_SHA:0:7} ==="

# Define the internal test script
TEST_SCRIPT_PATH_IN_CONTAINER="/tmp/test.sh"
LOCAL_TEST_SCRIPT="${TOOLKIT_DIR}/test.sh"

# Run the tests in a container
if docker run --rm --dns=8.8.8.8 \
    -v "${PROJECT_DIR}:/repo" \
    -v "${LOCAL_TEST_SCRIPT}:${TEST_SCRIPT_PATH_IN_CONTAINER}" \
    -e "COMMIT_SHA=${COMMIT_SHA}" \
    -e "BUILD_DIR_NAME=${BUILD_DIR_NAME}" \
    -e "TEST_TARGETS=${TEST_TARGETS}" \
    -e "JTREG_HOME=${JTREG_HOME}" \
    -w /repo \
    "${BUILDER_IMAGE_TAG}" \
    bash "${TEST_SCRIPT_PATH_IN_CONTAINER}"
then
    echo "=== Tests passed for ${COMMIT_SHA:0:7} ==="
    exit 0
else
    echo "=== Tests failed for ${COMMIT_SHA:0:7} ==="
    exit 1
fi
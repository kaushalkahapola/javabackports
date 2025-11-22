#!/bin/bash
# This script runs INSIDE the Docker container
set -e

echo "--- Inside Docker: Running tests for ${COMMIT_SHA:0:7} ---"
echo "Target: ${TEST_TARGETS}"

# 1. Define Build Directory
# In JDK 11+ build.sh, we created a separate build directory inside /repo
BUILD_DIR_ABS="/repo/${BUILD_DIR_NAME}"

if [ ! -d "${BUILD_DIR_ABS}" ]; then
    echo "❌ Error: Build directory not found at ${BUILD_DIR_ABS}"
    echo "The build must succeed before running tests."
    exit 1
fi

cd "${BUILD_DIR_ABS}"

# 2. Configure Test Targets
if [ "${TEST_TARGETS}" == "ALL" ]; then
    TEST_LIST="tier1"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No relevant source code changes found. Skipping tests."
    exit 0
else
    TEST_LIST="${TEST_TARGETS}"
fi

echo "--- Starting Test Execution in ${BUILD_DIR_ABS} ---"

FINAL_EXIT_CODE=0

# 3. Iterate and Run
for TARGET in ${TEST_LIST}; do
    echo "--- Running target: ${TARGET} ---"
    
    set +e
    
    # JDK 11+ Unified Test Framework
    # We can just pass the path or group to TEST=
    # JTREG="VERBOSE=fail,error" keeps logs clean
    make test TEST="${TARGET}" \
         JOBS=$(nproc) \
         JTREG="VERBOSE=fail,error"
    
    EXIT_CODE=$?
    set -e
    
    if [ ${EXIT_CODE} -ne 0 ]; then
        echo "❌ Target ${TARGET} FAILED"
        FINAL_EXIT_CODE=1
    else
        echo "✅ Target ${TARGET} PASSED"
    fi
done

if [ ${FINAL_EXIT_CODE} -eq 0 ]; then
    echo "=== ALL TESTS PASSED ==="
    exit 0
else
    echo "=== SOME TESTS FAILED ==="
    exit 1
fi
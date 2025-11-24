#!/bin/bash
set -e

echo "--- Inside Docker: Running tests for ${COMMIT_SHA:0:7} ---"
echo "Target: ${TEST_TARGETS}"

BUILD_DIR_ABS="/repo/${BUILD_DIR_NAME}"
[ -d "$BUILD_DIR_ABS" ] || { echo "Build dir missing"; exit 1; }
cd "$BUILD_DIR_ABS"

if [ "${TEST_TARGETS}" == "ALL" ]; then
    TEST_LIST="tier1"
elif [ "${TEST_TARGETS}" == "NONE" ]; then
    echo "No tests to run"
    exit 0
else
    TEST_LIST="${TEST_TARGETS}"
fi

echo "--- Starting Test Execution in $BUILD_DIR_ABS ---"

FINAL_EXIT_CODE=0

for TARGET in ${TEST_LIST}; do
    echo "=== Running test target: ${TARGET} ==="

    set +e

# In the make test command:
    make test TEST="${TARGET}" \
        JOBS=$(nproc) \
        JTREG="VERBOSE=all,fail,error,summary,time OPTIONS=-xml:verify -va -vp" \
        JTREG_VERBOSE=all \
        IGNORE_INTERNAL_VM_WARNINGS=true \
        2>&1 | tee test_output_${TARGET}.log

    EXIT_CODE=$?
    set -e

    if [ $EXIT_CODE -ne 0 ]; then
        echo "❌ Target ${TARGET} FAILED"
        FINAL_EXIT_CODE=1
    else
        echo "✅ Target ${TARGET} PASSED"
    fi
done

if [ $FINAL_EXIT_CODE -eq 0 ]; then
    echo "=== ALL TESTS PASSED ==="
    exit 0
else
    echo "=== SOME TESTS FAILED ==="
    exit 1
fi
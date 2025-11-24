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
    
    # Create unique work/report directories for this target
    WORK_DIR="${BUILD_DIR_ABS}/JTwork_${TARGET//\//_}"
    REPORT_DIR="${BUILD_DIR_ABS}/JTreport_${TARGET//\//_}"
    mkdir -p "${WORK_DIR}" "${REPORT_DIR}"
    
    set +e
    
    # Method 1: Try make test first (with proper options)
    make test TEST="${TARGET}" \
         JOBS=$(nproc) \
         JTREG="VERBOSE=all OPTIONS=-xml:verify -retain:all" \
         TEST_OPTS="-va -vp" \
         IGNORE_INTERNAL_VM_WARNINGS=true
    
    EXIT_CODE=$?
    
    # Method 2: If make test doesn't produce good output, try direct jtreg
    # Check if we got XML files from make test
    XML_COUNT=$(find "${BUILD_DIR_ABS}" -name "*.xml" -path "*/JTwork/*" 2>/dev/null | wc -l)
    
    if [ $XML_COUNT -eq 0 ]; then
        echo "--- No XML found from make test, trying direct jtreg invocation ---"
        
        # Determine the actual test path
        if [[ "${TARGET}" == test/* ]]; then
            # Already has 'test/' prefix
            TEST_PATH="/repo/${TARGET}"
        elif [[ "${TARGET}" == jdk_* ]] || [[ "${TARGET}" == tier* ]]; then
            # It's a test group, use make test (already tried above)
            echo "Test group ${TARGET} - relying on make test results"
        else
            # Assume it's a path relative to test/
            TEST_PATH="/repo/test/${TARGET}"
        fi
        
        # Only try direct jtreg if we have a specific path
        if [ -n "${TEST_PATH}" ] && [ -d "${TEST_PATH}" ]; then
            echo "--- Running jtreg directly on ${TEST_PATH} ---"
            
            ${JTREG_HOME}/bin/jtreg \
                -jdk:"${BUILD_DIR_ABS}/images/jdk" \
                -verbose:all \
                -retain:all \
                -xml:verify \
                -workDir:"${WORK_DIR}" \
                -reportDir:"${REPORT_DIR}" \
                -timeoutFactor:5 \
                -conc:$(nproc) \
                "${TEST_PATH}"
            
            EXIT_CODE=$?
        fi
    fi
    
    set -e
    
    # Debug: Show where test results ended up
    echo "--- Searching for test results after ${TARGET} ---"
    find "${BUILD_DIR_ABS}" -name "*.xml" -type f 2>/dev/null | grep -E "(JTwork|JTreport)" | head -20 || echo "No XML files found"
    
    # Also show directory structure
    echo "--- Directory structure: ---"
    ls -la "${BUILD_DIR_ABS}" 2>/dev/null | grep JT || echo "No JT directories found"
    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "❌ Target ${TARGET} FAILED (exit code: ${EXIT_CODE})"
        FINAL_EXIT_CODE=1
    else
        echo "✅ Target ${TARGET} PASSED"
    fi
done

# Final debug: Show all XML locations
echo "=== FINAL XML REPORT LOCATIONS ==="
find /repo -name "*.xml" -type f 2>/dev/null | head -50

if [ $FINAL_EXIT_CODE -eq 0 ]; then
    echo "=== ALL TESTS PASSED ==="
    exit 0
else
    echo "=== SOME TESTS FAILED ==="
    exit 1
fi
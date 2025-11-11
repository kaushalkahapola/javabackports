#!/usr/bin/env bash
# This script runs INSIDE the Docker container
set -euo pipefail

echo "=== Building JDK for ${COMMIT_SHA:0:7} (Inside Container) ==="

# The Boot JDK and jtreg are provided by the Docker image's env variables
echo "Using Boot JDK: ${BOOT_JDK}"
echo "Using jtreg: ${JTREG_HOME}"

# Checkout the specific commit
echo "Checking out commit: ${COMMIT_SHA}"
git checkout -f "${COMMIT_SHA}"

# Define the build directory path (relative to /repo)
export BUILD_DIR_ABS="/repo/${BUILD_DIR_NAME}"
echo "--- Creating build directory: ${BUILD_DIR_ABS} ---"
mkdir -p "${BUILD_DIR_ABS}"

# 'cd' into the build directory
cd "${BUILD_DIR_ABS}"

echo "--- Configuring build from outside source dir... ---"

# Note: --disable-warnings-as-errors does NOT exist in JDK 8
bash ../configure \
    --with-boot-jdk="${BOOT_JDK}" \
    --with-jtreg="${JTREG_HOME}" \
    --enable-ccache \
    --with-debug-level=release \
    --with-native-debug-symbols=none \
    --disable-zip-debug-info

echo "--- Patching spec.gmk to disable warnings-as-errors... ---"
# JDK 8's build system hardcodes -Werror in many places
# We need to remove it from the generated spec.gmk file
if [ -f spec.gmk ]; then
    # Remove -Werror flags from all compiler flag variables
    sed -i 's/-Werror[^ ]*//g' spec.gmk
    sed -i 's/WARNINGS_ARE_ERRORS[[:space:]]*:=[[:space:]]*-Werror/WARNINGS_ARE_ERRORS :=/g' spec.gmk
    echo "--- spec.gmk patched ---"
else
    echo "--- Warning: spec.gmk not found, skipping patch ---"
fi

# Build the JDK
echo "--- Running make... (Output will be in ${BUILD_DIR_ABS}) ---"

# Run 'make' from inside the build dir.
# For JDK 8, use 'all' target instead of 'images'
# Pass multiple flags to disable warnings-as-errors
if make JOBS="${MAKE_JOBS:-$(nproc)}" all \
    COMPILER_WARNINGS_FATAL=false \
    WARNINGS_ARE_ERRORS="" \
    CFLAGS_WARNINGS_ARE_ERRORS=""; then
    echo "=== Build OK ==="
else
    echo "=== Build FAILED ==="
    exit 1
fi
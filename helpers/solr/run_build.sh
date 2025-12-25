#!/bin/bash
# This script builds the Docker image and compiles the code.
set -e # Exit on error

echo "--- Building code for ${COMMIT_SHA:0:7} ---"

echo "--- Changing directory to ${PROJECT_DIR} ---"
cd "${PROJECT_DIR}"

echo "--- Checking out commit... ---"
git checkout -f ${COMMIT_SHA}
git clean -fd

# Create persistent Gradle cache volumes
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

echo "--- Building Docker image... ---"
${DOCKER_CMD} build -t ${IMAGE_TAG} -f ${TOOLKIT_DIR}/Dockerfile .

echo "--- Setting cache permissions... ---"
${DOCKER_CMD} run --rm -u root \
    -v "gradle-cache-solr:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-solr:/home/gradle/.gradle/wrapper" \
    -v "${BUILD_DIR}:/repo/build" \
    ${IMAGE_TAG} \
    chown -R 1000:1000 /home/gradle/.gradle/caches /home/gradle/.gradle/wrapper /repo/build

echo "--- Compiling and preparing for tests... ---"
# Solr build: assemble testClasses
# We disable git validation to prevent failures on modified files (if any artifact is left over)
# We disable errorprone to avoid strict compilation errors unrelated to backports
if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "gradle-cache-solr:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-solr:/home/gradle/.gradle/wrapper" \
    -v "${BUILD_DIR}:/repo/build" \
    ${IMAGE_TAG} \
    ./gradlew assemble testClasses -x test -Pvalidation.git.failOnModified=false -Pvalidation.errorprone=false --continue; then
    echo "Success" > $BUILD_STATUS_FILE
else
    echo "Fail" > $BUILD_STATUS_FILE
fi

echo "--- Build complete for ${COMMIT_SHA:0:7} ---"

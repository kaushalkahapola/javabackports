#!/bin/bash
# This script builds the Docker image and compiles the code.
set -e # Exit on error

echo "--- Building code for ${COMMIT_SHA:0:7} ---"

echo "--- Changing directory to ${PROJECT_DIR} ---"
cd "${PROJECT_DIR}"

echo "--- Checking out commit... ---"
git checkout -f ${COMMIT_SHA}
git clean -fd

# Create persistent Maven cache volume if it doesn't exist
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

${DOCKER_CMD} volume create maven-cache-flow 2>/dev/null || true

echo "--- Building Docker image... ---"
# -f points to the Dockerfile in our toolkit
# . (the context) is the PROJECT_DIR we just cd'd into
${DOCKER_CMD} build -t ${IMAGE_TAG} -f ${TOOLKIT_DIR}/Dockerfile .

echo "--- Setting cache permissions... ---"
${DOCKER_CMD} run --rm -u root \
    -v "maven-cache-flow:/home/maven/.m2" \
    -v "${BUILD_DIR}:/repo/target" \
    ${IMAGE_TAG} \
    chown -R 1000:1000 /home/maven/.m2 /repo/target

echo "--- Compiling and preparing for tests... ---"
# Vaadin Flow build: mvn clean install -DskipTests
if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "maven-cache-flow:/home/maven/.m2" \
    ${IMAGE_TAG} \
    mvn clean install -DskipTests -Dmaven.javadoc.skip=true -B -V; then
    echo "Success" > $BUILD_STATUS_FILE
else
    echo "Fail" > $BUILD_STATUS_FILE
fi

echo "--- Build complete for ${COMMIT_SHA:0:7} ---"

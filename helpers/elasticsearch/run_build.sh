#!/bin/bash
# This script builds the Docker image and compiles the code.
set -e # Exit on error

echo "--- Building code for ${COMMIT_SHA:0:7} ---"

echo "--- Changing directory to ${PROJECT_DIR} ---"
cd ${PROJECT_DIR}"

echo "--- Checking out commit... ---"
git checkout ${COMMIT_SHA}

echo "--- Building Docker image... ---"
# -f points to the Dockerfile in our toolkit
# . (the context) is the PROJECT_DIR we just cd'd into
docker build -t ${IMAGE_TAG} -f ${TOOLKIT_DIR}/Dockerfile .

echo "--- Setting cache permissions... ---"
docker run --rm -u root \
    -v "gradle-cache:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper:/home/gradle/.gradle/wrapper" \
    ${IMAGE_TAG} \
    chown -R 1000:1000 /home/gradle/.gradle/caches /home/gradle/.gradle/wrapper

echo "--- Compiling ALL modules... ---"
if docker run --rm \
    --dns=8.8.8.8 \
    -v "gradle-cache:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper:/home/gradle/.gradle/wrapper" \
    -v "${BUILD_DIR}:/repo/build" \
    ${IMAGE_TAG} \
    ./gradlew classes -Dbuild.docker=false --continue; then
    echo "Success" > $BUILD_STATUS_FILE
else
    echo "Fail" > $BUILD_STATUS_FILE
fi

echo "--- Build complete for ${COMMIT_SHA:0:7} ---"
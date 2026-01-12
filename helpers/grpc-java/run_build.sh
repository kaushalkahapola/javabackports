#!/bin/bash
# run_build.sh for grpc-java
set -e

echo "--- Building code for ${COMMIT_SHA:0:7} ---"

echo "--- Changing directory to ${PROJECT_DIR} ---"
cd "${PROJECT_DIR}"

echo "--- Checking out commit... ---"
git checkout -f ${COMMIT_SHA}
git clean -fd

# Create persistent Gradle cache volumes if they don't exist
docker volume create gradle-cache-grpc-java 2>/dev/null || true
docker volume create gradle-wrapper-grpc-java 2>/dev/null || true

echo "--- Building Docker image... ---"
docker build -t ${IMAGE_TAG} -f ${TOOLKIT_DIR}/Dockerfile .

echo "--- Setting cache permissions... ---"
docker run --rm -u root \
    -v "gradle-cache-grpc-java:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-grpc-java:/home/gradle/.gradle/wrapper" \
    ${IMAGE_TAG} \
    chown -R 1000:1000 /home/gradle/.gradle/caches /home/gradle/.gradle/wrapper

echo "--- Setting permissions on source directory... ---"
docker run --rm -u root \
    -v "${PROJECT_DIR}:/repo" \
    -w /repo \
    ${IMAGE_TAG} \
    chown -R 1000:1000 /repo

echo "--- Compiling and preparing for tests... ---"
if docker run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "gradle-cache-grpc-java:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-grpc-java:/home/gradle/.gradle/wrapper" \
    -v "${PROJECT_DIR}:/repo" \
    -w /repo \
    ${IMAGE_TAG} \
    ./gradlew classes testClasses -PskipAndroid=true -PskipCodegen=true --continue; then
    echo "Success" > $BUILD_STATUS_FILE
else
    echo "Fail" > $BUILD_STATUS_FILE
fi

echo "--- Build complete for ${COMMIT_SHA:0:7} ---"

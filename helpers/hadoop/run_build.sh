#!/bin/bash
# This script runs the Hadoop (Maven) build inside our pre-built Docker container.
set -euo pipefail

echo "=== Starting Hadoop Build in Docker for ${COMMIT_SHA:0:7} ==="

# We create a persistent maven cache volume to speed up builds
docker volume create --name=maven-cache || true

# This avoids the parent POM trying to resolve modules we want to skip
BUILD_COMMAND="git checkout -f ${COMMIT_SHA} && \
  mvn clean install -DskipTests -Dmaven.javadoc.skip=true -Drat.skip=true \
    -pl hadoop-common-project/hadoop-common \
    -pl hadoop-hdfs-project/hadoop-hdfs \
    -pl hadoop-mapreduce-project \
    -am"


# Run the build in a container
if docker run --rm --dns=8.8.8.8 \
    -v "${PROJECT_DIR}:/repo" \
    -v "maven-cache:/root/.m2" \
    -w /repo \
    "${BUILDER_IMAGE_TAG}" \
    bash -c "rm -rf /root/.m2/repository/org/apache/hadoop && ${BUILD_COMMAND}"
then
    echo "Success" > "${BUILD_STATUS_FILE}"
else
    echo "Fail" > "${BUILD_STATUS_FILE}"
fi

echo "=== Build finished for ${COMMIT_SHA:0:7} ==="
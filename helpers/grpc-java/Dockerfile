# Dockerfile for grpc-java build/test environment
FROM gradle:8.5.0-jdk17 AS builder

WORKDIR /repo

# Install Protobuf compiler, C/C++ build tools, and dependencies
RUN apt-get update && apt-get install -y \
    protobuf-compiler \
    libprotobuf-dev \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Default user is gradle (UID 1000)
# The toolkit scripts will mount caches and source code

CMD ["/bin/bash"]

# Use JDK 17 as recommended for Solr 9.x
FROM eclipse-temurin:17-jdk-jammy

# Install basic tools
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user 'gradle'
RUN groupadd --gid 1000 gradle && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home gradle

# Create the global .gradle directory
RUN mkdir -p /home/gradle/.gradle

# Configure Gradle properties for performance
RUN echo "org.gradle.daemon=true" >> /home/gradle/.gradle/gradle.properties && \
    echo "org.gradle.parallel=true" >> /home/gradle/.gradle/gradle.properties && \
    echo "org.gradle.workers.max=6" >> /home/gradle/.gradle/gradle.properties && \
    echo "org.gradle.caching=true" >> /home/gradle/.gradle/gradle.properties

# Set ownership
RUN chown -R gradle:gradle /home/gradle/.gradle

# Create /repo
RUN mkdir /repo && chown gradle:gradle /repo

WORKDIR /repo

# Copy files *AS* the gradle user
COPY --chown=gradle:gradle . .

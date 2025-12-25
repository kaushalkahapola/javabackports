# Use JDK 17 as researched for Hive 4.1
FROM eclipse-temurin:17-jdk-jammy

# Install basic tools and Maven
ENV MAVEN_VERSION=3.9.6
ENV BASE_URL=https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries

RUN apt-get update && apt-get install -y \
    git \
    python3 \
    curl \
    gnupg \
    && mkdir -p /usr/share/maven /usr/share/maven/ref \
    && curl -fsSL -o /tmp/apache-maven.tar.gz ${BASE_URL}/apache-maven-${MAVEN_VERSION}-bin.tar.gz \
    && tar -xzf /tmp/apache-maven.tar.gz -C /usr/share/maven --strip-components=1 \
    && rm -f /tmp/apache-maven.tar.gz \
    && ln -s /usr/share/maven/bin/mvn /usr/bin/mvn \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a non-root user 'maven' (similar to kafka's 'gradle' user pattern)
RUN groupadd --gid 1000 maven && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home maven

# Configure Maven
USER maven
RUN mkdir -p /home/maven/.m2
COPY --chown=maven:maven . /repo
WORKDIR /repo

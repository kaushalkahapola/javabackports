# Use a standard, trusted Java 21 (JDK) image
FROM eclipse-temurin:17-jdk-jammy

# Install basic tools (git, python3) and Node.js/npm for Vaadin frontend
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    unzip \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Maven
ARG MAVEN_VERSION=3.9.6
ARG BASE_URL=https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries

RUN mkdir -p /usr/share/maven /usr/share/maven/ref \
 && curl -fsSL -o /tmp/apache-maven.tar.gz ${BASE_URL}/apache-maven-${MAVEN_VERSION}-bin.tar.gz \
 && tar -xzf /tmp/apache-maven.tar.gz -C /usr/share/maven --strip-components=1 \
 && rm -f /tmp/apache-maven.tar.gz \
 && ln -s /usr/share/maven/bin/mvn /usr/bin/mvn

# Create a non-root user 'maven'
RUN groupadd --gid 1000 maven && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home maven

# Create the global .m2 directory
RUN mkdir -p /home/maven/.m2

# Set ownership for the .m2 dir
RUN chown -R maven:maven /home/maven/.m2

# Create the /repo dir and give the maven user ownership
RUN mkdir /repo
RUN chown maven:maven /repo

# Set up a working directory inside the container
WORKDIR /repo

# Copy all files *AS* the maven user.
COPY --chown=maven:maven . .

# JavaBackports: A Dataset for Benchmarking Automated Backporting in Java

[![Dataset](https://img.shields.io/badge/dataset-474%20backports-blue.svg)](#-dataset-overview)
[![Projects](https://img.shields.io/badge/projects-8%20Java%20repos-green.svg)](#-included-projects)




## Dataset Overview

The JavaBackports dataset contains **474 manually validated backport instances** spanning across 8 major Java projects. Each backport represents a real-world scenario where a patch from a main development branch was adapted and applied to a long-term support or stable release branch.


### Dataset Schema

Each CSV file contains the following columns:

| Column | Description |
|--------|-------------|
| `Project` | Name of the source project (e.g., "kafka", "druid", "jdk17u-dev") |
| `Original Version` | Source branch/version where the original patch was applied (e.g., "trunk", "master") |
| `Original Commit` | SHA hash of the original commit in the source branch |
| `Backport Version` | Target branch/version where the backport was applied (e.g., "3.6", "29.0.1") |
| `Backport Commit` | SHA hash of the backported commit in the target branch |
| `Backport Date` | DateTime | Timestamp when the backport was committed |
| `Type` | Classification of backport complexity (TYPE-I, TYPE-II, ... TYPE-V) |


## Included Projects

The dataset covers 8 major Java projects representing different domains:

| Project | Repository | Domain |
|---------|------------|--------|
| **Apache Druid** | [apache/druid](https://github.com/apache/druid) | Real-time analytics database |
| **Elasticsearch** | [elastic/elasticsearch](https://github.com/elastic/elasticsearch) | Search and analytics engine |
| **Apache Hadoop** | [apache/hadoop](https://github.com/apache/hadoop) | Distributed computing framework |
| **Apache Kafka** | [apache/kafka](https://github.com/apache/kafka) | Distributed streaming platform |
| **OpenJDK 8** | [openjdk/jdk8u-dev](https://github.com/openjdk/jdk8u-dev) | Java Development Kit 8 LTS |
| **OpenJDK 11** | [openjdk/jdk11u-dev](https://github.com/openjdk/jdk11u-dev) | Java Development Kit 11 LTS |
| **OpenJDK 17** | [openjdk/jdk17u-dev](https://github.com/openjdk/jdk17u-dev) | Java Development Kit 17 LTS |
| **OpenJDK 21** | [openjdk/jdk21u-dev](https://github.com/openjdk/jdk21u-dev) | Java Development Kit 21 LTS |


---

# Build Tool

This repository also includes a comprehensive build tool for reproducing and testing the backport instances in containerized environments. The tool enables researchers to replicate builds for any commit in the dataset.

## Table of Contents

- [Prerequisites](#-prerequisites-1)
- [Setup](#-setup-1)
- [Usage](#-usage-1)
- [Supported Projects](#-supported-projects)
- [Directory Structure](#-directory-structure)

## Prerequisites

Before using the build tool, ensure you have the following installed:

> **Recommended OS**: Ubuntu/Debian-based Linux (Windows and macOS may require additional configuration)

### Required Software

| Tool | Version | Purpose |
|------|---------|---------|
| **Git** | Latest | Source code management |
| **Python** | 3.8+ | Running build scripts |
| **pip** | Latest | Installing Python dependencies |
| **Docker** | Latest | Containerized build environments |

### Docker Setup (Critical)

**Important**: You must configure Docker to run without `sudo` privileges:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Apply the changes (logout and login required)
newgrp docker
```

> ⚠️ **Warning**: You must log out and log back in after running the `usermod` command for changes to take effect.

### Verify Docker Installation

```bash
# Test Docker without sudo
docker run hello-world
```

## Setup

### Step 1: Install Python Dependencies

Install the required Python packages:

```bash
pip3 install pandas
```

### Step 2: Clone This Repository

```bash
git clone https://github.com/kaushalkahapola/javabackports.git
cd javabackports
```

### Step 3: Set Up Project Repositories

> **Critical Step**: The build scripts expect project repositories to be located in the **parent directory** of this toolkit.

Clone the project repositories you want to test **adjacent** to this repository:

```bash
# Navigate to parent directory
cd ..

# Clone target projects (examples)
git clone https://github.com/apache/kafka.git
git clone https://github.com/apache/hadoop.git
git clone https://github.com/openjdk/jdk17u-dev.git
git clone https://github.com/openjdk/jdk11u-dev.git
git clone https://github.com/openjdk/jdk8u-dev.git
git clone https://github.com/openjdk/jdk21u-dev.git
git clone https://github.com/elastic/elasticsearch.git
git clone https://github.com/apache/druid.git
```

### Required Directory Structure

Your workspace must follow this exact structure:

```
📁 your-research-workspace/
│
├── 📁 javabackports/              ← This repository
│   ├── 📄 build_commit.py         ← Main build script
│   ├── 📄 README.md
│   ├── 📁 dataset/                ← Commit datasets
│   │   ├── kafka.csv
│   │   ├── hadoop.csv
│   │   └── ...
│   └── 📁 helpers/                ← Docker configurations
│       ├── kafka/
│       ├── hadoop/
│       └── ...
│
├── 📁 kafka/                      ← Apache Kafka repository
├── 📁 hadoop/                     ← Apache Hadoop repository  
├── 📁 jdk17u-dev/                 ← OpenJDK 17 repository
├── 📁 jdk11u-dev/                 ← OpenJDK 11 repository
├── 📁 jdk8u-dev/                  ← OpenJDK 8 repository
├── 📁 jdk21u-dev/                 ← OpenJDK 21 repository
├── 📁 elasticsearch/              ← Elasticsearch repository
└── 📁 druid/                      ← Apache Druid repository
```

## Usage

All builds are executed from the `javabackports` directory using the `build_commit.py` script.

### Command Line Arguments

| Argument | Short | Required | Description |
|----------|-------|----------|-------------|
| `--project` | `-p` | ✅ Yes | Name of the project to build |
| `--commit` | `-c` | ✅ Yes | Commit hash to build (the "after"/"fixed" version) |
| `--build-before` | `-b` | ❌ No | Also build the parent commit ("before"/"buggy" version) |

### Basic Command Structure

```bash
python3 build_commit.py --project <PROJECT_NAME> --commit <COMMIT_HASH> [--build-before]
```

### Examples

#### Example 1: Build Fixed Version Only

Build the "after" (fixed) version of a Kafka commit:

```bash
python3 build_commit.py --project kafka --commit 6351bc05aafc8ba480e9f85ab702e67e48416953
```

#### Example 2: Build Both Versions

Build **both** "before" (buggy) and "after" (fixed) versions for comparison:

```bash
python3 build_commit.py --project hadoop --commit e6cf6e6 --build-before
```

#### Example 3: Build JDK Commit

Build a specific JDK 17 commit:

```bash
python3 build_commit.py --project jdk17u-dev --commit ffa7dd545d654060803405786375c879d2b8b937
```

#### Example 4: Build with Short Commit Hash

You can use shortened commit hashes:

```bash
python3 build_commit.py --project elasticsearch --commit a1b2c3d --build-before
```

### Viewing Results

- **Live Output**: All build logs stream directly to your terminal in real-time
- **Saved Results**: Build artifacts and status files are automatically saved to:
  ```
  build_results/
  ├── <project_name>/
  │   └── <commit_hash>/
  │       ├── fixed_build_status.txt
  │       ├── buggy_build_status.txt (if --build-before used)
  │       └── build_logs/
  ```


## 📁 Directory Structure

```
javabackports/
├── 📄 build_commit.py              # Main build orchestrator
├── 📄 README.md                    # This file
│
├── 📁 dataset/                     # Research datasets
│   ├── all_projects_combined.csv  # Complete dataset (474 instances)
│   ├── kafka.csv                  # Kafka commit dataset
│   ├── hadoop.csv                 # Hadoop commit dataset
│   ├── jdk8u-dev.csv             # JDK 8 commit dataset
│   ├── jdk11u-dev.csv            # JDK 11 commit dataset
│   ├── jdk17u-dev.csv            # JDK 17 commit dataset
│   ├── jdk21u-dev.csv            # JDK 21 commit dataset
│   ├── elasticsearch.csv          # Elasticsearch commit dataset
│   └── druid.csv                  # Druid commit dataset
│
└── 📁 helpers/                     # Docker build configurations
    ├── kafka/                     # Kafka build environment
    │   ├── Dockerfile
    │   └── run_build.sh
    ├── hadoop/                    # Hadoop build environment
    │   ├── Dockerfile
    │   └── run_build.sh
    ├── jdk8u-dev/                # JDK 8 build environment
    │   ├── Dockerfile
    │   ├── build.sh
    │   └── run_build.sh
    ├── jdk11u-dev/               # JDK 11 build environment
    │   ├── Dockerfile
    │   ├── build.sh
    │   └── run_build.sh
    ├── jdk17u-dev/               # JDK 17 build environment
    │   ├── Dockerfile
    │   ├── build.sh
    │   └── run_build.sh
    ├── jdk21u-dev/               # JDK 21 build environment
    │   ├── Dockerfile
    │   ├── build.sh
    │   └── run_build.sh
    ├── elasticsearch/             # Elasticsearch build environment
    │   ├── Dockerfile
    │   └── run_build.sh
    └── druid/                     # Druid build environment
        ├── Dockerfile
        └── run_build.sh
```

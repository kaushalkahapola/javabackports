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

-----

# Build & Test Tool

This repository also includes a comprehensive build and test orchestration tool. It enables researchers to replicate builds and run regression tests for any commit in the dataset using containerized environments.

## Table of Contents

  - [Prerequisites](https://www.google.com/search?q=%23-prerequisites-1)
  - [Setup](https://www.google.com/search?q=%23-setup-1)
  - [Usage](https://www.google.com/search?q=%23-usage-1)
  - [Supported Projects](https://www.google.com/search?q=%23-supported-projects)
  - [Directory Structure](https://www.google.com/search?q=%23-directory-structure)

## Prerequisites

Before using the build tool, ensure you have the following installed:

> **Recommended OS**: Ubuntu/Debian-based Linux (Windows and macOS may require additional configuration)

### Required Software

| Tool | Version | Purpose |
|------|---------|---------|
| **Git** | Latest | Source code management |
| **Python** | 3.8+ | Running build scripts |
| **pip** | Latest | Installing Python dependencies |
| **Docker** | Latest | Containerized build/test environments |

### Docker Setup (Critical)

**Important**: You must configure Docker to run without `sudo` privileges:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Apply the changes (logout and login required)
newgrp docker
```

## Setup

### Step 1: Install Python Dependencies

```bash
pip3 install pandas
```

### Step 2: Clone This Repository

```bash
git clone https://github.com/your-repo/javabackports.git
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
# ... (clone other projects as needed)
```

### Required Directory Structure

Your workspace must follow this exact structure:

```
📁 your-research-workspace/
│
├── 📁 javabackports/              ← This repository
│   ├── 📄 build_commit.py         ← Main orchestrator
│   ├── 📄 README.md
│   ├── 📁 dataset/                ← Commit datasets
│   └── 📁 helpers/                ← Build & Test logic
│       ├── kafka/
│       ├── hadoop/
│       └── ...
│
├── 📁 kafka/                      ← Apache Kafka repository
├── 📁 hadoop/                     ← Apache Hadoop repository  
└── ...
```

## Usage

All operations are executed from the `javabackports` directory using the `build_commit.py` script.

### Command Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--project` | `-p` | **(Required)** Name of the project to build | - |
| `--commit` | `-c` | **(Required)** Commit hash to build (the "after"/"fixed" version) | - |
| `--build-before` | `-b` | Also build the parent commit ("before"/"buggy" version) | False |
| `--run-tests` | | Run tests after a successful build | False |
| `--test-target` | | Which version to test: `fixed`, `buggy`, or `both` | `fixed` |
| `--test-strategy` | | Test selection mode: `smart` (filtered) or `all` (full suite) | `smart` |

### Basic Build Examples

**Build Fixed Version Only:**

```bash
python3 build_commit.py --project kafka --commit 6351bc05aafc8ba480e9f85ab702e67e48416953
```

**Build Both Versions:**

```bash
python3 build_commit.py --project hadoop --commit e6cf6e6 --build-before
```

### Test Execution Examples

**Build & Smart Test (Recommended):**
This uses `get_test_targets.py` to analyze the git diff and run only relevant tests/modules.

```bash
python3 build_commit.py --project jdk8u-dev --commit <SHA> --run-tests
```

**Build & Run ALL Tests:**
Warning: This can take hours depending on the project.

```bash
python3 build_commit.py --project kafka --commit <SHA> --run-tests --test-strategy all
```

**Test Both Versions (Regression Check):**
Builds and tests both the buggy and fixed versions to verify the fix.

```bash
python3 build_commit.py --project druid --commit <SHA> --build-before --run-tests --test-target both
```

### Viewing Results

  - **Live Output**: Build and test logs stream directly to your terminal.
  - **Saved Results**: Artifacts are saved locally to `build_results/`:
    ```
    build_results/
    ├── <project_name>/
    │   └── <commit_hash>/
    │       ├── fixed_build_status.txt    # Success / Fail
    │       ├── buggy_build_status.txt    # Success / Fail
    │       └── final_build_report.txt    # Summary including test results
    ```


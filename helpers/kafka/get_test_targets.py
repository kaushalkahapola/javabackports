#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to analyze")
    args = parser.parse_args()

    # 1. Get list of changed files
    cmd = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", args.commit]
    try:
        output = subprocess.check_output(cmd, cwd=args.repo, text=True)
    except subprocess.CalledProcessError:
        # Fallback if git fails
        print("test") 
        return

    changed_files = output.strip().splitlines()
    gradle_tasks = set()

    for f in changed_files:
        # Kafka structure: [module]/src/...
        # e.g. clients/src/main/java/org/apache/kafka/clients/producer/KafkaProducer.java
        
        parts = f.split("/")
        if len(parts) < 2:
            continue
            
        module = parts[0]
        
        # Verify it is a real module (has build.gradle)
        if not os.path.exists(os.path.join(args.repo, module, "build.gradle")):
            # Maybe it's a root file like build.gradle?
            if f == "build.gradle" or f == "gradle.properties":
                print("ALL") # Core build config changed, run everything (or specific subset)
                return
            continue

        # --- MAPPING LOGIC ---
        
        # 1. If it is a Test file, run ONLY that test class
        if "/src/test/" in f and f.endswith(".java") or f.endswith(".scala"):
            try:
                # Extract class name. 
                # Path: clients/src/test/java/org/apache/kafka/clients/MyTest.java
                # Want: org.apache.kafka.clients.MyTest
                
                # Find where package structure starts (after java/ or scala/)
                if "/java/" in f:
                    rel_path = f.split("/java/")[1]
                elif "/scala/" in f:
                    rel_path = f.split("/scala/")[1]
                else:
                    # Weird path, fall back to module
                    gradle_tasks.add(f":{module}:test")
                    continue

                class_name = rel_path.replace("/", ".").rsplit(".", 1)[0]
                
                # Gradle syntax for single test
                gradle_tasks.add(f":{module}:test --tests \"{class_name}\"")
            except IndexError:
                # Fallback
                gradle_tasks.add(f":{module}:test")

        # 2. If it is a Source file, run the whole module's tests
        elif "/src/main/" in f:
            gradle_tasks.add(f":{module}:test")
            
        # 3. Any other file in the module (resources, etc.)
        else:
            gradle_tasks.add(f":{module}:test")

    # 3. Output
    if not gradle_tasks:
        print("NONE")
    else:
        # Join all tasks. Gradle handles multiple tasks well.
        # e.g. :clients:test :core:test --tests "kafka.server.ReplicaManagerTest"
        print(" ".join(sorted(gradle_tasks)))

if __name__ == "__main__":
    main()
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
        print("test") # Fallback to running all tests
        return

    changed_files = output.strip().splitlines()
    gradle_tasks = set()

    for f in changed_files:
        # 1. Find the Gradle Module for this file
        # We walk up the directory tree until we find a build.gradle
        head = f
        module_path = ""
        while head:
            head, tail = os.path.split(head)
            if os.path.exists(os.path.join(args.repo, head, "build.gradle")):
                # Convert path to gradle module format: server/ -> :server
                # x-pack/plugin/core -> :x-pack:plugin:core
                if head == "": # Root directory
                    module_path = "" 
                else:
                    module_path = ":" + head.replace("/", ":")
                break
        
        # If we couldn't find a module (e.g. file deleted, or outside src), skip
        if module_path == "" and "build.gradle" not in f:
             continue

        # 2. Determine Test Target
        # If it's a test file, run it directly
        if f.endswith("Tests.java") or f.endswith("IT.java"):
            # Extract class name: org.elasticsearch.index.IndexTests
            # Remove src/test/java/ prefix if present
            try:
                if "src/test/java/" in f:
                    class_path = f.split("src/test/java/")[1]
                    class_name = class_path.replace("/", ".").replace(".java", "")
                    # Task: :module:test --tests "org.example.MyTest"
                    gradle_tasks.add(f"{module_path}:test --tests \"{class_name}\"")
                elif "src/yamlRestTest/java/" in f:
                     # REST tests often run via a different task, but usually 'check' covers them.
                     # For simplicity, we trigger the module's test task which usually aggregates.
                     gradle_tasks.add(f"{module_path}:test")
            except IndexError:
                gradle_tasks.add(f"{module_path}:test")

        # If it's a source file, try to guess the test class or run module tests
        elif f.endswith(".java") and "src/main/java/" in f:
             # Heuristic: Run all tests in this module. 
             # Precise mapping (MyClass -> MyClassTests) is hard because naming isn't 100% consistent.
             gradle_tasks.add(f"{module_path}:test")
        
        # If build.gradle changed, run everything in that module
        elif f.endswith("build.gradle"):
             if module_path:
                gradle_tasks.add(f"{module_path}:test")
             else:
                # Root build.gradle changed? This is heavy. Fallback to core tests.
                gradle_tasks.add(":server:test")

    # 3. Output
    if not gradle_tasks:
        print("NONE")
    else:
        # Join all tasks. Gradle can accept multiple tasks/flags in one go.
        print(" ".join(sorted(gradle_tasks)))

if __name__ == "__main__":
    main()
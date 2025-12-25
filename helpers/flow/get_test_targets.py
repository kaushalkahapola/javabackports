#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import json
import re

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to analyze")
    args = parser.parse_args()

    # 1. Get list of changed files with status
    cmd = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", args.commit]
    try:
        output = subprocess.check_output(cmd, cwd=args.repo, text=True)
    except subprocess.CalledProcessError:
        print(json.dumps({"modified": [], "added": []}))
        return

    modified_tests = set()
    added_tests = set()

    lines = output.strip().splitlines()
    
    for line in lines:
        parts = line.split('\t')
        if not parts:
            continue
            
        status = parts[0]
        
        # Handle Renames (R) and Copies (C)
        if status.startswith('R') or status.startswith('C'):
            if len(parts) >= 3:
                filepath = parts[2]
            else:
                continue
        else:
            if len(parts) >= 2:
                filepath = parts[1]
            else:
                continue
        
        # Only process test files
        # Maven standard layout: src/test/java/package/TestClass.java
        if not ("/src/test/java/" in filepath and filepath.endswith(".java")):
            continue
            
        filename = os.path.basename(filepath)
        # Check standard naming conventions
        if not (filename.startswith("Test") or filename.endswith("Test.java") or filename.endswith("Tests.java") or filename.endswith("TestCase.java")):
            continue
            
        class_name = ""
        try:
            # Extract class name. 
            # Path: flow-server/src/test/java/com/vaadin/flow/server/MyTest.java
            # Want: com.vaadin.flow.server.MyTest
            
            rel_path = filepath.split("/src/test/java/")[1]
            class_name = rel_path.replace("/", ".").replace("\\", ".").rsplit(".", 1)[0]
            
        except IndexError:
            continue

        if class_name:
            if status == 'A':
                added_tests.add(class_name)
            else:
                modified_tests.add(class_name)

    # Output as JSON
    # Maven -Dtest accepts comma-separated list of classes
    # But run_tests.py usually joins them with spaces
    # run_tests.sh for flow handles comma-separation if needed, or we can just return list here
    # The run_tests.sh script I wrote does: MVN_CMD="mvn test -Dtest=${TEST_TARGETS} -B"
    # If TEST_TARGETS is "Class1 Class2", then "mvn test -Dtest=Class1 Class2" is WRONG.
    # It should be comma separated.
    # BUT! run_tests.py joins with spaces on line 434: " ".join(modified + added)
    # So run_tests.sh needs to handle space-separated input and convert to comma-separated.
    # Let's check run_tests.sh again.
    # Script says: MVN_CMD="mvn test -Dtest=${TEST_TARGETS} -B"
    # If TEST_TARGETS comes in with spaces, we need to replace spaces with commas in bash script or here.
    # Better to return compatible list here and fix bash script to handle spaces.
    
    result = {
        "modified": sorted(list(modified_tests)),
        "added": sorted(list(added_tests))
    }
    print(json.dumps(result))

if __name__ == "__main__":
    main()

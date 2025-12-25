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

    modified_tests = []
    added_tests = []

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
        
        # Check if it's a Java test file
        if filepath.endswith(".java") and "/src/test/java/" in filepath:
            # Extract fully qualified class name
            # e.g., .../src/test/java/org/apache/hive/MyTest.java -> org.apache.hive.MyTest
            try:
                rel_path = filepath.split("/src/test/java/")[1]
                class_name = rel_path.replace("/", ".").replace(".java", "")
                
                if status == 'A':
                    added_tests.append(class_name)
                else:
                    modified_tests.append(class_name)
            except IndexError:
                # If path doesn't match standard structure, skip or handle differently
                pass

    # Output as JSON
    result = {
        "modified": modified_tests,
        "added": added_tests
    }
    print(json.dumps(result))

if __name__ == "__main__":
    main()

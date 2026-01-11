#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import json

def find_gradle_module(repo, filepath):
    """
    Finds the Gradle module path (e.g. :hibernate-core) for a given file.
    """
    # filepath is relative to repo root (e.g. hibernate-core/src/test/java/...)
    
    # 1. Look for build.gradle in current or parent dirs
    current_dir = os.path.dirname(filepath)
    while current_dir:
        build_gradle = os.path.join(repo, current_dir, "build.gradle")
        build_gradle_kts = os.path.join(repo, current_dir, "build.gradle.kts")
        
        if os.path.exists(build_gradle) or os.path.exists(build_gradle_kts):
            # Convert path to module format (e.g. "hibernate-core" -> ":hibernate-core")
            normalized = current_dir.replace("\\", "/").replace("/", ":")
            return ":" + normalized
            
        parent = os.path.dirname(current_dir)
        if parent == current_dir or not parent:
            break
        current_dir = parent
        
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to analyze")
    args = parser.parse_args()

    # 1. Get list of changed files
    cmd = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", args.commit]
    try:
        output = subprocess.check_output(cmd, cwd=args.repo, text=True)
    except subprocess.CalledProcessError:
        print(json.dumps({"modified": [], "added": []}))
        return

    modified_tests = set()
    added_tests = set()

    for line in output.strip().splitlines():
        parts = line.split('\t')
        if not parts: continue
            
        status = parts[0]
        filepath = parts[1] if len(parts) >= 2 else ""
        if status.startswith('R') or status.startswith('C'):
             if len(parts) >= 3: filepath = parts[2]

        if not filepath: continue
        
        # Only process test files
        # Hibernate tests often start with just a standard name
        is_test_file = (
            "/src/test/" in filepath and 
            filepath.endswith(".java")
        )
        
        if not is_test_file:
            print(f"DEBUG: Skipping non-test file: {filepath}", file=sys.stderr)
            continue
            
        # Find the Gradle module
        module_path = find_gradle_module(args.repo, filepath)
        if not module_path:
            print(f"DEBUG: Could not find module for: {filepath}", file=sys.stderr)
            continue
            
        print(f"DEBUG: Found module {module_path} for {filepath}", file=sys.stderr)

        try:
            # Extract class name
            rel_path = ""
            if "/src/test/java/" in filepath:
                rel_path = filepath.split("/src/test/java/")[1]
            elif "/src/test/kotlin/" in filepath:
                rel_path = filepath.split("/src/test/kotlin/")[1]
            elif "/src/test/groovy/" in filepath:
                rel_path = filepath.split("/src/test/groovy/")[1]
            
            if rel_path:
                class_name = rel_path.replace("/", ".").replace("\\", ".").rsplit(".", 1)[0]
                test_target = f"{module_path}:test --tests \"{class_name}\""
            else:
                test_target = f"{module_path}:test"
        except Exception as e:
             print(f"DEBUG: Error processing {filepath}: {e}", file=sys.stderr)
             test_target = f"{module_path}:test"

        if test_target:
            if status == 'A':
                added_tests.add(test_target)
            else:
                modified_tests.add(test_target)

    result = {
        "modified": sorted(list(modified_tests)),
        "added": sorted(list(added_tests))
    }
    print(json.dumps(result))

if __name__ == "__main__":
    main()

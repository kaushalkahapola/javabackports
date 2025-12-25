#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import json

def find_gradle_module(repo, filepath):
    """
    Finds the Gradle module path (e.g. :solr:core) for a given file.
    """
    current_dir = os.path.dirname(filepath)
    while current_dir:
        build_gradle_path = os.path.join(repo, current_dir, "build.gradle")
        if os.path.exists(build_gradle_path):
            normalized_dir = current_dir.replace("\\", "/")
            return ":" + normalized_dir.replace("/", ":")
        
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent
        
    if os.path.exists(os.path.join(repo, "build.gradle")):
        return ":"
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to analyze")
    args = parser.parse_args()

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
        if not parts: continue
        
        status = parts[0]
        if status.startswith('R') or status.startswith('C'):
            filepath = parts[2] if len(parts) >= 3 else None
        else:
            filepath = parts[1] if len(parts) >= 2 else None
            
        if not filepath: continue

        filename = os.path.basename(filepath)
        is_test_file = (
            "/src/test/" in filepath and 
            (filepath.endswith(".java") or filepath.endswith(".scala")) and
            (filename.startswith("Test") or filename.endswith("Test.java") or filename.endswith("Tests.java"))
        )
        
        if not is_test_file:
            continue
            
        module_path = find_gradle_module(args.repo, filepath)
        if not module_path: continue
        if module_path == ":": module_path = ""
        
        test_target = ""
        try:
            rel_path = ""
            if "/src/test/java/" in filepath:
                rel_path = filepath.split("/src/test/java/")[1]
            elif "/src/test/scala/" in filepath:
                rel_path = filepath.split("/src/test/scala/")[1]
            
            if rel_path:
                class_name = rel_path.replace("/", ".").replace("\\", ".").rsplit(".", 1)[0]
                test_target = f"{module_path}:test --tests \"{class_name}\""
            else:
                test_target = f"{module_path}:test"
        except IndexError:
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

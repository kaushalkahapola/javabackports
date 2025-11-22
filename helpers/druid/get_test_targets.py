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
        # Fallback to core modules if git fails
        print("processing,server,core") 
        return

    changed_files = output.strip().splitlines()
    modules = set()

    # 2. Map Files to Maven Modules
    # Druid structure: [module_name]/src/...
    # We just need to grab the top-level folder name.
    
    for f in changed_files:
        parts = f.split("/")
        if len(parts) > 1:
            module = parts[0]
            
            # Skip the known broken/ignored modules
            if module in ["web-console", "distribution"]:
                continue
            
            # Check if it looks like a maven module (has a pom.xml)
            if os.path.exists(os.path.join(args.repo, module, "pom.xml")):
                modules.add(module)
            
            # Special case: Root pom.xml change -> Run core tests
            elif f == "pom.xml":
                modules.add("processing")
                modules.add("server")

    # 3. Output formatted string
    if not modules:
        print("NONE")
    else:
        # Join unique modules with commas for the -pl flag
        # Example output: processing,server,indexing-service
        print(",".join(sorted(modules)))

if __name__ == "__main__":
    main()
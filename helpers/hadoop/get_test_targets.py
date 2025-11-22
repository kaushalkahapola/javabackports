#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os

# Modules known to be broken/require complex envs that we want to skip
BLACKLIST_MODULES = [
    "hadoop-yarn-project/hadoop-yarn/hadoop-yarn-applications/hadoop-yarn-applications-catalog/hadoop-yarn-applications-catalog-webapp",
    "hadoop-yarn-project/hadoop-yarn/hadoop-yarn-applications/hadoop-yarn-applications-catalog/hadoop-yarn-applications-catalog-docker",
    "hadoop-yarn-project" # Aggregator that often fails if children fail
]

def is_blacklisted(module_path):
    for bad in BLACKLIST_MODULES:
        if module_path.startswith(bad) or bad.startswith(module_path):
             # If exact match or if the module path is a parent of a bad module? 
             # Actually, simpler: just skip if it *is* one of the bad ones.
             if module_path == bad: return True
    return False

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
        # Fallback: test core modules if git fails
        print("hadoop-common-project/hadoop-common,hadoop-hdfs-project/hadoop-hdfs") 
        return

    changed_files = output.strip().splitlines()
    modules = set()

    # 2. Map Files to Maven Modules
    # Hadoop structure is nested. We walk up from the file until we find a pom.xml.
    
    for f in changed_files:
        # 'f' is a relative path like 'hadoop-common-project/hadoop-common/src/main/java/...'
        current_dir = os.path.dirname(f)
        found_module = False
        
        while current_dir:
            pom_path = os.path.join(args.repo, current_dir, "pom.xml")
            if os.path.exists(pom_path):
                # Found the module!
                if not is_blacklisted(current_dir):
                    modules.add(current_dir)
                found_module = True
                break
            
            # Move up one level
            # If current_dir is "a/b", dirname is "a". If "a", dirname is "" (loop ends)
            parent = os.path.dirname(current_dir)
            if parent == current_dir: break # Safety break
            current_dir = parent
        
        if not found_module and f == "pom.xml":
            # Root POM changed? This usually means we should test everything (or at least core)
            modules.add("hadoop-common-project/hadoop-common")
            modules.add("hadoop-hdfs-project/hadoop-hdfs")

    # 3. Output formatted string
    if not modules:
        print("NONE")
    else:
        # Join unique modules with commas for the -pl flag
        print(",".join(sorted(modules)))

if __name__ == "__main__":
    main()
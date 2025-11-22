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
        # Fallback to tier1 if git fails
        print("tier1") 
        return

    changed_files = output.strip().splitlines()
    test_targets = set()

    for f in changed_files:
        f = f.replace("\\", "/")
        
        # --- MAPPING LOGIC FOR JDK 11+ (Modular Layout) ---

        # 1. Hotspot (VM) Changes
        # Path: src/hotspot/...
        if f.startswith("src/hotspot/") or f.startswith("make/hotspot"):
            if "/gc/" in f:
                test_targets.add("hotspot_gc")
            elif "/compiler/" in f:
                test_targets.add("hotspot_compiler")
            elif "/runtime/" in f:
                test_targets.add("hotspot_runtime")
            elif "/serviceability/" in f:
                test_targets.add("hotspot_serviceability")
            else:
                test_targets.add("hotspot_all")
            continue

        # 2. Langtools (Compiler)
        # Path: src/jdk.compiler/... or src/jdk.javadoc/...
        if f.startswith("src/jdk.compiler") or f.startswith("src/jdk.javadoc"):
            test_targets.add("langtools_all")
            continue

        # 3. Java Libraries (The biggest category)
        # Source Path: src/[module]/share/classes/[package]/File.java
        # Target Path: test/jdk/[package]
        
        # Check if it is a source file
        if f.startswith("src/") and "/classes/" in f:
            try:
                # f = src/java.base/share/classes/java/lang/String.java
                # Split at /classes/
                parts = f.split("/classes/")
                if len(parts) > 1:
                    rel_path = parts[1] # java/lang/String.java
                    package_dir = os.path.dirname(rel_path) # java/lang
                    
                    # JDK 11 tests are usually in test/jdk/
                    target = f"test/jdk/{package_dir}"
                    test_targets.add(target)
            except IndexError:
                pass
            continue

        # 4. Test Files Changed
        # Path: test/jdk/... or test/hotspot/...
        if f.startswith("test/jdk/") and f.endswith(".java"):
            test_targets.add(os.path.dirname(f))
        elif f.startswith("test/hotspot/jtreg/"):
            # For hotspot tests, we usually run the whole group because deps are complex,
            # but we can try adding the directory.
            test_targets.add(os.path.dirname(f))
        elif f.startswith("test/langtools/"):
            test_targets.add(os.path.dirname(f))

    # 3. Output
    if not test_targets:
        print("NONE")
    else:
        # Check if targets exist to avoid errors? 
        # JDK 11 make system is robust, but let's be safe.
        # We print them; build system handles the rest.
        print(" ".join(sorted(test_targets)))

if __name__ == "__main__":
    main()
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
        print("jdk_core") # Safe fallback
        return

    changed_files = output.strip().splitlines()
    test_targets = set()

    for f in changed_files:
        f = f.replace("\\", "/")
        
        # --- MAPPING LOGIC BASED ON YOUR MAKEFILES ---
        
        # 1. Langtools (javac, javap, etc.)
        if f.startswith("langtools/"):
            # The Makefile has a 'langtools_all' target
            test_targets.add("langtools_all")
            continue

        # 2. Hotspot (VM)
        if f.startswith("hotspot/"):
            # Based on TEST.groups
            if "gc/" in f:
                test_targets.add("hotspot_gc")
            elif "compiler/" in f:
                test_targets.add("hotspot_compiler")
            elif "runtime/" in f:
                test_targets.add("hotspot_runtime")
            elif "serviceability/" in f:
                test_targets.add("hotspot_serviceability")
            else:
                test_targets.add("hotspot_all")
            continue

        # 3. JDK Core Libraries
        if f.startswith("jdk/"):
            # Based on jdk/test/TEST.groups definitions
            if "java/lang/" in f or "sun/reflect/" in f:
                test_targets.add("jdk_lang")
            elif "java/util/" in f:
                test_targets.add("jdk_util")
            elif "java/math/" in f:
                test_targets.add("jdk_math")
            elif "java/io/" in f:
                test_targets.add("jdk_io")
            elif "java/nio/" in f:
                test_targets.add("jdk_nio")
            elif "java/net/" in f or "sun/net/" in f:
                test_targets.add("jdk_net")
            elif "java/security/" in f or "javax/crypto/" in f:
                test_targets.add("jdk_security")
            elif "java/text/" in f:
                test_targets.add("jdk_text")
            elif "java/rmi/" in f:
                test_targets.add("jdk_rmi")
            else:
                # Fallback for other JDK areas
                test_targets.add("jdk_core")

    # 3. Output formatted string for make
    if not test_targets:
        print("NONE")
    else:
        # Join unique targets with spaces
        # Example: "jdk_lang jdk_util hotspot_gc"
        print(" ".join(sorted(test_targets)))

if __name__ == "__main__":
    main()
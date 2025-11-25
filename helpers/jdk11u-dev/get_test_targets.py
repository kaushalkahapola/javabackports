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
        # For backport analysis, run broader test suites instead of individual tests
        if f.startswith("test/jdk/") and f.endswith(".java"):
            # Map to broader test groups for better comparison
            # Extract the top-level package (e.g., test/jdk/java/lang -> jdk_lang)
            test_path = f.replace("test/jdk/", "")
            parts = test_path.split("/")
            if len(parts) >= 2:
                top_package = parts[0]  # e.g., "java", "javax", "sun"
                second_level = parts[1] if len(parts) > 1 else ""
                
                # Map to standard test groups
                if top_package == "java" and second_level in ["lang", "reflect"]:
                    test_targets.add("jdk_lang")
                elif top_package == "java" and second_level == "util":
                    test_targets.add("jdk_util")
                elif top_package == "java" and second_level == "io":
                    test_targets.add("jdk_io")
                elif top_package == "java" and second_level == "nio":
                    test_targets.add("jdk_nio")
                elif top_package == "java" and second_level == "net":
                    test_targets.add("jdk_net")
                elif top_package == "java" and second_level == "security":
                    test_targets.add("jdk_security")
                elif top_package == "javax":
                    # javax tests - run the top-level package
                    test_targets.add(f"test/jdk/{top_package}/{second_level}")
                else:
                    # For other cases, use the parent directory (broader than single test)
                    parent_dir = os.path.dirname(os.path.dirname(f))
                    if parent_dir and parent_dir != "test/jdk":
                        test_targets.add(parent_dir)
                    else:
                        test_targets.add("jdk_core")
        elif f.startswith("test/hotspot/jtreg/"):
            # For hotspot tests, run relevant test groups
            if "/gc/" in f:
                test_targets.add("hotspot_gc")
            elif "/compiler/" in f:
                test_targets.add("hotspot_compiler")
            elif "/runtime/" in f:
                test_targets.add("hotspot_runtime")
            else:
                test_targets.add("hotspot_all")
        elif f.startswith("test/langtools/"):
            test_targets.add("langtools_all")

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
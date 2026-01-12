#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import json

# Android modules to skip
ANDROID_MODULES = {
    "android",
    "android-interop-testing",
    "cronet",
    "gae-interop-testing",
}

def is_android_module(module_path):
    """Check if module is Android-related."""
    if ":compiler" in module_path or module_path.startswith("compiler"):
        return True
    parts = module_path.split(":")
    for part in parts:
        if part in ANDROID_MODULES:
            return True
    return False

def find_gradle_module(repo, filepath):
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
    return None

def extract_test_class(filepath):
    """Extract fully qualified test class name from file path."""
    if "/java/" not in filepath:
        return None
    
    # Split at /java/ to get the package/class part
    parts = filepath.split("/java/")
    if len(parts) < 2:
        return None
    
    class_path = parts[1]  # e.g. io/grpc/rls/LbPolicyConfigurationTest.java
    if not class_path.endswith(".java"):
        return None
    
    # Convert path to fully qualified class name
    # io/grpc/rls/LbPolicyConfigurationTest.java -> io.grpc.rls.LbPolicyConfigurationTest
    class_name = class_path.replace("/", ".").replace(".java", "")
    return class_name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to analyze")
    args = parser.parse_args()

    cmd = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", args.commit]
    try:
        output = subprocess.check_output(cmd, cwd=args.repo, text=True)
    except subprocess.CalledProcessError:
        print(json.dumps({"modified": [], "added": [], "skip": False}))
        return

    modified = []
    added = []
    has_android_files = False
    
    for line in output.strip().splitlines():
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        status, f = parts
        
        # Check if file is in Android modules
        if any(android_mod in f for android_mod in ["android/", "cronet/", "gae-interop-testing/"]):
            has_android_files = True
        
        if not f.endswith(".java"):
            continue
        if "src/test" not in f:
            continue
        
        gradle_module = find_gradle_module(args.repo, f)
        if gradle_module and not is_android_module(gradle_module):
            test_class = extract_test_class(f)
            if test_class:
                # Add grpc- prefix to module names
                gradle_module_with_prefix = gradle_module.replace(":", ":grpc-") if gradle_module.startswith(":") else f"grpc-{gradle_module}"
                # Create Gradle test target with specific class
                test_target = f"{gradle_module_with_prefix}:test --tests {test_class}"
                if status == "A":
                    added.append(test_target)
                else:
                    modified.append(test_target)

    # If commit involves Android files, skip entire commit
    if has_android_files:
        result = {"modified": [], "added": [], "skip": True, "reason": "Android files involved"}
    else:
        result = {"modified": sorted(set(modified)), "added": sorted(set(added)), "skip": False}
    print(json.dumps(result))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
from datetime import datetime

# --- 1. PROJECT CONFIGURATION ---
PROJECT_CONFIG = {
    "elasticsearch": {
        "repo_name": "elasticsearch",
        "build_system": "self-building",
        "builder_tag": "es-builder:latest"
    },
    "kafka": {
        "repo_name": "kafka",
        "build_system": "gradle",
        "builder_tag": "kafka-builder:latest"
    },
    "hadoop": {
        "repo_name": "hadoop",
        "build_system": "maven",
        "builder_tag": "hadoop-builder:latest"
    },
    "druid": {
        "repo_name": "druid",
        "build_system": "maven",
        "builder_tag": "druid-builder:latest"
    },
    "jdk8u-dev": {
        "repo_name": "jdk8u-dev",
        "build_system": "make",
        "builder_tag": "jdk8-builder:latest",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk11u-dev": {
        "repo_name": "jdk11u-dev",
        "build_system": "make",
        "builder_tag": "jdk11-builder:latest",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk17u-dev": {
        "repo_name": "jdk17u-dev",
        "build_system": "make",
        "builder_tag": "jdk17-builder:latest",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk21u-dev": {
        "repo_name": "jdk21u-dev",
        "build_system": "make",
        "builder_tag": "jdk21-builder:latest",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    }
}
# --- END CONFIGURATION ---

def run_command(command, env=None, capture_output=False, check=True, cwd=None):
    print(f"--- Running: {command} ---", flush=True)
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(command, shell=True, check=check, env=process_env,
                          capture_output=capture_output, text=True, cwd=cwd)

def get_smart_test_targets(toolkit_dir, project_dir, commit_sha, project_name):
    """Calls the project-specific python script to calculate test targets."""
    resolver_script = os.path.join(toolkit_dir, "helpers", project_name, "get_test_targets.py")
    
    if not os.path.exists(resolver_script):
        print(f"--- ⚠️ No smart test resolver found at {resolver_script}. Defaulting to ALL. ---")
        return "ALL"

    print(f"--- Calculating smart test targets... ---")
    try:
        result = run_command(
            f"python3 {resolver_script} --repo {project_dir} --commit {commit_sha}",
            capture_output=True,
            check=True
        )
        targets = result.stdout.strip()
        if not targets or targets == "NONE":
            print("--- No relevant tests found for this commit. ---")
            return "NONE"
        return targets
    except Exception as e:
        print(f"--- ❌ Error calculating test targets: {e}. Fallback to ALL. ---")
        return "ALL"

def run_tests(config, toolkit_dir, project_dir, commit_sha, build_type, results_dir, test_strategy):
    """Orchestrates the testing process."""
    print(f"\n{'='*80}")
    print(f"--- Starting Tests ({test_strategy.upper()}) for {config['repo_name']} ({build_type}) ---")
    print(f"{'='*80}")

    test_targets = "ALL"
    if test_strategy == "smart":
        test_targets = get_smart_test_targets(toolkit_dir, project_dir, commit_sha, config['repo_name'])
    
    if test_targets == "NONE":
        return "Skipped (No relevant tests)"

    print(f"--- Test Targets: {test_targets} ---")

    test_env = os.environ.copy()
    # This points to helpers/jdk8u-dev/ etc.
    project_helper_dir = os.path.join(toolkit_dir, "helpers", config['repo_name'])
    
    test_env.update({
        "COMMIT_SHA": commit_sha,
        "PROJECT_DIR": project_dir,
        "TEST_TARGETS": test_targets,
        "BUILDER_IMAGE_TAG": config['builder_tag'],
        "TOOLKIT_DIR": project_helper_dir  # <--- THIS WAS MISSING
    })
    
    # Add build-system specific env vars
    if config['build_system'] == 'make':
        test_env["BOOT_JDK"] = config['boot_jdk']
        test_env["JTREG_HOME"] = config['jtreg_home']
        test_env["BUILD_DIR_NAME"] = f"build_output_{commit_sha[:7]}_{build_type}"

    run_tests_script = os.path.join(project_helper_dir, "run_tests.sh")
    if not os.path.exists(run_tests_script):
        print(f"--- ❌ Error: {run_tests_script} not found. ---")
        return "Fail (Missing Script)"

    start_time = datetime.now()
    try:
        run_command(f"bash {run_tests_script}", env=test_env, check=True, cwd=toolkit_dir)
        status = "Success"
    except subprocess.CalledProcessError:
        status = "Fail (Tests Failed)"
    except Exception as e:
        status = f"Fail (Error: {e})"
    
    duration = (datetime.now() - start_time).total_seconds()
    print(f"--- Test run finished: {status} ({duration:.2f}s) ---")
    return status

def build_single_commit(config, toolkit_dir, project_dir, commit_sha, build_type, results_dir):
    """Builds a single commit (fixed or buggy)."""
    short_sha = commit_sha[:7]
    print(f"\n{'='*80}")
    print(f"--- Starting {build_type.upper()} build for {config['repo_name']} @ {short_sha} ---")
    print(f"{'='*80}")
    
    status_file = os.path.join(results_dir, f"{build_type}_build_status.txt")
    project_helper_dir = os.path.join(toolkit_dir, "helpers", config['repo_name'])

    build_env = os.environ.copy()
    build_env.update({
        "COMMIT_SHA": commit_sha,
        "BUILDER_IMAGE_TAG": config['builder_tag'],
        "BUILD_STATUS_FILE": status_file,
        "PROJECT_DIR": project_dir,
        "TOOLKIT_DIR": project_helper_dir,
    })

    if config['build_system'] == 'make':
        build_env["BUILD_DIR_NAME"] = f"build_output_{short_sha}_{build_type}"
        build_env["BOOT_JDK"] = config['boot_jdk']
        build_env["JTREG_HOME"] = config['jtreg_home']
    elif config['build_system'] == 'self-building':
        build_env["IMAGE_TAG"] = f"{config['repo_name']}-{build_type}-{short_sha}"
        build_env["BUILD_DIR"] = os.path.join(results_dir, f"{build_type}_run", "build_output")
        os.makedirs(build_env["BUILD_DIR"], exist_ok=True)
    elif config['build_system'] in ['gradle', 'maven']:
        build_env["IMAGE_TAG_TO_BUILD"] = f"{config['repo_name']}-{build_type}-{short_sha}"

    build_status = "Fail (Script Error)"
    start_time = datetime.now()
    
    try:
        run_command(f"bash {project_helper_dir}/run_build.sh", env=build_env, check=True, cwd=toolkit_dir)
        try:
            with open(status_file, 'r') as f:
                build_status = f.read().strip()
        except FileNotFoundError:
            build_status = "Fail (Status file not found)"
    except Exception as e:
        print(f"--- ❌ BUILD ERROR: {e} ---")
        build_status = "Fail (Error)"
    
    end_time = datetime.now()
    build_time = (end_time - start_time).total_seconds()
    print(f"--- Build complete: {build_status} ({build_time:.2f}s) ---")
    return build_status, build_time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--project", required=True, choices=PROJECT_CONFIG.keys())
    parser.add_argument("-c", "--commit", required=True)
    parser.add_argument("-b", "--build-before", action="store_true", help="Also build the parent commit")
    
    # --- TEST ARGUMENTS ---
    parser.add_argument("--run-tests", action="store_true", help="Enable testing after build")
    parser.add_argument("--test-target", choices=['fixed', 'buggy', 'both'], default='fixed', 
                        help="Which commit to test (default: fixed)")
    parser.add_argument("--test-strategy", choices=['smart', 'all'], default='smart',
                        help="smart: affected modules only (default), all: full suite")
    
    args = parser.parse_args()

    TOOLKIT_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_NAME = args.project
    COMMIT_SHA = args.commit
    config = PROJECT_CONFIG[PROJECT_NAME]
    PROJECT_DIR = os.path.abspath(os.path.join(TOOLKIT_DIR, "..", config['repo_name']))
    RESULTS_DIR = os.path.join(TOOLKIT_DIR, "build_results", PROJECT_NAME, COMMIT_SHA[:7])
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    final_report_path = os.path.join(RESULTS_DIR, "final_build_report.txt")

    # Checks (skipped for brevity, same as before)
    if not os.path.isdir(PROJECT_DIR):
        print(f"FATAL: Repo not found at {PROJECT_DIR}")
        sys.exit(1)

    # Build Builder Image
    if config['build_system'] != 'self-building':
        dockerfile = os.path.join(TOOLKIT_DIR, "helpers", PROJECT_NAME, "Dockerfile")
        run_command(f"docker build -t {config['builder_tag']} -f {dockerfile} {os.path.dirname(dockerfile)}")

    # --- 1. Build & Test AFTER ---
    after_status, after_time = build_single_commit(config, TOOLKIT_DIR, PROJECT_DIR, COMMIT_SHA, "fixed", RESULTS_DIR)
    after_test_status = "Skipped"
    
    # Logic: Run tests if --run-tests IS SET AND target is 'fixed' or 'both'
    if after_status == "Success" and args.run_tests and args.test_target in ['fixed', 'both']:
        after_test_status = run_tests(config, TOOLKIT_DIR, PROJECT_DIR, COMMIT_SHA, "fixed", RESULTS_DIR, args.test_strategy)

    # --- 2. Build & Test BEFORE ---
    before_status = "Skipped"
    before_test_status = "Skipped"
    
    if args.build_before:
        # Only attempt before build if after build succeeded (save time)
        if after_status == "Success":
            parent_commit = run_command(f"git rev-parse {COMMIT_SHA}^", capture_output=True, cwd=PROJECT_DIR).stdout.strip()
            before_status, before_time = build_single_commit(config, TOOLKIT_DIR, PROJECT_DIR, parent_commit, "buggy", RESULTS_DIR)
            
            # Logic: Run tests if --run-tests IS SET AND target is 'buggy' or 'both'
            if before_status == "Success" and args.run_tests and args.test_target in ['buggy', 'both']:
                before_test_status = run_tests(config, TOOLKIT_DIR, PROJECT_DIR, parent_commit, "buggy", RESULTS_DIR, args.test_strategy)
        else:
            print("--- Skipping Before build because After build failed. ---")
            before_status = "Skipped (After Failed)"

    # --- Cleanup ---
    print("\n--- Cleaning up... ---")
    run_command(f"sudo rm -rf {PROJECT_DIR}/build_output_*", check=False, capture_output=True)
    run_command("docker builder prune -a -f", check=False, capture_output=True)

    # --- Report ---
    print("\n" + "="*80)
    print(f"REPORT: {PROJECT_NAME} {COMMIT_SHA}")
    print(f"After:  Build={after_status}, Test={after_test_status}")
    print(f"Before: Build={before_status}, Test={before_test_status}")
    print("="*80)
    
    # Save report
    with open(final_report_path, "w") as f:
        f.write(f"Project: {PROJECT_NAME}\nCommit: {COMMIT_SHA}\n")
        f.write(f"After Build: {after_status}\nAfter Test: {after_test_status}\n")
        f.write(f"Before Build: {before_status}\nBefore Test: {before_test_status}\n")

if __name__ == "__main__":
    main()
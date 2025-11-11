#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
from datetime import datetime

# --- 1. PROJECT CONFIGURATION ---
# This dictionary maps project names to their specific build settings.
# This is the "brain" that knows how to build each project.
PROJECT_CONFIG = {
    "elasticsearch": {
        "repo_name": "elasticsearch",
        "build_system": "self-building", # Special case
        "builder_tag": "es-builder:latest" # Not pre-built, but used for naming
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
        "boot_jdk": "/opt/java/openjdk", # Path inside container
        "jtreg_home": "/opt/jtreg"       # Path inside container
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
    """Runs a shell command."""
    print(f"--- Running: {command} ---", flush=True)
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(command, shell=True, check=check, env=process_env,
                          capture_output=capture_output, text=True, cwd=cwd)

def build_single_commit(config, toolkit_dir, project_dir, commit_sha, build_type, results_dir):
    """
    Builds a single commit (fixed or buggy) using its dedicated run_build.sh.
    """
    short_sha = commit_sha[:7]
    print(f"\n{'='*80}")
    print(f"--- Starting {build_type.upper()} build for {config['repo_name']} @ {short_sha} ---")
    print(f"{'='*80}")
    
    status_file = os.path.join(results_dir, f"{build_type}_build_status.txt")
    builder_image_tag = config['builder_tag']
    project_helper_dir = os.path.join(toolkit_dir, "helpers", config['repo_name'])

    # --- 1. Set up Base Environment Variables ---
    build_env = os.environ.copy()
    build_env.update({
        "COMMIT_SHA": commit_sha,
        "BUILDER_IMAGE_TAG": builder_image_tag,
        "BUILD_STATUS_FILE": status_file,
        "PROJECT_DIR": project_dir,
        "TOOLKIT_DIR": project_helper_dir, # Pass the helper dir as TOOLKIT_DIR
    })

    # --- 2. Add build-system-specific variables ---
    if config['build_system'] == 'make': # For JDKs
        build_env["BUILD_DIR_NAME"] = f"build_output_{short_sha}_{build_type}"
        build_env["BOOT_JDK"] = config['boot_jdk']
        build_env["JTREG_HOME"] = config['jtreg_home']
    
    elif config['build_system'] == 'self-building': # For elasticsearch
        build_env["IMAGE_TAG"] = f"{config['repo_name']}-{build_type}-{short_sha}"
        build_env["BUILD_DIR"] = os.path.join(results_dir, f"{build_type}_run", "build_output")
        os.makedirs(build_env["BUILD_DIR"], exist_ok=True)
    
    # Note: Kafka, Hadoop, Druid (gradle/maven) don't need extra env vars
    # because run_build.sh handles them.

    build_status = "Fail (Script Error)"
    start_time = datetime.now()
    
    try:
        # Run the build
        run_command(f"bash {project_helper_dir}/run_build.sh", env=build_env, check=True, cwd=toolkit_dir)
        
        # Read the status file
        try:
            with open(status_file, 'r') as f:
                build_status = f.read().strip()
        except FileNotFoundError:
            build_status = "Fail (Status file not found)"
            
    except subprocess.CalledProcessError as e:
        print(f"--- ❌ BUILD SCRIPT FAILED for {short_sha} ---")
        build_status = "Fail (Build Script Error)"
    except Exception as e:
        print(f"--- ❌ UNEXPECTED ERROR for {short_sha}: {e} ---")
        build_status = f"Fail (Orchestrator Error: {e})"
    
    end_time = datetime.now()
    build_time = (end_time - start_time).total_seconds()
    
    print(f"--- Build {build_type} for {short_sha} complete. Status: {build_status} (Time: {build_time:.2f}s) ---")
    return build_status, build_time

def main():
    # 1. Setup Argument Parser
    parser = argparse.ArgumentParser(description="Build 'before' and 'after' versions of a project commit.")
    parser.add_argument("-p", "--project", required=True, choices=PROJECT_CONFIG.keys(),
                        help=f"The project to build (e.g., {', '.join(PROJECT_CONFIG.keys())})")
    parser.add_argument("-c", "--commit", required=True,
                        help="The 'after' (fixed) commit hash.")
    parser.add_argument("-b", "--build-before", action="store_true",
                        help="Also build the 'before' (parent) commit.")
    args = parser.parse_args()

    # 2. Define Paths and Config
    TOOLKIT_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_NAME = args.project
    COMMIT_SHA = args.commit
    config = PROJECT_CONFIG[PROJECT_NAME]
    
    PROJECT_DIR = os.path.abspath(os.path.join(TOOLKIT_DIR, "..", config['repo_name']))
    
    # Create a local results directory
    RESULTS_DIR = os.path.join(TOOLKIT_DIR, "build_results", PROJECT_NAME, COMMIT_SHA[:7])
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    final_report_path = os.path.join(RESULTS_DIR, "final_build_report.txt")
    
    print(f"--- Starting Build Job for: {PROJECT_NAME} ---")
    print(f"--- Project Repo Path: {PROJECT_DIR} ---")
    print(f"--- Results will be in: {RESULTS_DIR} ---")

    # 3. Check for Project Repo
    if not os.path.isdir(PROJECT_DIR):
        print(f"\n--- ❌ ERROR: Project directory not found at {PROJECT_DIR}")
        print(f"--- Please clone '{config['repo_name']}' into the parent folder (next to this repo).")
        sys.exit(1)

    # 4. Build the Builder Image (if not self-building)
    builder_tag = config['builder_tag']
    dockerfile_path = os.path.join(TOOLKIT_DIR, "helpers", PROJECT_NAME, "Dockerfile")
    
    if config['build_system'] != 'self-building':
        print(f"\n--- Building builder image '{builder_tag}'... ---")
        try:
            run_command(f"docker build -t {builder_tag} -f {dockerfile_path} {os.path.dirname(dockerfile_path)}")
            print("--- Builder image is ready. ---")
        except Exception as e:
            print(f"--- ❌ ERROR: Failed to build Dockerfile at {dockerfile_path}")
            print(e)
            sys.exit(1)
    else:
        print(f"\n--- Skipping builder image (project '{PROJECT_NAME}' builds its own). ---")

    # 5. Run the "After" Build
    after_status, after_time = build_single_commit(
        config, TOOLKIT_DIR, PROJECT_DIR, COMMIT_SHA, "fixed", RESULTS_DIR
    )
    
    before_status = "Skipped"
    before_time = 0
    parent_commit = "" # For cleanup

    # 6. Run the "Before" Build (if requested)
    if args.build_before:
        try:
            parent_commit = run_command(
                f"git rev-parse {COMMIT_SHA}^", 
                capture_output=True, 
                cwd=PROJECT_DIR
            ).stdout.strip()
            
            if not parent_commit:
                print(f"--- ❌ ERROR: Could not find parent commit for {COMMIT_SHA} ---")
                before_status = "Fail (No Parent)"
            else:
                before_status, before_time = build_single_commit(
                    config, TOOLKIT_DIR, PROJECT_DIR, parent_commit, "buggy", RESULTS_DIR
                )
        except Exception as e:
            print(f"--- ❌ ERROR: Failed to get parent commit: {e} ---")
            before_status = "Fail (Error)"

    # 7. Final Cleanup
    print("\n--- Cleaning up build environment... ---")
    
    # Clean up build artifacts from repo
    run_command(f"sudo rm -rf {PROJECT_DIR}/build_output_*", check=False, capture_output=True)
    
    # Clean up Docker images
    if config['build_system'] == 'self-building':
        # For elasticsearch, rmi the images it just built
        after_tag = f"{config['repo_name']}-{build_type}-{COMMIT_SHA[:7]}"
        before_tag = ""
        if before_status != "Skipped" and parent_commit:
             before_tag = f"{config['repo_name']}-{build_type}-{parent_commit[:7]}"
        run_command(f"docker rmi -f {after_tag} {before_tag}", check=False, capture_output=True)
    else:
        # For all other projects, rmi the builder image
        run_command(f"docker rmi -f {builder_tag}", check=False, capture_output=True)

    run_command("docker builder prune -a -f", check=False, capture_output=True)
    
    # 8. Write Final Report
    print("\n" + "="*80)
    print("--- ✅ BUILD COMPLETE: FINAL REPORT ---")
    print("="*80)
    
    report_content = (
        f"Project:         {PROJECT_NAME}\n"
        f"Commit (After):  {COMMIT_SHA}\n"
        f"Parent (Before): {parent_commit if parent_commit else 'N/A'}\n"
        f"----------------------------------\n"
        f"Status (After):  {after_status}\n"
        f"Build Time:      {after_time:.2f}s\n"
        f"----------------------------------\n"
        f"Status (Before): {before_status}\n"
        f"Build Time:      {before_time:.2f}s\n"
        f"----------------------------------\n"
        f"Results saved locally in:\n{RESULTS_DIR}\n"
    )
    
    with open(final_report_path, "w") as f:
        f.write(report_content)
        
    print(report_content)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import pandas as pd
import json
import glob
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil

# --- CONFIGURATION ---
# Maps project names to their specific settings
PROJECT_CONFIG = {
    "elasticsearch": {
        "repo_dir": "elasticsearch",
        "report_pattern": "build/test-results/**/*.xml", # Gradle
        "builder_tag": "es-builder:latest",
        "build_system": "self-building"
    },
    "kafka": {
        "repo_dir": "kafka",
        "report_pattern": "**/build/test-results/**/*.xml", # Gradle multi-module
        "builder_tag": "kafka-builder:latest",
        "build_system": "gradle"
    },
    "hadoop": {
        "repo_dir": "hadoop",
        "report_pattern": "**/target/surefire-reports/*.xml", # Maven multi-module
        "builder_tag": "hadoop-builder:latest",
        "build_system": "maven"
    },
    "druid": {
        "repo_dir": "druid",
        "report_pattern": "**/target/surefire-reports/*.xml", # Maven
        "builder_tag": "druid-builder:latest",
        "build_system": "maven"
    },
    "jdk8u-dev": {
        "repo_dir": "jdk8u-dev",
        "report_pattern": "**/JTwork/**/*.xml", 
        "builder_tag": "jdk8-builder:latest",
        "build_system": "make",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk11u-dev": {
        "repo_dir": "jdk11u-dev",
        "report_pattern": "**/JTwork/**/*.xml",
        "builder_tag": "jdk11-builder:latest",
        "build_system": "make",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk17u-dev": {
        "repo_dir": "jdk17u-dev",
        "report_pattern": "**/JTwork/**/*.xml",
        "builder_tag": "jdk17-builder:latest",
        "build_system": "make",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    },
    "jdk21u-dev": {
        "repo_dir": "jdk21u-dev",
        "report_pattern": "**/JTwork/**/*.xml",
        "builder_tag": "jdk21-builder:latest",
        "build_system": "make",
        "boot_jdk": "/opt/java/openjdk",
        "jtreg_home": "/opt/jtreg"
    }
}

# --- FIX 1: Allow **kwargs to support capture_output ---
def run_command(command, env=None, check=True, cwd=None, **kwargs):
    """Runs a shell command and prints output."""
    # Only print command if we are not capturing output (to keep logs clean)
    if not kwargs.get("capture_output"):
        print(f"CMD: {command}", flush=True)
    
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    
    # We use shell=True to easily handle complex bash strings
    return subprocess.run(command, shell=True, check=check, env=process_env, cwd=cwd, **kwargs)

def parse_test_results(results_dir):
    """
    Scans the results directory for XML files and parses them.
    Returns: (set(passed_tests), set(failed_tests))
    """
    passed = set()
    failed = set()
    
    # Recursive glob to find all XMLs in the temp folder
    xml_files = glob.glob(os.path.join(results_dir, "**/*.xml"), recursive=True)
    
    print(f"--- Parsing {len(xml_files)} test report files in {results_dir} ---")

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Handle standard JUnit XML format
            for testcase in root.iter('testcase'):
                classname = testcase.get('classname', 'UnknownClass')
                name = testcase.get('name', 'UnknownTest')
                full_name = f"{classname}.{name}"
                
                if testcase.find('failure') is not None or testcase.find('error') is not None:
                    failed.add(full_name)
                else:
                    if testcase.find('skipped') is None:
                        passed.add(full_name)
                        
        except Exception as e:
            print(f"⚠️ Error parsing {xml_file}: {e}")
            
    return passed, failed

def get_smart_test_targets(toolkit_dir, project_dir, commit_sha, project_name):
    """Calls the project-specific python script to calculate test targets."""
    resolver_script = os.path.join(toolkit_dir, "helpers", project_name, "get_test_targets.py")
    
    if not os.path.exists(resolver_script):
        return "ALL"

    try:
        result = subprocess.run(
            f"python3 {resolver_script} --repo {project_dir} --commit {commit_sha}",
            shell=True, capture_output=True, text=True, check=True
        )
        targets = result.stdout.strip()
        return targets if targets else "NONE"
    except:
        return "ALL"

def collect_test_reports(project_name, project_repo_dir, dest_dir):
    """
    Copies test reports from the project repo to our temp analysis folder.
    """
    pattern = PROJECT_CONFIG[project_name]["report_pattern"]
    # Use glob inside the repo dir
    search_path = os.path.join(project_repo_dir, pattern)
    found_files = glob.glob(search_path, recursive=True)
    
    print(f"--- Collecting {len(found_files)} report files from {pattern} ---")
    
    for f in found_files:
        try:
            # Create a unique filename to avoid overwrites if multiple modules have same filename
            # e.g. repo/moduleA/TEST-x.xml -> dest/moduleA_TEST-x.xml
            rel_path = os.path.relpath(f, project_repo_dir).replace("/", "_")
            shutil.copy2(f, os.path.join(dest_dir, rel_path))
        except Exception as e:
            print(f"Warning: Failed to copy {f}: {e}")

def execute_lifecycle(project_name, commit_sha, state, toolkit_dir, project_repo_dir, work_dir):
    """
    Runs Build -> Test -> Parse for a specific state ('fixed' or 'buggy').
    Returns: dict with build_status, test_status, passed_tests, failed_tests
    """
    print(f"\n>>> Processing {state.upper()} state for {commit_sha}...")
    
    config = PROJECT_CONFIG[project_name]
    
    # 1. Define Paths
    state_dir = os.path.join(work_dir, state)
    build_output_dir = os.path.join(state_dir, "build_out")
    test_output_dir = os.path.join(state_dir, "test_out")
    status_file = os.path.join(state_dir, "build_status.txt")
    
    os.makedirs(build_output_dir, exist_ok=True)
    os.makedirs(test_output_dir, exist_ok=True)

    # 2. Prepare Env
    env = {
        "COMMIT_SHA": commit_sha,
        "PROJECT_DIR": project_repo_dir,
        "TOOLKIT_DIR": os.path.join(toolkit_dir, "helpers", project_name),
        "BUILDER_IMAGE_TAG": config['builder_tag'],
        "BUILD_STATUS_FILE": status_file,
        "BUILD_DIR_NAME": f"build_{commit_sha[:7]}_{state}" 
    }
    
    # Add JDK specific envs
    if config['build_system'] == 'make':
        env["BOOT_JDK"] = config['boot_jdk']
        env["JTREG_HOME"] = config['jtreg_home']
    elif config['build_system'] == 'self-building':
        env["IMAGE_TAG"] = f"{project_name}-{state}-{commit_sha[:7]}"
        env["BUILD_DIR"] = build_output_dir
    elif config['build_system'] in ['gradle', 'maven']:
         env["IMAGE_TAG_TO_BUILD"] = f"{project_name}-{state}-{commit_sha[:7]}"

    # 3. Run Build
    build_script = os.path.join(toolkit_dir, "helpers", project_name, "run_build.sh")
    try:
        run_command(f"bash {build_script}", env=env, check=True)
        with open(status_file, 'r') as f:
            build_status = f.read().strip()
    except:
        build_status = "Fail"

    if build_status != "Success":
        return {"build": "Fail", "test": "Skipped", "passed": set(), "failed": set()}

    # 4. Smart Test Filtering
    test_targets = get_smart_test_targets(toolkit_dir, project_repo_dir, commit_sha, project_name)
    if test_targets == "NONE":
         return {"build": "Success", "test": "Skipped (No Targets)", "passed": set(), "failed": set()}

    # 5. Run Tests
    env["TEST_TARGETS"] = test_targets
    env["TEST_REPORT_DIR"] = test_output_dir 
    if config['build_system'] == 'self-building':
        env["BUILD_TYPE"] = state

    test_script = os.path.join(toolkit_dir, "helpers", project_name, "run_tests.sh")
    try:
        proc = run_command(f"bash {test_script}", env=env, check=False)
        test_status = "Success" if proc.returncode == 0 else "Fail"
    except:
        test_status = "Error"

    # --- FIX 2: COPY RESULTS ---
    # Explicitly copy XMLs from repo to our temp directory before parsing
    collect_test_reports(project_name, project_repo_dir, test_output_dir)

    # 6. Parse Results
    passed, failed = parse_test_results(test_output_dir)
    
    if test_status == "Fail" and len(failed) == 0:
        test_status = "Crash/Timeout"

    return {
        "build": build_status, 
        "test": test_status, 
        "passed": passed, 
        "failed": failed
    }

def main():
    parser = argparse.ArgumentParser(description="Run Before/After tests for backports.")
    parser.add_argument("--project", required=True, help="Project name (e.g., kafka)")
    parser.add_argument("--start-index", type=int, default=0, help="Start row index")
    parser.add_argument("--end-index", type=int, default=None, help="End row index")
    args = parser.parse_args()

    project_name = args.project
    if project_name not in PROJECT_CONFIG:
        print(f"Unknown project: {project_name}")
        sys.exit(1)

    # Setup Paths
    toolkit_dir = os.getcwd()
    dataset_path = os.path.join(toolkit_dir, "dataset", f"{project_name}.csv")
    project_repo_dir = os.path.abspath(os.path.join(toolkit_dir, "..", PROJECT_CONFIG[project_name]["repo_dir"]))
    
    results_csv = os.path.join(toolkit_dir, f"results_{project_name}.csv")
    results_json = os.path.join(toolkit_dir, f"results_{project_name}.json")

    # Load Dataset
    df = pd.read_csv(dataset_path)
    total_rows = len(df)
    end_index = args.end_index if args.end_index is not None else total_rows
    
    print(f"--- Processing {project_name} rows {args.start_index} to {end_index} ---")

    # Load existing results to skip
    existing_commits = set()
    full_results_data = []
    
    if os.path.exists(results_json):
        try:
            with open(results_json, 'r') as f:
                full_results_data = json.load(f)
                existing_commits = {item['commit'] for item in full_results_data}
                print(f"--- Loaded {len(existing_commits)} existing results. ---")
        except:
            print("--- Could not read existing JSON, starting fresh list. ---")

    # Build the Builder Image Once
    builder_tag = PROJECT_CONFIG[project_name]['builder_tag']
    if PROJECT_CONFIG[project_name]['build_system'] != 'self-building':
        print("--- Building Base Docker Image... ---")
        dockerfile = os.path.join(toolkit_dir, "helpers", project_name, "Dockerfile")
        run_command(f"docker build -t {builder_tag} -f {dockerfile} {os.path.dirname(dockerfile)}")

    # Iterate
    for idx in range(args.start_index, end_index):
        row = df.iloc[idx]
        commit_sha = row['Backport Commit'] 
        
        print(f"\n\n=== [{idx}/{total_rows}] Processing {commit_sha} ===")

        if commit_sha in existing_commits:
            print(f"--- Skipping {commit_sha} (Already processed) ---")
            continue

        try:
            res = subprocess.run(f"git rev-parse {commit_sha}^", shell=True, cwd=project_repo_dir, capture_output=True, text=True)
            parent_sha = res.stdout.strip()
        except:
            print("Error finding parent commit.")
            continue

        # Create temp work dir
        work_dir = os.path.join(toolkit_dir, "temp_work", commit_sha)
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir)

        # --- EXECUTE AFTER (Fixed) ---
        after_res = execute_lifecycle(project_name, commit_sha, "fixed", toolkit_dir, project_repo_dir, work_dir)
        
        # --- EXECUTE BEFORE (Buggy) ---
        if after_res["build"] == "Success":
            before_res = execute_lifecycle(project_name, parent_sha, "buggy", toolkit_dir, project_repo_dir, work_dir)
        else:
            before_res = {"build": "Skipped", "test": "Skipped", "passed": set(), "failed": set()}

        # --- ANALYZE RESULTS ---
        regressions = list(before_res["passed"].intersection(after_res["failed"]))
        fixes = list(before_res["failed"].intersection(after_res["passed"]))
        persistent = list(before_res["failed"].intersection(after_res["failed"]))

        result_entry = {
            "index": idx,
            "commit": commit_sha,
            "parent": parent_sha,
            "build_status_after": after_res["build"],
            "test_status_after": after_res["test"],
            "build_status_before": before_res["build"],
            "test_status_before": before_res["test"],
            "stats": {
                "after_pass_count": len(after_res["passed"]),
                "after_fail_count": len(after_res["failed"]),
                "before_pass_count": len(before_res["passed"]),
                "before_fail_count": len(before_res["failed"]),
                "regression_count": len(regressions),
                "fix_count": len(fixes)
            },
            "details": {
                "regressions": regressions,
                "fixes": fixes,
                "persistent_failures": persistent,
                "all_failures_after": list(after_res["failed"]),
                "all_failures_before": list(before_res["failed"])
            }
        }

        full_results_data.append(result_entry)

        # --- SAVE RESULTS (Incremental) ---
        with open(results_json, 'w') as f:
            json.dump(full_results_data, f, indent=2)
        
        csv_row = {
            "commit": commit_sha,
            "build_after": after_res["build"],
            "test_after": after_res["test"],
            "build_before": before_res["build"],
            "test_before": before_res["test"],
            "regressions": len(regressions),
            "fixes": len(fixes)
        }
        
        csv_df = pd.DataFrame([csv_row])
        if not os.path.exists(results_csv):
            csv_df.to_csv(results_csv, index=False)
        else:
            csv_df.to_csv(results_csv, mode='a', header=False, index=False)

        print(f"--- Results saved for {commit_sha} ---")
        
        # --- CLEANUP ---
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        
        run_command("docker builder prune -a -f", check=False, capture_output=True)
        if project_name == "elasticsearch":
             run_command(f"docker rmi -f elasticsearch-fixed-{commit_sha[:7]} elasticsearch-buggy-{parent_sha[:7]}", check=False, capture_output=True)

    print("\n=== EXPERIMENT RUN COMPLETE ===")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import pandas as pd
import json
import glob
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import shutil

# --- CONFIGURATION ---
PROJECT_CONFIG = {
    "elasticsearch": {
        "repo_dir": "elasticsearch",
        "report_pattern": "build/test-results/**/*.xml",
        "builder_tag": "es-builder:latest",
        "build_system": "self-building"
    },
    "kafka": {
        "repo_dir": "kafka",
        "report_pattern": "**/build/test-results/**/*.xml",
        "builder_tag": "kafka-builder:latest",
        "build_system": "gradle"
    },
    "hadoop": {
        "repo_dir": "hadoop",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "hadoop-builder:latest",
        "build_system": "maven"
    },
    "druid": {
        "repo_dir": "druid",
        "report_pattern": "**/target/surefire-reports/*.xml",
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

def run_command(command, env=None, check=True, cwd=None, **kwargs):
    """Runs a shell command."""
    if not kwargs.get("capture_output"):
        print(f"CMD: {command}", flush=True)
    
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    
    return subprocess.run(command, shell=True, check=check, env=process_env, cwd=cwd, **kwargs)

def parse_console_output(console_text):
    """Parses raw console text for JDK test results when XMLs are missing."""
    passed = set()
    failed = set()
    
    # Extract Failures
    fail_matches = re.findall(r"^FAILED:\s+(.+)$", console_text, re.MULTILINE)
    for f in fail_matches:
        test_name = f.replace("/", ".").replace(".java", "")
        failed.add(test_name)

    # Extract Passed (Approximation from summary if available)
    # Pattern: Passed: java/lang/String/StringTest.java
    pass_matches = re.findall(r"^Passed:\s+(.+)$", console_text, re.MULTILINE)
    for p in pass_matches:
        test_name = p.replace("/", ".").replace(".java", "")
        passed.add(test_name)

    return passed, failed

def parse_test_results(results_dir):
    """Scans XML files for results."""
    passed = set()
    failed = set()
    
    xml_files = glob.glob(os.path.join(results_dir, "**/*.xml"), recursive=True)
    
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for testcase in root.iter('testcase'):
                classname = testcase.get('classname', 'UnknownClass')
                name = testcase.get('name', 'UnknownTest')
                full_name = f"{classname}.{name}"
                
                if testcase.find('failure') is not None or testcase.find('error') is not None:
                    failed.add(full_name)
                else:
                    if testcase.find('skipped') is None:
                        passed.add(full_name)
        except:
            pass
            
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
        return result.stdout.strip() or "NONE"
    except:
        return "ALL"

def collect_test_reports(project_name, project_repo_dir, dest_dir):
    """Recursively searches for XML reports and copies them."""
    found_files = []
    if "jdk" in project_name:
        try:
            cmd = f"find {project_repo_dir} -type f \\( -path '*/JTwork/*.xml' -o -path '*/test-results/*.xml' \\)"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                found_files = result.stdout.strip().splitlines()
        except: pass
    else:
        pattern = PROJECT_CONFIG[project_name]["report_pattern"]
        search_path = os.path.join(project_repo_dir, pattern)
        found_files = glob.glob(search_path, recursive=True)
    
    print(f"--- Found {len(found_files)} XML report files ---")
    
    for f in found_files:
        if not f: continue
        try:
            rel_path = os.path.relpath(f, project_repo_dir).replace("/", "_")
            shutil.copy2(f, os.path.join(dest_dir, rel_path))
        except: pass

def execute_lifecycle(project_name, commit_sha, state, toolkit_dir, project_repo_dir, work_dir, test_targets):
    """
    Runs Build -> Test -> Parse.
    Crucially: It accepts 'test_targets' as an argument, forcing the same tests for both states.
    """
    print(f"\n>>> Processing {state.upper()} state for {commit_sha}...")
    
    config = PROJECT_CONFIG[project_name]
    
    state_dir = os.path.join(work_dir, state)
    build_output_dir = os.path.join(state_dir, "build_out")
    test_output_dir = os.path.join(state_dir, "test_out")
    status_file = os.path.join(state_dir, "build_status.txt")
    console_log_file = os.path.join(state_dir, "console.log")
    
    os.makedirs(build_output_dir, exist_ok=True)
    os.makedirs(test_output_dir, exist_ok=True)

    # 1. Run Build
    env = {
        "COMMIT_SHA": commit_sha,
        "PROJECT_DIR": project_repo_dir,
        "TOOLKIT_DIR": os.path.join(toolkit_dir, "helpers", project_name),
        "BUILDER_IMAGE_TAG": config['builder_tag'],
        "BUILD_STATUS_FILE": status_file,
        "BUILD_DIR_NAME": f"build_{commit_sha[:7]}_{state}" 
    }
    
    if config['build_system'] == 'make':
        env["BOOT_JDK"] = config['boot_jdk']
        env["JTREG_HOME"] = config['jtreg_home']
    elif config['build_system'] == 'self-building':
        env["IMAGE_TAG"] = f"{project_name}-{state}-{commit_sha[:7]}"
        env["BUILD_DIR"] = build_output_dir
    elif config['build_system'] in ['gradle', 'maven']:
         env["IMAGE_TAG_TO_BUILD"] = f"{project_name}-{state}-{commit_sha[:7]}"

    build_script = os.path.join(toolkit_dir, "helpers", project_name, "run_build.sh")
    try:
        run_command(f"bash {build_script}", env=env, check=True)
        with open(status_file, 'r') as f:
            build_status = f.read().strip()
    except:
        build_status = "Fail"

    if build_status != "Success":
        return {"build": "Fail", "test": "Skipped", "passed": set(), "failed": set()}

    # 2. Run Tests (Using the pre-calculated targets)
    if test_targets == "NONE":
         return {"build": "Success", "test": "Skipped (No Targets)", "passed": set(), "failed": set()}
         
    env["TEST_TARGETS"] = test_targets
    env["TEST_REPORT_DIR"] = test_output_dir 
    if config['build_system'] == 'self-building':
        env["BUILD_TYPE"] = state

    test_script = os.path.join(toolkit_dir, "helpers", project_name, "run_tests.sh")
    
    console_output = ""
    try:
        proc = run_command(f"bash {test_script}", env=env, check=False, capture_output=True, text=True)
        with open(console_log_file, "w") as f:
            f.write(proc.stdout)
            if proc.stderr: f.write("\n\n--- STDERR ---\n" + proc.stderr)
        print(proc.stdout) # Stream to tmux
        if proc.stderr: print(proc.stderr)
        
        test_status = "Success" if proc.returncode == 0 else "Fail"
        console_output = proc.stdout
    except Exception as e:
        print(f"Error running tests: {e}")
        test_status = "Error"

    # 3. Parse Results
    collect_test_reports(project_name, project_repo_dir, test_output_dir)
    passed, failed = parse_test_results(test_output_dir)
    
    # Fallback to console parsing if XMLs missing
    if len(passed) == 0 and len(failed) == 0:
        print("--- No XML results found. Attempting to parse console logs... ---")
        log_passed, log_failed = parse_console_output(console_output)
        if len(log_passed) > 0 or len(log_failed) > 0:
            passed, failed = log_passed, log_failed
            print(f"--- Recovered stats from logs: {len(passed)} passed, {len(failed)} failed ---")
        else:
             if test_status == "Fail":
                 test_status = "Crash/No Report"
    
    return {
        "build": build_status, 
        "test": test_status, 
        "passed": passed, 
        "failed": failed
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=None)
    args = parser.parse_args()

    project_name = args.project
    if project_name not in PROJECT_CONFIG:
        print(f"Unknown project: {project_name}")
        sys.exit(1)

    toolkit_dir = os.getcwd()
    dataset_path = os.path.join(toolkit_dir, "dataset", f"{project_name}.csv")
    project_repo_dir = os.path.abspath(os.path.join(toolkit_dir, "..", PROJECT_CONFIG[project_name]["repo_dir"]))
    
    results_csv = os.path.join(toolkit_dir, f"results_{project_name}.csv")
    results_json = os.path.join(toolkit_dir, f"results_{project_name}.json")

    df = pd.read_csv(dataset_path)
    total_rows = len(df)
    end_index = args.end_index if args.end_index is not None else total_rows
    
    print(f"--- Processing {project_name} rows {args.start_index} to {end_index} ---")

    # Load existing
    existing_commits = set()
    full_results_data = []
    if os.path.exists(results_json):
        try:
            with open(results_json, 'r') as f:
                full_results_data = json.load(f)
                existing_commits = {item['commit'] for item in full_results_data}
        except: pass

    # Build Builder Image
    builder_tag = PROJECT_CONFIG[project_name]['builder_tag']
    if PROJECT_CONFIG[project_name]['build_system'] != 'self-building':
        dockerfile = os.path.join(toolkit_dir, "helpers", project_name, "Dockerfile")
        run_command(f"docker build -t {builder_tag} -f {dockerfile} {os.path.dirname(dockerfile)}")

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

        work_dir = os.path.join(toolkit_dir, "temp_work", commit_sha)
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir)

        # --- 1. CALCULATE TESTS (ONCE) ---
        # We calculate targets based on the BACKPORT (After) commit
        print(f"--- Calculating Test Targets for {commit_sha}... ---")
        test_targets = get_smart_test_targets(toolkit_dir, project_repo_dir, commit_sha, project_name)
        print(f"--- Targets: {test_targets} ---")

        # --- 2. EXECUTE AFTER (Fixed) ---
        after_res = execute_lifecycle(project_name, commit_sha, "fixed", toolkit_dir, project_repo_dir, work_dir, test_targets)
        
        # --- 3. EXECUTE BEFORE (Buggy) ---
        if after_res["build"] == "Success":
            before_res = execute_lifecycle(project_name, parent_sha, "buggy", toolkit_dir, project_repo_dir, work_dir, test_targets)
        else:
            before_res = {"build": "Skipped", "test": "Skipped", "passed": set(), "failed": set()}

        # --- ANALYZE ---
        regressions = list(before_res["passed"].intersection(after_res["failed"]))
        fixes = list(before_res["failed"].intersection(after_res["passed"]))

        result_entry = {
            "index": idx,
            "commit": commit_sha,
            "parent": parent_sha,
            "test_targets": test_targets, # Log what we decided to run
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
                "all_failures_after": list(after_res["failed"]),
                "all_failures_before": list(before_res["failed"])
            }
        }

        full_results_data.append(result_entry)

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
        
        # Cleanup
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        if PROJECT_CONFIG[project_name]['build_system'] == 'make':
            run_command(f"sudo rm -rf {project_repo_dir}/build_*", check=False, capture_output=True)
        run_command("docker builder prune -a -f", check=False, capture_output=True)
        if project_name == "elasticsearch":
             run_command(f"docker rmi -f elasticsearch-fixed-{commit_sha[:7]} elasticsearch-buggy-{parent_sha[:7]}", check=False, capture_output=True)

    print("\n=== EXPERIMENT RUN COMPLETE ===")

if __name__ == "__main__":
    main()
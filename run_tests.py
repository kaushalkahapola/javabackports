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
    
    # JDK8 style - verbose FAILED/Passed lines
    fail_matches = re.findall(r"^FAILED:\s+(.+)$", console_text, re.MULTILINE)
    for f in fail_matches:
        test_name = f.replace("/", ".").replace(".java", "")
        failed.add(test_name)

    pass_matches = re.findall(r"^Passed:\s+(.+)$", console_text, re.MULTILINE)
    for p in pass_matches:
        test_name = p.replace("/", ".").replace(".java", "")
        passed.add(test_name)
    
    # JDK11 style - terse "Target X PASSED/FAILED"
    terse_pass = re.findall(r"Target\s+(.+?)\s+PASSED", console_text, re.MULTILINE)
    for target in terse_pass:
        test_name = target.replace("test/", "").replace("/", ".")
        passed.add(test_name)
    
    terse_fail = re.findall(r"Target\s+(.+?)\s+FAILED", console_text, re.MULTILINE)
    for target in terse_fail:
        test_name = target.replace("test/", "").replace("/", ".")
        failed.add(test_name)
    
    # jtreg summary format: "Test results: passed: X; failed: Y"
    summary_match = re.search(r"Test results:\s+passed:\s+(\d+)(?:;\s+failed:\s+(\d+))?", console_text)
    if summary_match and len(passed) == 0 and len(failed) == 0:
        pass_count = int(summary_match.group(1))
        fail_count = int(summary_match.group(2) or 0)
        
        # Try to extract test names from jtreg output
        # Pattern: "test SomeTest.java"
        test_names = re.findall(r"^\s*test\s+(.+\.java)", console_text, re.MULTILINE)
        
        if test_names:
            # We have test names, try to categorize them
            for test_name in test_names:
                clean_name = test_name.replace("/", ".").replace(".java", "")
                # Check if this test failed (look for failure indicators near this test)
                test_section = re.search(
                    rf"{re.escape(test_name)}.*?(?:FAILED|PASSED|^test\s|\Z)", 
                    console_text, 
                    re.DOTALL | re.MULTILINE
                )
                if test_section:
                    section_text = test_section.group(0)
                    if "FAILED" in section_text or "Error" in section_text:
                        failed.add(clean_name)
                    else:
                        passed.add(clean_name)
        else:
            # No test names found, create placeholders based on counts
            if pass_count > 0:
                passed.add(f"TestGroup.passed_{pass_count}_tests")
            if fail_count > 0:
                failed.add(f"TestGroup.failed_{fail_count}_tests")
    
    # Alternative: Look for "TEST: test_name" patterns in jtreg verbose output
    if len(passed) == 0 and len(failed) == 0:
        test_lines = re.findall(r"TEST:\s+(.+)", console_text)
        for test in test_lines:
            clean_test = test.strip().replace("/", ".").replace(".java", "")
            # Default to passed if we can't determine status
            passed.add(clean_test)

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
    print(f"--- Scanning {project_repo_dir} for test reports... ---")
    
    count = 0
    
    # For JDK projects, search more broadly
    if "jdk" in project_name:
        # Search in multiple possible locations
        search_patterns = [
            os.path.join(project_repo_dir, "**/JTwork/**/*.xml"),
            os.path.join(project_repo_dir, "**/JTreport/**/*.xml"),
            os.path.join(project_repo_dir, "build*/JTwork*/**/*.xml"),
            os.path.join(project_repo_dir, "build*/test-results/**/*.xml"),
            os.path.join(project_repo_dir, "build*/test-support/**/*.xml"),
        ]
        
        xml_files = []
        for pattern in search_patterns:
            xml_files.extend(glob.glob(pattern, recursive=True))
        
        # Remove duplicates
        xml_files = list(set(xml_files))
        
        print(f"--- Found {len(xml_files)} XML files in JDK project ---")
        
        for full_src_path in xml_files:
            rel_path = os.path.relpath(full_src_path, project_repo_dir).replace("/", "_")
            dest_path = os.path.join(dest_dir, rel_path)
            try:
                shutil.copy2(full_src_path, dest_path)
                count += 1
            except Exception as e:
                print(f"Failed to copy {full_src_path}: {e}")
    else:
        # Original logic for non-JDK projects
        for root, dirs, files in os.walk(project_repo_dir):
            if ".git" in dirs: 
                dirs.remove(".git")
            
            for file in files:
                if file.endswith(".xml") and file.startswith("TEST-"):
                    full_src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_src_path, project_repo_dir).replace("/", "_")
                    dest_path = os.path.join(dest_dir, rel_path)
                    try:
                        shutil.copy2(full_src_path, dest_path)
                        count += 1
                    except Exception as e:
                        pass

    print(f"--- Collected {count} test report files. ---")
    
    # Debug: List what we collected
    if count > 0:
        print(f"--- Sample of collected files: ---")
        collected_files = os.listdir(dest_dir)[:10]
        for f in collected_files:
            print(f"  - {f}")

def execute_lifecycle(project_name, commit_sha, state, toolkit_dir, project_repo_dir, work_dir, test_targets):
    """
    Runs Build -> Test -> Parse.
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
    
    # Set timeout based on project (JDK tests can take a long time)
    timeout_minutes = 120 if "jdk" in project_name else 60
    
    console_output = ""
    try:
        # Stream output in real-time instead of buffering
        with open(console_log_file, "w") as log_file:
            proc = subprocess.Popen(
                f"bash {test_script}",
                shell=True,
                env={**os.environ, **env},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Read and display output line by line
            try:
                for line in proc.stdout:
                    print(line, end='', flush=True)
                    log_file.write(line)
                    console_output += line
                
                proc.wait(timeout=timeout_minutes * 60)
                test_status = "Success" if proc.returncode == 0 else "Fail"
                
            except subprocess.TimeoutExpired:
                print(f"\n!!! Test execution timed out after {timeout_minutes} minutes !!!")
                proc.kill()
                proc.wait()
                test_status = "Timeout"
            
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

    existing_commits = set()
    full_results_data = []
    if os.path.exists(results_json):
        try:
            with open(results_json, 'r') as f:
                full_results_data = json.load(f)
                existing_commits = {item['commit'] for item in full_results_data}
        except: pass

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

        # --- 1. CALCULATE TESTS ---
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

        # --- 4. DETAILED ANALYSIS (UPDATED) ---
        
        # Fail -> Pass (Fixes)
        fixes = list(before_res["failed"].intersection(after_res["passed"]))
        
        # Pass -> Fail (Regressions)
        regressions = list(before_res["passed"].intersection(after_res["failed"]))
        
        # Failed in Both (Persistent)
        persistent = list(before_res["failed"].intersection(after_res["failed"]))
        
        # --- NEW LOGIC: New Tests that Passed ---
        # (Passed in After) MINUS (Passed in Before OR Failed in Before)
        # Meaning: It passed now, but it didn't exist (or didn't run) before.
        all_tests_before = before_res["passed"].union(before_res["failed"])
        new_passes = list(after_res["passed"].difference(all_tests_before))

        result_entry = {
            "index": idx,
            "commit": commit_sha,
            "parent": parent_sha,
            "test_targets": test_targets, 
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
                "fix_count": len(fixes),
                "new_pass_count": len(new_passes) # New Stat
            },
            "details": {
                "regressions": regressions,
                "fixes": fixes,
                "new_passes": new_passes, # New List
                "persistent_failures": persistent,
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
            "fixes": len(fixes),
            "new_passes": len(new_passes) # New Column
        }
        
        csv_df = pd.DataFrame([csv_row])
        if not os.path.exists(results_csv):
            csv_df.to_csv(results_csv, index=False)
        else:
            csv_df.to_csv(results_csv, mode='a', header=False, index=False)

        print(f"--- Results saved for {commit_sha} ---")
        
        # Cleanup
        if os.path.exists(work_dir): 
            # Use the run_command wrapper to execute removal with sudo
            run_command(f"sudo rm -rf {work_dir}", check=False, capture_output=True)
        if PROJECT_CONFIG[project_name]['build_system'] == 'make':
            run_command(f"sudo rm -rf {project_repo_dir}/build_*", check=False, capture_output=True)
        run_command("docker builder prune -a -f", check=False, capture_output=True)
        if project_name == "elasticsearch":
             run_command(f"docker rmi -f elasticsearch-fixed-{commit_sha[:7]} elasticsearch-buggy-{parent_sha[:7]}", check=False, capture_output=True)

    print("\n=== EXPERIMENT RUN COMPLETE ===")

if __name__ == "__main__":
    main()

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
        "build_system": "self-building"
    },
    "hadoop": {
        "repo_dir": "hadoop",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "hadoop-builder:latest",
        "build_system": "self-building"
    },
    "druid": {
        "repo_dir": "druid",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "druid-builder:latest",
        "build_system": "maven"
    },
    "graylog2-server": {
        "repo_dir": "graylog2-server",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "graylog-builder:latest",
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
    },
    "sql": {
        "repo_dir": "sql",
        "report_pattern": "**/build/test-results/**/*.xml",
        "builder_tag": "sql-builder:latest",
        "build_system": "self-building"
    },
    "logstash": {
        "repo_dir": "logstash",
        "report_pattern": "**/build/test-results/**/*.xml",
        "builder_tag": "logstash-builder:latest",
        "build_system": "self-building"
    }
}

def run_command(command, env=None, check=True, cwd=None, **kwargs):
    if not kwargs.get("capture_output"):
        print(f"CMD: {command}", flush=True)
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(command, shell=True, check=check, env=process_env, cwd=cwd, **kwargs)

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def parse_console_output(console_text):
    console_text = strip_ansi(console_text)
    passed = set()
    failed = set()

    # JTreg verbose: TEST RESULT: Passed / Failed
    for match in re.finditer(r"TEST:\s+(.+\.java)\s*\nTEST RESULT:\s*(Passed|Failed)", console_text):
        test_file, result = match.groups()
        clean_name = test_file.replace("/", ".").replace(".java", "")
        if result == "Passed":
            passed.add(clean_name)
        else:
            failed.add(clean_name)

    # ✅ / ❌ style: Target ... PASSED / FAILED
    for match in re.finditer(r"✅ Target\s+(.+?)\s+PASSED", console_text):
        passed.add(match.group(1).replace("test/", "").replace("/", "."))
    for match in re.finditer(r"❌ Target\s+(.+?)\s+FAILED", console_text):
        failed.add(match.group(1).replace("test/", "").replace("/", "."))

    # jtreg summary fallback
    summary_match = re.search(r"Test results:\s+passed:\s+(\d+)(?:;\s+failed:\s+(\d+))?", console_text)
    if summary_match and len(passed) == 0 and len(failed) == 0:
        pass_count = int(summary_match.group(1))
        fail_count = int(summary_match.group(2) or 0)
        for i in range(pass_count):
            passed.add(f"TestGroup.passed_{i+1}")
        for i in range(fail_count):
            failed.add(f"TestGroup.failed_{i+1}")

    # Gradle style: Class > Method PASSED
    # Example: org.logstash.plugins.NamespacedMetricImplTest > testNamespaceUnicodeFragment PASSED
    for match in re.finditer(r"([a-zA-Z0-9_$.]+)\s+>\s+([a-zA-Z0-9_$]+)\s+(PASSED|FAILED|SKIPPED)", console_text):
        cls, method, status = match.groups()
        full_name = f"{cls}.{method}"
        if status == "PASSED":
            passed.add(full_name)
        elif status == "FAILED":
            failed.add(full_name)

    return passed, failed

def parse_test_results(results_dir):
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
                elif testcase.find('skipped') is None:
                    passed.add(full_name)
        except:
            continue
    return passed, failed

def get_smart_test_targets(toolkit_dir, project_dir, commit_sha, project_name):
    resolver_script = os.path.join(toolkit_dir, "helpers", project_name, "get_test_targets.py")
    if not os.path.exists(resolver_script):
        return {"modified": [], "added": [], "all_targets": "ALL"}
    try:
        result = subprocess.run(
            f"python3 {resolver_script} --repo {project_dir} --commit {commit_sha}",
            shell=True, capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if not output:
            return {"modified": [], "added": [], "all_targets": "NONE"}
        
        # Try to parse as JSON (new format)
        try:
            data = json.loads(output)
            modified = data.get("modified", [])
            added = data.get("added", [])
            
            # Determine all_targets string for backward compatibility
            if not modified and not added:
                all_targets = "NONE"
            else:
                all_targets = " ".join(modified + added)
            
            return {
                "modified": modified,
                "added": added,
                "all_targets": all_targets
            }
        except json.JSONDecodeError:
            # Fallback for old format (space-separated list)
            return {"modified": [], "added": [], "all_targets": output}
    except:
        return {"modified": [], "added": [], "all_targets": "ALL"}

def collect_test_reports(project_name, project_repo_dir, dest_dir):
    print(f"--- Scanning {project_repo_dir} for test reports... ---")
    count = 0
    if "jdk" in project_name:
        patterns = [
            os.path.join(project_repo_dir, "**/JTwork/**/*.xml"),
            os.path.join(project_repo_dir, "**/JTreport/**/*.xml")
        ]
        xml_files = []
        for pat in patterns:
            xml_files.extend(glob.glob(pat, recursive=True))
        xml_files = list(set(xml_files))
        print(f"--- Found {len(xml_files)} XML files in JDK project ---")
        for full_src_path in xml_files:
            rel_path = os.path.relpath(full_src_path, project_repo_dir)
            dest_path = os.path.join(dest_dir, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            try:
                shutil.copy2(full_src_path, dest_path)
                count += 1
            except Exception as e:
                print(f"Failed to copy {full_src_path}: {e}")
    else:
        # For self-building projects (like ES), source_dir is already the build directory
        # We aggregated all results into 'all-test-results' in run_tests.sh
        if PROJECT_CONFIG[project_name]['build_system'] == 'self-building':
             full_pattern = os.path.join(project_repo_dir, "all-test-results", "*.xml")
        else:
             full_pattern = os.path.join(project_repo_dir, PROJECT_CONFIG[project_name]["report_pattern"])
        
        print(f"--- Searching for reports with pattern: {full_pattern} ---")
        
        for file in glob.glob(full_pattern, recursive=True):
             if file.endswith(".xml"):
                full_src_path = file
                rel_path = os.path.relpath(full_src_path, project_repo_dir)
                dest_path = os.path.join(dest_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                try:
                    shutil.copy2(full_src_path, dest_path)
                    count += 1
                except:
                    continue
    print(f"--- Collected {count} test report files. ---")
    if count > 0:
        print(f"--- Sample of collected files: ---")
        for f in os.listdir(dest_dir)[:10]:
            print(f"  - {f}")

def execute_lifecycle(project_name, commit_sha, state, toolkit_dir, project_repo_dir, work_dir, test_targets):
    print(f"\n>>> Processing {state.upper()} state for {commit_sha}...")
    config = PROJECT_CONFIG[project_name]
    state_dir = os.path.join(work_dir, state)
    build_output_dir = os.path.join(state_dir, "build_out")
    test_output_dir = os.path.join(state_dir, "test_out")
    status_file = os.path.join(state_dir, "build_status.txt")
    console_log_file = os.path.join(state_dir, "console.log")

    os.makedirs(build_output_dir, exist_ok=True)
    os.makedirs(test_output_dir, exist_ok=True)

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

    if test_targets == "NONE":
         return {"build": "Success", "test": "Skipped (No Targets)", "passed": set(), "failed": set()}

    env["TEST_TARGETS"] = test_targets
    env["TEST_REPORT_DIR"] = test_output_dir
    if config['build_system'] == 'self-building':
        env["BUILD_TYPE"] = state

    test_script = os.path.join(toolkit_dir, "helpers", project_name, "run_tests.sh")
    timeout_minutes = 120 if "jdk" in project_name else 60
    console_output = ""

    try:
        with open(console_log_file, "w") as log_file:
            proc = subprocess.Popen(
                f"bash {test_script}",
                shell=True,
                env={**os.environ, **env},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
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

    source_dir = project_repo_dir
    if config['build_system'] == 'self-building':
        source_dir = build_output_dir
    collect_test_reports(project_name, source_dir, test_output_dir)
    passed, failed = parse_test_results(test_output_dir)

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
            
            # Check file count
            res_files = subprocess.run(f"git diff-tree --no-commit-id --name-only -r {commit_sha}", shell=True, cwd=project_repo_dir, capture_output=True, text=True)
            changed_files = res_files.stdout.strip().splitlines()
            if len(changed_files) > 10:
                print(f"--- Skipping {commit_sha} (Too many changed files: {len(changed_files)}) ---")
                continue
        except:
            print("Error finding parent commit or checking file count.")
            continue

        work_dir = os.path.join(toolkit_dir, "temp_work", commit_sha)
        if os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
            except PermissionError:
                run_command(f"sudo rm -rf {work_dir}", check=False, capture_output=True)
        os.makedirs(work_dir)

        print(f"--- Calculating Test Targets for {commit_sha}... ---")
        test_targets_data = get_smart_test_targets(toolkit_dir, project_repo_dir, commit_sha, project_name)
        modified_tests = test_targets_data["modified"]
        added_tests = test_targets_data["added"]
        all_targets = test_targets_data["all_targets"]
        
        print(f"--- Modified tests: {modified_tests or 'None'} ---")
        print(f"--- Added tests: {added_tests or 'None'} ---")

        if all_targets == "NONE" or (not modified_tests and not added_tests and all_targets == ""):
             print(f"--- No test targets found for {commit_sha}. Skipping build. ---")
             result_entry = {
                "index": idx,
                "commit": commit_sha,
                "parent": parent_sha,
                "test_targets": {
                    "modified": modified_tests,
                    "added": added_tests,
                    "all": all_targets
                },
                "build_status_after": "Skipped",
                "test_status_after": "Skipped (No Targets)",
                "build_status_before": "Skipped",
                "test_status_before": "Skipped",
                "stats": {
                    "after_pass_count": 0,
                    "after_fail_count": 0,
                    "before_pass_count": 0,
                    "before_fail_count": 0,
                    "regression_count": 0,
                    "fix_count": 0,
                    "new_pass_count": 0
                },
                "details": {
                    "regressions": [],
                    "fixes": [],
                    "new_passes": [],
                    "persistent_failures": [],
                    "all_failures_after": [],
                    "all_failures_before": []
                }
            }
             full_results_data.append(result_entry)
             with open(results_json, 'w') as f:
                json.dump(full_results_data, f, indent=2)

             csv_row = {
                "commit": commit_sha,
                "build_after": "Skipped",
                "test_after": "Skipped (No Targets)",
                "build_before": "Skipped",
                "test_before": "Skipped",
                "regressions": 0,
                "fixes": 0,
                "new_passes": 0
             }
             csv_df = pd.DataFrame([csv_row])
             if not os.path.exists(results_csv):
                csv_df.to_csv(results_csv, index=False)
             else:
                csv_df.to_csv(results_csv, mode='a', header=False, index=False)
             print(f"--- Results saved for {commit_sha} (Skipped) ---")
             continue
        
        # Decide if we need to test buggy version
        skip_buggy = (len(modified_tests) == 0 and len(added_tests) > 0)
        
        if skip_buggy:
            print(f"--- Only new tests detected. Skipping buggy build and running tests only on patched version. ---")

        # Run patched version
        patched_test_targets = " ".join(modified_tests + added_tests) if (modified_tests or added_tests) else all_targets
        after_res = execute_lifecycle(project_name, commit_sha, "fixed", toolkit_dir, project_repo_dir, work_dir, patched_test_targets)
        
        # Run buggy version only if needed
        if after_res["build"] == "Success" and not skip_buggy:
            buggy_test_targets = " ".join(modified_tests) if modified_tests else "NONE"
            before_res = execute_lifecycle(project_name, parent_sha, "buggy", toolkit_dir, project_repo_dir, work_dir, buggy_test_targets)
        else:
            before_res = {"build": "Skipped", "test": "Skipped (Only New Tests)", "passed": set(), "failed": set()}

        fixes = list(before_res["failed"].intersection(after_res["passed"]))
        regressions = list(before_res["passed"].intersection(after_res["failed"]))
        persistent = list(before_res["failed"].intersection(after_res["failed"]))
        all_tests_before = before_res["passed"].union(before_res["failed"])
        new_passes = list(after_res["passed"].difference(all_tests_before))

        result_entry = {
            "index": idx,
            "commit": commit_sha,
            "parent": parent_sha,
            "test_targets": {
                "modified": modified_tests,
                "added": added_tests,
                "all": all_targets
            },
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
                "new_pass_count": len(new_passes)
            },
            "details": {
                "regressions": regressions,
                "fixes": fixes,
                "new_passes": new_passes,
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
            "new_passes": len(new_passes)
        }

        csv_df = pd.DataFrame([csv_row])
        if not os.path.exists(results_csv):
            csv_df.to_csv(results_csv, index=False)
        else:
            csv_df.to_csv(results_csv, mode='a', header=False, index=False)

        print(f"--- Results saved for {commit_sha} ---")

        if os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
            except PermissionError:
                # Docker-created files may have wrong permissions
                run_command(f"sudo rm -rf {work_dir}", check=False, capture_output=True)
        if PROJECT_CONFIG[project_name]['build_system'] == 'make':
            run_command(f"sudo rm -rf {project_repo_dir}/build_*", check=False, capture_output=True)
        run_command("docker builder prune -a -f", check=False, capture_output=True)
        if project_name == "elasticsearch":
            run_command(f"docker rmi -f elasticsearch-fixed-{commit_sha[:7]} elasticsearch-buggy-{parent_sha[:7]}", check=False, capture_output=True)

    print("\n=== EXPERIMENT RUN COMPLETE ===")

if __name__ == "__main__":
    main()


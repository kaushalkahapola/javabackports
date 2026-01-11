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
    "jdk25u-dev": {
        "repo_dir": "jdk25u-dev",
        "report_pattern": "**/JTwork/**/*.xml",
        "builder_tag": "jdk25-builder:latest",
        "build_system": "make",
        "boot_jdk": "/opt/java/jdk-24",
        "jtreg_home": "/opt/jtreg"
    },
    "hibernate-orm": {
        "repo_dir": "hibernate-orm",
        "report_pattern": "**/*.xml",
        "builder_tag": "hibernate-builder:latest",
        "build_system": "gradle"
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
    },
    "spring-framework": {
        "repo_dir": "spring-framework",
        "report_pattern": "**/build/test-results/**/*.xml",
        "builder_tag": "spring-builder:latest",
        "build_system": "self-building"
    },
    "doris": {
        "repo_dir": "doris",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "doris-builder:latest",
        "build_system": "maven"
    },
    "hbase": {
        "repo_dir": "hbase",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "hbase-builder:latest",
        "build_system": "maven"
    },
    "flink": {
        "repo_dir": "flink",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "flink-builder:latest",
        "build_system": "maven"
    },
    "hive": {
        "repo_dir": "hive",
        "report_pattern": "**/target/surefire-reports/*.xml",
        "builder_tag": "hive-builder:latest",
        "build_system": "maven"
    },
    "lucene": {
        "repo_dir": "lucene",
        "report_pattern": "all-test-results/*.xml",
        "builder_tag": "lucene-builder:latest",
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

    # Maven Surefire/Failsafe: [INFO] Running ... and [INFO] Tests run: ... -- in ...
    # Example:
    # [INFO] Running org.apache.hadoop.hbase.backup.master.TestBackupLogCleaner
    # [INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: ... -- in org.apache.hadoop.hbase.backup.master.TestBackupLogCleaner
    surefire_results = {}
    for match in re.finditer(r"^\[INFO\] Running ([\w.$-]+)", console_text, re.MULTILINE):
        current_class = match.group(1)
        surefire_results[current_class] = {"run": 0, "fail": 0, "error": 0, "skipped": 0}
    for match in re.finditer(r"^\[INFO\] Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)[^\n]*-- in ([\w.$-]+)", console_text, re.MULTILINE):
        run, fail, error, skipped, test_class = match.groups()
        run = int(run)
        fail = int(fail)
        error = int(error)
        skipped = int(skipped)
        # Count all non-failed, non-error tests as passed
        fail_count = fail + error
        pass_count = run - fail - error - skipped
        for i in range(pass_count):
            passed.add(f"{test_class}.pass_{i+1}")
        for i in range(fail_count):
            failed.add(f"{test_class}.fail_{i+1}")

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

def get_modified_test_files(project_dir, commit_sha):
    """Get list of modified test files (not newly added) from commit."""
    try:
        # Get modified files (excluding added files)
        result = subprocess.run(
            f"git diff-tree --no-commit-id --name-only --diff-filter=M -r {commit_sha}",
            shell=True, cwd=project_dir, capture_output=True, text=True, check=True
        )
        all_modified = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
        
        # Filter for test files
        test_files = []
        for f in all_modified:
            if any(indicator in f.lower() for indicator in ['test', 'spec']) and f.endswith('.java'):
                test_files.append(f)
        
        return test_files
    except:
        return []

def apply_test_changes(project_dir, commit_sha, test_files):
    """Apply changes to specific test files from commit_sha to current state."""
    if not test_files:
        return True, "No test files to apply"
    
    try:
        for test_file in test_files:
            # Get the file content from the commit
            result = subprocess.run(
                f"git show {commit_sha}:{test_file}",
                shell=True, cwd=project_dir, capture_output=True, text=True
            )
            if result.returncode != 0:
                continue
            
            file_content = result.stdout
            file_path = os.path.join(project_dir, test_file)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write the updated file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
        
        return True, f"Applied changes to {len(test_files)} test files"
    except Exception as e:
        return False, f"Error applying test changes: {e}"

def compile_and_check_imports(project_dir, test_files, project_name):
    """Compile test files and check specifically for import errors."""
    if not test_files:
        return True, "No files to compile", []
    
    print(f"--- Checking for import errors in {len(test_files)} test files... ---")
    
    # Find Java compiler and classpath
    # This is a simplified approach - may need project-specific adjustments
    compile_errors = []
    import_errors = []

    # Check for javac
    if not shutil.which("javac"):
        print("  ⚠️  javac not found on system path. Skipping import checks.")
        return True, "Skipped (javac not found)", []
    
    for test_file in test_files:
        file_path = os.path.join(project_dir, test_file)
        if not os.path.exists(file_path):
            continue
        
        try:
            # Try to compile the file
            # For a proper check, we'd need the project's classpath, but we can do a basic check
            result = subprocess.run(
                f"javac -Xlint:all {file_path}",
                shell=True, cwd=project_dir, capture_output=True, text=True, timeout=30
            )
            
            error_output = result.stderr + result.stdout
            
            # Check for import-related errors
            import_error_patterns = [
                r"package .+ does not exist",
                r"cannot find symbol.*import",
                r"class .+ is not public",
                r"cannot access",
            ]
            
            for pattern in import_error_patterns:
                if re.search(pattern, error_output, re.IGNORECASE):
                    import_errors.append({
                        "file": test_file,
                        "error": error_output
                    })
                    print(f"  ❌ Import error in {test_file}")
                    break
            else:
                # Has errors but not import-related
                if result.returncode != 0:
                    compile_errors.append({
                        "file": test_file,
                        "error": error_output
                    })
                    print(f"  ⚠️  Compilation error (not import) in {test_file}")
                    print(f"     DETAILS:\n{error_output}\n     ----------------------------------")
                else:
                    print(f"  ✅ No import errors in {test_file}")
        
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  Compilation timeout for {test_file}")
            continue
        except Exception as e:
            print(f"  ⚠️  Error checking {test_file}: {e}")
            continue
    
    if import_errors:
        return False, f"Import errors detected in {len(import_errors)} files", import_errors
    
    return True, "No import errors detected", compile_errors

def get_smart_test_targets(toolkit_dir, project_dir, commit_sha, project_name):
    resolver_script = os.path.join(toolkit_dir, "helpers", project_name, "get_test_targets.py")
    if not os.path.exists(resolver_script):
        return {"modified": [], "added": [], "all_targets": "ALL"}
    try:
        result = subprocess.run(
            f"python3 {resolver_script} --repo {project_dir} --commit {commit_sha}",
            shell=True, capture_output=True, text=True, check=False
        )
        if result.stderr:
            print(f"--- Debug get_test_targets stderr: ---\n{result.stderr}\n----------------------------------")
        
        if result.returncode != 0:
            print(f"--- WARNING: get_test_targets exited with code {result.returncode} ---")
            print(f"--- stdout: {result.stdout} ---")
            return {"modified": [], "added": [], "all_targets": "ALL"}
        
        output = result.stdout.strip()
        if not output:
            print(f"--- get_test_targets returned empty output ---")
            return {"modified": [], "added": [], "all_targets": "NONE"}
        
        # Try to parse as JSON (new format)
        try:
            data = json.loads(output)
            modified = data.get("modified", [])
            added = data.get("added", [])
            
            print(f"--- Test target detection: {len(modified)} modified, {len(added)} added ---")
            print(f"--- Debug: Modified targets: {modified} ---")
            print(f"--- Debug: Added targets: {added} ---")
            
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
        except json.JSONDecodeError as e:
            print(f"--- ERROR: Failed to parse JSON from get_test_targets: {e} ---")
            print(f"--- Output was: {output} ---")
            # Fallback for old format (space-separated list)
            return {"modified": [], "added": [], "all_targets": output}
    except Exception as e:
        print(f"--- ERROR calling get_test_targets: {e} ---")
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

def execute_lifecycle(project_name, commit_sha, state, toolkit_dir, project_repo_dir, work_dir, test_targets,
                      apply_test_changes_from=None, modified_test_files=None, build_scope=None):
    """
    Execute build and test lifecycle for a commit state.
    
    Args:
        apply_test_changes_from: If provided, apply test changes from this commit before building
        modified_test_files: List of modified test files to apply
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
    
    # If this is buggy state and we need to apply test changes
    if apply_test_changes_from and modified_test_files:
        print(f"--- Applying modified test changes from {apply_test_changes_from[:7]} to buggy state ---")
        success, msg = apply_test_changes(project_repo_dir, apply_test_changes_from, modified_test_files)
        if not success:
            return {"build": "Error", "test": "Skipped", "passed": set(), "failed": set(), 
                    "error_type": "test_apply_failed", "error_msg": msg}
        
        print(f"--- {msg} ---")
        
        # Check for import errors
        has_no_import_errors, check_msg, errors = compile_and_check_imports(
            project_repo_dir, modified_test_files, project_name
        )
        
        if not has_no_import_errors:
            print(f"--- ❌ IMPORT ERROR DETECTED: {check_msg} ---")
            return {"build": "Skipped", "test": "Skipped", "passed": set(), "failed": set(),
                    "error_type": "import_error", "error_msg": check_msg, "import_errors": errors}
        
        print(f"--- ✅ {check_msg} ---")

    env = {
        "COMMIT_SHA": commit_sha,
        "PROJECT_DIR": project_repo_dir,
        "TOOLKIT_DIR": os.path.join(toolkit_dir, "helpers", project_name),
        "BUILDER_IMAGE_TAG": config['builder_tag'],
        "BUILD_STATUS_FILE": status_file,
        "BUILD_DIR_NAME": f"build_{commit_sha[:7]}_{state}"
    }

    # Allow per-project build scope hints (e.g., Doris FE_ONLY vs FULL)
    if project_name == "doris" and build_scope:
        env["DORIS_BUILD_SCOPE"] = build_scope

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

    # Use new results folder to avoid overlap
    results_dir = os.path.join(toolkit_dir, "results_v2")
    os.makedirs(results_dir, exist_ok=True)
    results_csv = os.path.join(results_dir, f"results_{project_name}.csv")
    results_json = os.path.join(results_dir, f"results_{project_name}.json")

    df = pd.read_csv(dataset_path)
    total_rows = len(df)
    end_index = args.end_index if args.end_index is not None else total_rows

    print(f"--- Processing {project_name} rows {args.start_index} to {end_index} ---")

    # Check CSV for already processed commits (faster than JSON)
    existing_commits = set()
    if os.path.exists(results_csv):
        try:
            csv_df = pd.read_csv(results_csv)
            existing_commits = set(csv_df['commit'].tolist())
        except: pass
    
    # Load JSON for appending new results
    full_results_data = []
    if os.path.exists(results_json):
        try:
            with open(results_json, 'r') as f:
                full_results_data = json.load(f)
        except: pass
    
    # Load old results for reuse when only new tests are added
    old_results_csv = os.path.join(toolkit_dir, f"results_{project_name}.csv")
    old_results_json = os.path.join(toolkit_dir, f"results_{project_name}.json")
    old_results_map = {}
    if os.path.exists(old_results_json):
        try:
            with open(old_results_json, 'r') as f:
                old_results = json.load(f)
                old_results_map = {item['commit']: item for item in old_results}
            print(f"--- Loaded {len(old_results_map)} existing results for potential reuse ---")
        except:
            pass

    builder_tag = PROJECT_CONFIG[project_name]['builder_tag']
    if PROJECT_CONFIG[project_name]['build_system'] != 'self-building':
        dockerfile = os.path.join(toolkit_dir, "helpers", project_name, "Dockerfile")
        run_command(f"docker build -t {builder_tag} -f {dockerfile} {os.path.dirname(dockerfile)}")

    doris_build_scope = None

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
            if len(changed_files) > 50:
                print(f"--- Skipping {commit_sha} (Too many changed files: {len(changed_files)}) ---")
                continue

            # Check if any Java files are modified
            has_java_changes = any(f.endswith(".java") for f in changed_files)
            print(f"--- Changed files in {commit_sha}: {len(changed_files)} total, Java: {sum(1 for f in changed_files if f.endswith('.java'))} ---")
            if len(changed_files) <= 20:
                for f in changed_files[:10]:
                    print(f"    {f}")
            if not has_java_changes:
                print(f"--- Skipping {commit_sha} (No Java files changed) ---")
                continue
            
            # Separate test and non-test Java files
            test_java_files = [f for f in changed_files if f.endswith(".java") and any(indicator in f.lower() for indicator in ['test', 'spec'])]
            non_test_java_files = [f for f in changed_files if f.endswith(".java") and not any(indicator in f.lower() for indicator in ['test', 'spec'])]
            
            print(f"--- Java files breakdown: {len(non_test_java_files)} code, {len(test_java_files)} test ---")
            
            # Require both code changes AND test changes to continue
            if len(non_test_java_files) == 0:
                print(f"--- Skipping {commit_sha} (Only test files changed, no code changes) ---")
                continue
            if len(test_java_files) == 0:
                print(f"--- Skipping {commit_sha} (Only code files changed, no test changes) ---")
                continue

            # For Doris, decide FE-only vs full build based on changed files
            if project_name == "doris":
                be_like_exts = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")
                be_like_paths = ("be/", "thirdparty/", "output/", "ui/", "docker/", "cloud/be")

                touches_be_or_native = False
                for path in changed_files:
                    lower_path = path.lower()
                    if lower_path.startswith(be_like_paths) or any(lower_path.endswith(ext) for ext in be_like_exts):
                        touches_be_or_native = True
                        break

                doris_build_scope = "FULL" if touches_be_or_native else "FE_ONLY"
                print(f"--- Doris build scope for {commit_sha}: {doris_build_scope} ---")
        except:
            print("Error finding parent commit or checking file count.")
            continue

        # Early check: if old results show build_after failed, reuse immediately
        if commit_sha in old_results_map:
            old_result = old_results_map[commit_sha]
            build_after_status = old_result.get("build_status_after", "Unknown")
            
            if build_after_status == "Fail":
                print(f"--- ✅ REUSING OLD RESULTS: Build failed in previous run, no need to retry ---")
                
                # Convert old result to new format
                result_entry = {
                    "index": idx,
                    "commit": commit_sha,
                    "parent": old_result.get("parent", parent_sha),
                    "validation_status": "BUILD_FAILED",
                    "validation_reason": "reused_build_failure",
                    "reused_from_old_results": True,
                    "test_targets": {
                        "modified": old_result.get("test_targets", {}).get("modified", []),
                        "added": old_result.get("test_targets", {}).get("added", []),
                        "modified_files": [],
                        "all": old_result.get("test_targets", {}).get("all", "NONE")
                    },
                    "build_status_after": build_after_status,
                    "test_status_after": old_result.get("test_status_after", "Skipped"),
                    "build_status_before": old_result.get("build_status_before", "Skipped"),
                    "test_status_before": old_result.get("test_status_before", "Skipped"),
                    "error_info": {
                        "before_error_type": None,
                        "before_error_msg": None,
                        "import_errors": []
                    },
                    "stats": old_result.get("stats", {}),
                    "details": old_result.get("details", {})
                }
                
                full_results_data.append(result_entry)
                with open(results_json, 'w') as f:
                    json.dump(full_results_data, f, indent=2)
                
                # Save to CSV
                csv_row = {
                    "commit": commit_sha,
                    "validation_status": "BUILD_FAILED",
                    "validation_reason": "reused_build_failure",
                    "build_after": build_after_status,
                    "test_after": old_result.get("test_status_after", "Skipped"),
                    "build_before": old_result.get("build_status_before", "Skipped"),
                    "test_before": old_result.get("test_status_before", "Skipped"),
                    "error_type": "",
                    "regressions": old_result.get("stats", {}).get("regression_count", 0),
                    "fixes": old_result.get("stats", {}).get("fix_count", 0),
                    "new_passes": old_result.get("stats", {}).get("new_pass_count", 0)
                }
                csv_df = pd.DataFrame([csv_row])
                if not os.path.exists(results_csv):
                    csv_df.to_csv(results_csv, index=False)
                else:
                    csv_df.to_csv(results_csv, mode='a', header=False, index=False)
                
                print(f"--- ✅ Reused build failure result for {commit_sha} ---")
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

        # If no explicit test files were detected, skip
        if len(modified_tests) == 0 and len(added_tests) == 0:
            print(f"--- Skipping {commit_sha} (No test targets detected; no work to do) ---")
            continue
        
        # Determine modified test files (for applying changes to buggy version)
        modified_test_files = get_modified_test_files(project_repo_dir, commit_sha)
        
        # Determine if we need to test buggy version
        skip_buggy = (len(modified_tests) == 0 and len(added_tests) > 0)
        
        # Check if we can reuse old results (only new tests, no modified tests)
        # Can only reuse if: (build_after=Success AND test_after=Success) OR (build_after=Fail)
        # Cannot reuse if: build_after=Success AND test_after=Fail (need baseline for comparison)
        if len(modified_tests) == 0 and len(added_tests) > 0 and commit_sha in old_results_map:
            old_result = old_results_map[commit_sha]
            build_after_status = old_result.get("build_status_after", "Unknown")
            test_after_status = old_result.get("test_status_after", "Unknown")
            
            can_reuse = False
            reuse_reason = ""
            
            if build_after_status == "Success" and test_after_status == "Success":
                can_reuse = True
                reuse_reason = "build_and_tests_passed"
            elif build_after_status == "Success" and test_after_status in ["Fail", "Timeout", "Error"]:
                can_reuse = False
                print(f"--- ⚠️  CANNOT REUSE: Build succeeded but tests failed - need baseline for comparison ---")
            
            if can_reuse:
                print(f"--- ✅ REUSING OLD RESULTS: Only new tests, {reuse_reason} ---")
            
                # Convert old result format to new format with validation status
                result_entry = {
                    "index": idx,
                    "commit": commit_sha,
                    "parent": old_result.get("parent", parent_sha),
                    "validation_status": "VALID_BACKPORT",
                    "validation_reason": f"reused_{reuse_reason}",
                    "reused_from_old_results": True,
                    "test_targets": {
                        "modified": [],
                        "added": added_tests,
                        "modified_files": [],
                        "all": all_targets
                    },
                    "build_status_after": build_after_status,
                    "test_status_after": test_after_status,
                    "build_status_before": old_result.get("build_status_before", "Skipped"),
                    "test_status_before": old_result.get("test_status_before", "Skipped"),
                    "error_info": {
                        "before_error_type": None,
                        "before_error_msg": None,
                        "import_errors": []
                    },
                    "stats": old_result.get("stats", {}),
                    "details": old_result.get("details", {})
                }
                
                full_results_data.append(result_entry)
                with open(results_json, 'w') as f:
                    json.dump(full_results_data, f, indent=2)
                
                # Save to CSV
                csv_row = {
                    "commit": commit_sha,
                    "validation_status": "VALID_BACKPORT",
                    "validation_reason": f"reused_{reuse_reason}",
                    "build_after": build_after_status,
                    "test_after": test_after_status,
                    "build_before": result_entry["build_status_before"],
                    "test_before": result_entry["test_status_before"],
                    "error_type": "",
                    "regressions": result_entry["stats"].get("regression_count", 0),
                    "fixes": result_entry["stats"].get("fix_count", 0),
                    "new_passes": result_entry["stats"].get("new_pass_count", 0)
                }
                csv_df = pd.DataFrame([csv_row])
                if not os.path.exists(results_csv):
                    csv_df.to_csv(results_csv, index=False)
                else:
                    csv_df.to_csv(results_csv, mode='a', header=False, index=False)
                
                print(f"--- ✅ Reused results saved for {commit_sha} ---")
                continue
        
        # Decide if we need to test buggy version
        skip_buggy = (len(modified_tests) == 0 and len(added_tests) > 0)
        
        if skip_buggy:
            print(f"--- Only new tests detected. Skipping buggy build and running tests only on patched version. ---")

        # Run patched version first
        patched_test_targets = " ".join(modified_tests + added_tests) if (modified_tests or added_tests) else all_targets
        after_res = execute_lifecycle(
            project_name,
            commit_sha,
            "fixed",
            toolkit_dir,
            project_repo_dir,
            work_dir,
            patched_test_targets,
            build_scope=doris_build_scope if project_name == "doris" else None,
        )
        
        # Always run buggy version for proper baseline comparison
        # For patches with only new tests: run without applying test changes (no modified files)
        # For patches with modified tests: apply test changes and check for import errors
        if after_res["build"] == "Success":
            # Checkout parent commit
            run_command(f"git checkout {parent_sha}", cwd=project_repo_dir, capture_output=True)
            
            # Early import check: if we have modified test files, check them for import errors
            # before spending time building the buggy version
            if len(modified_test_files) > 0:
                print(f"--- Early import check: applying test changes and checking for import errors ---")
                success, msg = apply_test_changes(project_repo_dir, commit_sha, modified_test_files)
                if not success:
                    print(f"--- ⚠️  Failed to apply test changes: {msg} ---")
                    # Skip buggy build, mark as invalid
                    print(f"--- ❌ INVALID BACKPORT: Could not apply test changes to buggy version ---")
                    result_entry = {
                        "index": idx,
                        "commit": commit_sha,
                        "parent": parent_sha,
                        "validation_status": "INVALID_BACKPORT",
                        "validation_reason": "test_apply_failed",
                        "error_details": msg,
                        "import_errors": [],
                        "test_targets": {
                            "modified": modified_tests,
                            "added": added_tests,
                            "modified_files": modified_test_files if 'modified_test_files' in locals() else [],
                        }
                    }
                    full_results_data.append(result_entry)
                    with open(results_json, 'w') as f:
                        json.dump(full_results_data, f, indent=2)
                    # Reset to patched version
                    run_command(f"git checkout {commit_sha}", cwd=project_repo_dir, capture_output=True)
                    continue
                
                # Check for import errors without building
                has_no_import_errors, check_msg, errors = compile_and_check_imports(
                    project_repo_dir, modified_test_files, project_name
                )
                
                if not has_no_import_errors:
                    print(f"--- ❌ INVALID BACKPORT: Import errors in buggy version: {check_msg} ---")
                    result_entry = {
                        "index": idx,
                        "commit": commit_sha,
                        "parent": parent_sha,
                        "validation_status": "INVALID_BACKPORT",
                        "validation_reason": "import_error",
                        "error_details": check_msg,
                        "import_errors": errors,
                        "test_targets": {
                            "modified": modified_tests,
                            "added": added_tests,
                            "modified_files": modified_test_files if 'modified_test_files' in locals() else [],
                        }
                    }
                    full_results_data.append(result_entry)
                    with open(results_json, 'w') as f:
                        json.dump(full_results_data, f, indent=2)
                    # Reset to patched version
                    run_command(f"git checkout {commit_sha}", cwd=project_repo_dir, capture_output=True)
                    continue
                
                print(f"--- ✅ {check_msg} - Proceeding with buggy build ---")
            
            # Determine test targets and whether to apply test changes
            buggy_test_targets = all_targets  # Default to all targets
            should_apply_test_changes = False
            
            # If only new test files (no modified tests), skip buggy build entirely
            if len(modified_test_files) == 0 and len(added_tests) > 0 and len(modified_tests) == 0:
                print(f"--- Only new tests added (no modified tests). Skipping buggy build/test. ---")
                before_res = {"build": "Skipped", "test": "Skipped (Only New Tests)", "passed": set(), "failed": set()}
            elif len(modified_test_files) > 0:
                # Has modified test files - we already applied and checked them above
                buggy_test_targets = " ".join(modified_tests) if modified_tests else all_targets
                should_apply_test_changes = False  # Already applied in import check, don't re-apply
                print(f"--- Running buggy version (test changes already applied and validated) ---")
                
                before_res = execute_lifecycle(
                    project_name,
                    parent_sha,
                    "buggy",
                    toolkit_dir,
                    project_repo_dir,
                    work_dir,
                    buggy_test_targets,
                    apply_test_changes_from=None,  # Already applied in early import check
                    modified_test_files=None,
                    build_scope=doris_build_scope if project_name == "doris" else None,
                )
            else:
                # Default: run all tests in buggy version
                buggy_test_targets = all_targets
                print(f"--- Running buggy version (establishing baseline) ---")
                
                before_res = execute_lifecycle(
                    project_name,
                    parent_sha,
                    "buggy",
                    toolkit_dir,
                    project_repo_dir,
                    work_dir,
                    buggy_test_targets,
                    apply_test_changes_from=None,
                    modified_test_files=None,
                    build_scope=doris_build_scope if project_name == "doris" else None,
                )
        else:
            print(f"--- Patched version build failed; skipping buggy version ---")
            before_res = {"build": "Skipped", "test": "Skipped (Build Failed)", "passed": set(), "failed": set()}

        fixes = list(before_res["failed"].intersection(after_res["passed"]))
        regressions = list(before_res["passed"].intersection(after_res["failed"]))
        persistent = list(before_res["failed"].intersection(after_res["failed"]))
        all_tests_before = before_res["passed"].union(before_res["failed"])
        new_passes = list(after_res["passed"].difference(all_tests_before))

        # Determine validation status
        validation_status = "VALID_BACKPORT"
        validation_reason = None
        
        if before_res.get("error_type") == "import_error":
            validation_status = "INVALID_BACKPORT"
            validation_reason = "import_error_in_buggy"
        elif before_res.get("build") == "Fail" and after_res.get("build") == "Success":
            validation_status = "VALID_BACKPORT"
            validation_reason = "build_fixed"
        elif len(fixes) > 0:
            validation_status = "VALID_BACKPORT"
            validation_reason = "tests_fixed"
        
        result_entry = {
            "index": idx,
            "commit": commit_sha,
            "parent": parent_sha,
            "validation_status": validation_status,
            "validation_reason": validation_reason,
            "test_targets": {
                "modified": modified_tests,
                "added": added_tests,
                "modified_files": modified_test_files if 'modified_test_files' in locals() else [],
                "all": all_targets
            },
            "build_status_after": after_res["build"],
            "test_status_after": after_res["test"],
            "build_status_before": before_res["build"],
            "test_status_before": before_res["test"],
            "error_info": {
                "before_error_type": before_res.get("error_type"),
                "before_error_msg": before_res.get("error_msg"),
                "import_errors": before_res.get("import_errors", [])
            },
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
            "validation_status": validation_status,
            "validation_reason": validation_reason or "",
            "build_after": after_res["build"],
            "test_after": after_res["test"],
            "build_before": before_res["build"],
            "test_before": before_res["test"],
            "error_type": before_res.get("error_type", ""),
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

        # Reset git repo to clean state after each commit
        print(f"--- Resetting git repository to clean state ---")
        run_command(f"git reset --hard HEAD", cwd=project_repo_dir, check=False, capture_output=True)
        run_command(f"git clean -fd", cwd=project_repo_dir, check=False, capture_output=True)
        run_command(f"git checkout {commit_sha}", cwd=project_repo_dir, check=False, capture_output=True)

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


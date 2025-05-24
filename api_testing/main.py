"""CLI for the REST API Testing Framework.

This module provides the main entry point and both interactive and scripted flows:
- Parses command-line arguments (--app, --env, --tags, --cookie)
- Allows selecting applications, environments, and actions interactively
- Executes test suites and displays colored output via TestRunner and Rich Console
- Generates standalone HTML reports using generate_html_report
- Supports dynamic app registration and integration test generation
"""
import argparse
import os
from pathlib import Path
import re
from . import config
from .api_tester import ApiTester
from colorama import Fore, Style, init
from datetime import datetime
from .utils.report_utils import generate_html_report
from rich.console import Console
import subprocess
import sys

# Initialize colorama
init()

console = Console()

def print_colored(text, color):
    """Print text with color"""
    print(f"{color}{text}{Style.RESET_ALL}")

def update_config_py(app_name, envs, base_path):
    """Insert new app entry into APPLICATIONS dict in config.py."""
    from pathlib import Path
    config_path = Path(__file__).parent / 'config.py'
    text = config_path.read_text()
    lines = text.splitlines()
    # locate APPLICATIONS start
    start_idx = None
    for idx, line in enumerate(lines):
        if line.strip().startswith('APPLICATIONS'):
            start_idx = idx
            break
    if start_idx is None:
        print("Error: 'APPLICATIONS' not found in config.py")
        return
    # find end of APPLICATIONS dict
    depth = 0
    end_idx = None
    for idx in range(start_idx, len(lines)):
        depth += lines[idx].count('{') - lines[idx].count('}')
        if depth == 0:
            end_idx = idx
            break
    if end_idx is None:
        print("Error: Could not find end of APPLICATIONS dict")
        return
    # ensure previous non-blank entry ends with comma
    prev_idx = end_idx - 1
    # skip blank lines
    while prev_idx >= 0 and not lines[prev_idx].strip():
        prev_idx -= 1
    if prev_idx >= 0:
        prev = lines[prev_idx]
        if not prev.rstrip().endswith(','):
            lines[prev_idx] = prev + ','
    # build new entry block with proper indentation
    ind1 = '    '
    ind2 = ind1 * 2
    ind3 = ind1 * 3
    block = [
        f"{ind1}'{app_name}': {{",
        f"{ind2}'description': '{app_name} API',",
        f"{ind2}'environments': {{"
    ]
    for key, url in envs.items():
        block.append(f"{ind3}'{key}': '{url}',")
    # determine relative path for config base_path
    tests_base = Path(__file__).parent.parent / 'tests'
    try:
        rel = base_path.relative_to(tests_base)
    except Exception:
        try:
            rel = base_path.relative_to(Path(os.getcwd()))
        except Exception:
            rel = Path(base_path).name
    path_str = rel.as_posix()
    block.extend([
        f"{ind2}}},",
        f"{ind2}'valid_environments': {list(envs.keys())},",
        f"{ind2}'base_path': TESTS_BASE_DIR / '{path_str}'",
        f"{ind1}}},"
    ])
    # insert and save
    new_lines = lines[:end_idx] + block + lines[end_idx:]
    config_path.write_text('\n'.join(new_lines) + '\n')

def gather_new_app_info():
    """Prompt for new app details and return (app_name, envs, base_path)."""
    import re, os
    from pathlib import Path
    while True:
        new_app = input("Enter new app name (no spaces; only '_' allowed): ").strip()
        # Validate format
        if not re.match(r'^[A-Za-z0-9_]+$', new_app):
            print("Invalid format. Try again.")
            continue
        # Prevent duplicates
        if new_app in config.APPLICATIONS:
            print(f"Application '{new_app}' already exists. Please enter a different name.")
            continue
        break
    new_envs = {}
    while True:
        while True:
            env_nm = input("Enter environment name (no spaces; only '_' allowed): ").strip()
            if re.match(r'^[A-Za-z0-9_]+$', env_nm):
                break
            print("Invalid format. Try again.")
        env_url = input(f"Enter URL for environment '{env_nm}': ").strip()
        new_envs[env_nm] = env_url
        if input("Add another environment? (y/n): ").strip().lower() not in ("y","yes"):
            break
    # Prompt for a valid existing directory to host test cases
    while True:
        base_dir = input("Enter existing directory to create test cases in: ").strip()
        bp = Path(base_dir)
        if not bp.is_absolute():
            bp = Path(os.getcwd()) / bp
        if not bp.exists() or not bp.is_dir():
            print("Directory does not exist. Please enter a valid directory.")
            continue
        break
    # Prepare 'api_integration_tests' subfolder inside provided directory
    integration_folder = bp / 'api_integration_tests'
    if integration_folder.exists():
        print(f"Using existing folder: {integration_folder}")
    else:
        integration_folder.mkdir(parents=True)
        print(f"Created folder: {integration_folder}")
    return new_app, new_envs, integration_folder

def register_new_app(app_name, envs, base_path):
    """Register new application in in-memory config."""
    config.APPLICATIONS[app_name] = {
        "description": f"{app_name} API",
        "environments": envs,
        "valid_environments": list(envs.keys()),
        "base_path": base_path
    }
    for env_nm in envs:
        if env_nm not in config.VALID_ENVIRONMENTS:
            config.VALID_ENVIRONMENTS.append(env_nm)

def prompt_generate_integration(base_path: Path):
    """
    Prompt for and generate integration testcases via standalone script.
    """
    script_path = Path(__file__).parent.parent / 'scripts' / 'generate_integration_tests.py'
    while input("Generate sample integration testcases? (y/n): ").strip().lower() in ('y','yes'):
        unit_file = input("Enter path to the unit test Python file (.py): ").strip()
        unit_path = Path(unit_file).resolve()
        if not unit_path.exists() or not unit_path.is_file() or unit_path.suffix.lower() != '.py':
            print("Invalid file; please try again.")
            continue
        try:
            rel_dir = unit_path.parent.relative_to(base_path.parent)
        except Exception:
            rel_dir = Path()
        out_dir = base_path / rel_dir
        subprocess.run([sys.executable, str(script_path), str(unit_path), '--output-dir', str(out_dir)], check=True)
        print(f"Integration tests generated under {out_dir}")
        if input("Generate another integration testcases? (y/n): ").strip().lower() not in ('y','yes'):
            break
    return

def select_application() -> str:
    while True:
        print("Select application:")
        apps = list(config.APPLICATIONS.keys()) + ["AddMeToYourFamily"]
        for i, a in enumerate(apps, 1):
            print(f"{i}. {a}")
        choice = input("Enter number or name: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(apps):
            selected = apps[int(choice)-1]
        elif choice in apps:
            selected = choice
        else:
            print("Invalid selection, try again.")
            continue
        if selected == "AddMeToYourFamily":
            console.print(
                "[italic cyan]*********************************************************\n\n"
                "Glad you want to be part of api-tester family!\n"
                "Together, we can build a beautiful world by doing our best to prevent problems before they arise. "
                "I know I’m not perfect, so please don’t hesitate to share your feedback, together, we can make things better.\n\n"
                "Now, take a deep breath, put that wonderful smile on your face, and let’s get started.\n"
                "Together, we’ve got this!\n\n"
                "**********************************************************\n\n",
                style="italic"
            )
            yn = input("Configure new app? (y/n): ").strip().lower()
            if yn in ("y","yes"):
                new_app, new_envs, base_path = gather_new_app_info()
                register_new_app(new_app, new_envs, base_path)
                if input("Write new app to config.py? (y/n): ").strip().lower() in ("y","yes"):
                    update_config_py(new_app, new_envs, base_path)
                    print("config.py updated with new app entry.")
                    prompt_generate_integration(base_path)
                else:
                    print("Exiting without writing to config.py.")
            continue
        return selected

def select_environment(app: str) -> str:
    while True:
        envs = config.APPLICATIONS[app]["valid_environments"]
        print("Select environment:")
        for i, e in enumerate(envs, 1):
            print(f"{i}. {e}")
        choice = input("Enter number or name: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(envs):
            return envs[int(choice)-1]
        elif choice in envs:
            return choice
        else:
            print("Invalid selection, try again.")

def prompt_tags(args) -> None:
    if not args.tags:
        tags_input = input("Enter tags to filter tests (space-separated), or press enter to run all: ").strip()
        args.tags = tags_input.split() if tags_input else []

def prompt_cookie(args) -> None:
    if not args.cookie:
        cookie_input = input("Enter cookie header value to include in requests (or press enter to skip): ").strip()
        args.cookie = cookie_input if cookie_input else None

def discover_test_files(base_path: Path) -> list[str]:
    files = []
    for path in Path(base_path).rglob('*.yaml'):
        if path.is_file():
            files.append(str(path))
    return files

def run_test_suites(test_files: list[str], env: str, app: str, cookie: str, tags: list[str]):
    """
    Execute run_test_suite for each file and return (results_by_file, results, base_url).
    """
    results_by_file = {}
    results = {}
    base_url = None
    for test_file in test_files:
        try:
            tester = ApiTester(env, app, cookie)
            file_results = tester.run_test_suite(test_file, tags)
            results_by_file[test_file] = file_results
            results.update(file_results)
            base_url = tester.test_runner.base_url
        except Exception as e:
            print(f"Error running tests in {test_file}: {str(e)}")
    return results_by_file, results, base_url

def print_test_results(results: dict[str, dict], env: str, app: str, base_url: str):
    """
    Display the aggregated and per-test results, plus summary statistics.
    """
    total_tests = len(results)
    passed = sum(1 for result in results.values() if result['status'])
    failed = total_tests - passed

    print("\nOverall Test Results:")
    print(f"Environment: {env}")
    print(f"Application: {app}")
    print(f"Base URL: {base_url}")

    print("\nIndividual Test Results:")
    for test_name, result in results.items():
        checkmark = u"\u2713" if result['status'] else u"\u2717"
        color = Fore.GREEN if result['status'] else Fore.RED
        error = f" - {result['error']}" if result['error'] else ""
        print(f"{color}{checkmark}{Style.RESET_ALL} {test_name}{error}")

    print("\nTest Statistics:")
    print_colored(f"Total Tests: {total_tests}", Fore.CYAN)
    print_colored(f"Passed: {passed}", Fore.GREEN)
    print_colored(f"Failed: {failed}", Fore.RED)
    # Avoid ZeroDivisionError when no tests were run
    pass_rate = (passed/total_tests)*100 if total_tests > 0 else 0.0
    print_colored(f"Pass Rate: {pass_rate:.1f}%", Fore.YELLOW)

def handle_action_flow(app: str) -> None:
    """Prompt user to run tests or generate integration testcases."""
    while True:
        print("What do you want to do?")
        print("1. Run Integration Tests")
        print("2. Generate Integration Testcases for Your App")
        choice = input("Enter choice [1/2]: ").strip()
        if choice == '1':
            return
        elif choice == '2':
            app_config = config.APPLICATIONS[app]
            prompt_generate_integration(app_config['base_path'])
            sys.exit(0)
        else:
            print("Invalid selection. Please choose 1 or 2.")

def execute_args_flow(args) -> bool:
    """If both --app and --env are provided and valid, run tests and generate report."""
    if args.app and args.app in config.APPLICATIONS \
       and args.env and args.env in config.APPLICATIONS[args.app]['valid_environments']:
        app = args.app
        env = args.env
        tags = args.tags or []
        cookie = args.cookie
        app_config = config.APPLICATIONS[app]
        test_files = discover_test_files(app_config['base_path'])
        if not test_files:
            print(f"Error: No test files found in application directory: {app_config['base_path']}")
            sys.exit(1)
        results_by_file, results, base_url = run_test_suites(test_files, env, app, cookie, tags)
        print_test_results(results, env, app, base_url)
        generate_html_report(app, env, tags, datetime.now(), results, results_by_file, base_url)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description='REST API Testing Framework')
    parser.add_argument('--env', help='Environment to run tests against (e.g. dev/staging/prod)')
    parser.add_argument('--app', help='Application to test (e.g. users/products/orders)')
    parser.add_argument('--tags', nargs='*', help='Run tests with specific tags')
    parser.add_argument('--cookie', help='Raw Cookie header value to include in all requests')
    args = parser.parse_args()
    # Validate provided app
    if args.app and args.app not in config.APPLICATIONS:
        print(f"Error: Application '{args.app}' is not recognized.")
        sys.exit(1)
    # Validate provided env for the app
    if args.env and args.app and args.app in config.APPLICATIONS and \
       args.env not in config.APPLICATIONS[args.app]['valid_environments']:
        print(f"Error: Environment '{args.env}' is not valid for application '{args.app}'.")
        sys.exit(1)

    # Enforce mandatory --env when --app is provided
    if args.app and not args.env:
        print("Error: --env is mandatory when --app is provided.")
        sys.exit(1)

    # Auto-run via CLI args
    if execute_args_flow(args):
        return

    # Interactive flow
    if not args.app or args.app not in config.APPLICATIONS:
        args.app = select_application()
    handle_action_flow(args.app)
    args.env = args.env or select_environment(args.app)

    prompt_tags(args)

    prompt_cookie(args)

    app = args.app
    env = args.env
    tags = args.tags or []
    cookie = args.cookie

    # Get application configuration
    app_config = config.APPLICATIONS[app]
    # Find all test files in the application directory
    test_files = discover_test_files(app_config['base_path'])

    if not test_files:
        print(f"Error: No test files found in application directory: {app_config['base_path']}")
        return 1

    print(f"\nFound {len(test_files)} test files in application {args.app}")
    print("Test files:")
    for test_file in test_files:
        print(f"  {os.path.relpath(test_file, app_config['base_path'])}")

    # Run tests and print results
    results_by_file, results, base_url = run_test_suites(test_files, env, app, cookie, tags)
    print_test_results(results, env, app, base_url)
    # Generate HTML report
    generate_html_report(app, env, tags, datetime.now(), results, results_by_file, base_url)

if __name__ == "__main__":
    main()

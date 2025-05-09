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
        if re.match(r'^[A-Za-z0-9_]+$', new_app):
            break
        print("Invalid format. Try again.")
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
    # Create 'api_integration_tests' subfolder inside provided directory
    integration_folder = bp / 'api_integration_tests'
    integration_folder.mkdir(parents=True, exist_ok=True)
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

def main():
    parser = argparse.ArgumentParser(description='REST API Testing Framework')
    parser.add_argument('--env', help='Environment to run tests against (e.g. dev/staging/prod)')
    parser.add_argument('--app', help='Application to test (e.g. users/products/orders)')
    parser.add_argument('--tags', nargs='*', help='Run tests with specific tags')
    parser.add_argument('--cookie', help='Raw Cookie header value to include in all requests')
    args = parser.parse_args()

    # Prompt for missing application (with “Not in list” and dynamic config)
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
            if yn not in ("y","yes"):
                continue
            # Gather and register new application
            new_app, new_envs, base_path = gather_new_app_info()
            register_new_app(new_app, new_envs, base_path)
            # Confirm writing to config.py
            confirm = input("Write new app to config.py? (y/n): ").strip().lower()
            if confirm in ('y','yes'):
                update_config_py(new_app, new_envs, base_path)
                print("config.py updated with new app entry.")
            else:
                print("Exiting without writing to config.py.")
            return
        else:
            args.app = selected
        if args.app:
            break

    # Prompt for missing environment (per application)
    while not args.env:
        envs = config.APPLICATIONS[args.app]["valid_environments"]
        print("Select environment:")
        for i, e in enumerate(envs, 1):
            print(f"{i}. {e}")
        choice = input("Enter number or name: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(envs):
            args.env = envs[int(choice)-1]
        elif choice in envs:
            args.env = choice
        else:
            print("Invalid selection, try again.")

    # Prompt for missing tags if not provided
    if not args.tags:
        tags_input = input("Enter tags to filter tests (space-separated), or press enter to run all: ").strip()
        args.tags = tags_input.split() if tags_input else []
    # Prompt for missing cookie header if not provided
    if not args.cookie:
        cookie_input = input("Enter cookie header value to include in requests (or press enter to skip): ").strip()
        args.cookie = cookie_input if cookie_input else None
    # Prepare tags for report summary
    tags_str = ", ".join(args.tags) if args.tags else "-"

    start_time = datetime.now()

    # Get application configuration
    app_config = config.APPLICATIONS[args.app]
    
    # Find all test files in the application directory
    test_files = []
    for path in Path(app_config['base_path']).rglob('*.yaml'):
        if path.is_file():
            test_files.append(str(path))

    if not test_files:
        print(f"Error: No test files found in application directory: {app_config['base_path']}")
        return 1

    print(f"\nFound {len(test_files)} test files in application {args.app}")
    print("Test files:")
    for test_file in test_files:
        print(f"  {os.path.relpath(test_file, app_config['base_path'])}")

    # Run tests for each file
    results_by_file = {}
    results = {}
    for test_file in test_files:
        try:
            tester = ApiTester(args.env, args.app, args.cookie)
            file_results = tester.run_test_suite(test_file, args.tags)
            results_by_file[test_file] = file_results
            results.update(file_results)
        except Exception as e:
            print(f"Error running tests in {test_file}: {str(e)}")
            continue

    # Calculate statistics
    total_tests = len(results)
    passed = sum(1 for result in results.values() if result['status'])
    failed = total_tests - passed

    # Print overall results
    print("\nOverall Test Results:")
    print(f"Environment: {args.env}")
    print(f"Application: {args.app}")
    print(f"Base URL: {tester.test_runner.base_url}")
    print("\nIndividual Test Results:")

    # Print test results with checkmarks
    for test_name, result in results.items():
        checkmark = u"\u2713" if result['status'] else u"\u2717"
        color = Fore.GREEN if result['status'] else Fore.RED
        error = f" - {result['error']}" if result['error'] else ""
        print(f"{color}{checkmark}{Style.RESET_ALL} {test_name}{error}")

    # Print statistics
    print("\nTest Statistics:")
    print_colored(f"Total Tests: {total_tests}", Fore.CYAN)
    print_colored(f"Passed: {passed}", Fore.GREEN)
    print_colored(f"Failed: {failed}", Fore.RED)
    print_colored(f"Pass Rate: {((passed/total_tests)*100):.1f}%", Fore.YELLOW)

    # Generate HTML report
    generate_html_report(args.app, args.env, args.tags, start_time, results, results_by_file, tester.test_runner.base_url)

if __name__ == "__main__":
    main()

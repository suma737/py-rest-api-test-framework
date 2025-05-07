import argparse
import os
from pathlib import Path
from . import config
from .api_tester import ApiTester
from colorama import Fore, Style, init
from datetime import datetime
from .utils.report_utils import generate_html_report

# Initialize colorama
init()

def print_colored(text, color):
    """Print text with color"""
    print(f"{color}{text}{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description='REST API Testing Framework')
    parser.add_argument('--env', required=True, choices=config.VALID_ENVIRONMENTS,
                      help='Environment to run tests against (dev/staging/prod)')
    parser.add_argument('--app', required=True, choices=list(config.APPLICATIONS.keys()),
                      help='Application to test (users/products/orders)')
    parser.add_argument('--tags', nargs='*', help='Run tests with specific tags')
    parser.add_argument('--cookie', help='Raw Cookie header value to include in all requests')
    args = parser.parse_args()

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

#!/usr/bin/env python

import sys
import os
import argparse
from pathlib import Path

# Ensure project root is on Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, project_root)

from api_testing import config
from api_testing.core.runner import TestRunner

def main():
    parser = argparse.ArgumentParser(description='Run API tests')
    parser.add_argument('--app', required=True,
                        choices=list(config.APPLICATIONS.keys()),
                        help='Application to test')
    parser.add_argument('--env', required=True,
                        choices=config.VALID_ENVIRONMENTS,
                        help='Environment to test against')
    args = parser.parse_args()

    # Derive base URL and discover test files
    app_conf = config.APPLICATIONS[args.app]
    base_url = app_conf['environments'][args.env]
    test_dir = app_conf['base_path']
    test_files = [str(p) for p in Path(test_dir).rglob('*.yaml') if p.is_file()]

    if not test_files:
        print(f"Error: No test files found for application {args.app} in {test_dir}")
        sys.exit(1)

    # Run tests file-by-file
    runner = TestRunner(base_url)
    for test_file in test_files:
        results = runner.run_test_suite(test_file)
        # Here you could print or log per-file results

if __name__ == "__main__":
    main()

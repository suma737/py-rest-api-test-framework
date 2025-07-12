"""ApiTester provides a high-level interface for running API test suites.

It validates environment and application names against the global config,
initializes a TestRunner with optional cookie support,
and exposes run_test_suite() to execute YAML test files with tag filtering.
"""
import os
from typing import Dict, Any, Optional
from pathlib import Path
from . import config
from .core.runner import TestRunner

class ApiTester:
    """Validates inputs and delegates test suite execution to the underlying TestRunner."""
    def __init__(self, env: str, app: str, cookie: Optional[str] = None):
        """
        Initialize API tester with environment and application
        
        Args:
            env: Environment (dev/staging/prod)
            app: Application name (users/products/orders)
            cookie: Raw Cookie header value to include in all requests
        """
        if app not in config.APPLICATIONS:
            raise ValueError(f"Invalid application: {app}. Must be one of: {list(config.APPLICATIONS.keys())}")
            
        app_config = config.APPLICATIONS[app]
        
        # Validate environment for this specific application
        if env not in app_config['valid_environments']:
            valid_envs = ", ".join(app_config['valid_environments'])
            raise ValueError(f"Invalid environment '{env}' for application '{app}'. "
                           f"Valid environments are: {valid_envs}")
            
        # Get the application-specific base URL for the environment
        base_url = app_config['environments'][env]
        # Determine test data file location ( <app_base_path>/testdata/test_data.json )
        test_data_file = app_config['base_path'] / 'testdata' / 'test_data.json'
        self.test_runner = TestRunner(base_url, cookie, env=env, test_data_file=test_data_file)

    def run_test_suite(self, test_suite_path: str, include_tags: list = None) -> Dict:
        """
        Run test suite with optional tag filtering
        
        Args:
            test_suite_path: Path to the YAML test suite file
            include_tags: List of tags to include. If None, run all tests
            
        Returns:
            Dictionary of test results
        """
        return self.test_runner.run_test_suite(test_suite_path, include_tags)

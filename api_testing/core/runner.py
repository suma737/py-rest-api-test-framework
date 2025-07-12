"""Core TestRunner orchestrates API test suite execution.

This module provides the TestRunner class which:
- Initializes and configures an HTTP session (with optional cookie support)
- Wraps requests to capture headers and data for logging
- Discovers, loads, and filters YAML test cases with variable substitution
- Executes precondition scripts and issues HTTP calls
- Validates responses (status, JSON schema, business rules) via ResponseValidator
- Extracts variables from responses for chained tests
- Aggregates and returns TestResult objects for reporting and downstream processing
"""

import requests
import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import urljoin
import json
import os
import subprocess
from jsonschema import validate, ValidationError
from .base import TestResult, HttpMethod
from .validator import ResponseValidator
from ..utils.constants import SCHEMA_VALIDATION_FAILURE
from .. import config

class TestRunner:
    _COMMON_TEST_DATA_CACHE: Dict[str, Dict[str, Any]] = {}  # Cache keyed by absolute file path

    def __init__(self, base_url: str, cookie: Optional[str] = None, env: str = 'default', test_data_file: Optional[Path] = None):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.env = env
        if test_data_file is None:
            raise ValueError("test_data_file must be provided via ApiTester; global TEST_DATA_FILE was removed.")
        self.test_data_file: Path = test_data_file
        self.session = requests.Session()
        # Add Cookie header if provided
        if cookie:
            self.session.headers.update({'Cookie': cookie})
        # Wrap session.request to capture headers and data
        orig_request = self.session.request
        def capture_request(method, url, headers=None, params=None, json=None, **kwargs):
            merged_headers = dict(self.session.headers)
            if headers:
                merged_headers.update(headers)
            self.last_request_headers = merged_headers
            self.last_request_data = json if json is not None else params
            return orig_request(method=method, url=url, headers=headers, params=params, json=json, **kwargs)
        self.session.request = capture_request
        self.validator = ResponseValidator()

    def _get_common_test_data(self) -> Dict[str, Any]:
        """Load and cache the common JSON test data for this runner instance."""
        file_path = self.test_data_file.resolve()
        cache_key = str(file_path)
        if cache_key in self._COMMON_TEST_DATA_CACHE:
            return self._COMMON_TEST_DATA_CACHE[cache_key]
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}
        self._COMMON_TEST_DATA_CACHE[cache_key] = data
        return data

    def _replace_variables(self, value: str, variables: Dict) -> str:
        """
        Replace $VARIABLE patterns in a string with their values
        """
        if not isinstance(value, str):
            return value
            
        # If the entire string is a placeholder, return original value with correct type
        for var_name, var_value in variables.items():
            placeholder = f'${{{var_name}}}'
            if value == placeholder:
                return var_value
            brace_placeholder = f'{{{var_name}}}'
            if value == brace_placeholder:
                return var_value
        # Otherwise, perform string replacement
        for var_name, var_value in variables.items():
            # replace ${VAR}
            placeholder = f'${{{var_name}}}'
            value = value.replace(placeholder, str(var_value))
            # replace {VAR}
            brace_placeholder = f'{{{var_name}}}'
            value = value.replace(brace_placeholder, str(var_value))
        return value

    def _replace_variables_dict(self, data: Dict, variables: Dict) -> Dict:
        """
        Recursively replace variables in a dictionary
        """
        if not isinstance(data, dict):
            return data
            
        new_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                new_data[key] = self._replace_variables_dict(value, variables)
            elif isinstance(value, list):
                new_data[key] = self._replace_variables_list(value, variables)
            else:
                new_data[key] = self._replace_variables(str(value), variables)
        return new_data

    def _replace_variables_list(self, data: List, variables: Dict) -> List:
        """
        Recursively replace variables in a list
        """
        if not isinstance(data, list):
            return data
            
        new_data = []
        for item in data:
            if isinstance(item, dict):
                new_data.append(self._replace_variables_dict(item, variables))
            elif isinstance(item, list):
                new_data.append(self._replace_variables_list(item, variables))
            else:
                new_data.append(self._replace_variables(str(item), variables))
        return new_data

    def _extract_variables(self, response_data: Dict, extract_config: Dict, variables: Dict) -> None:
        """
        Extract variables from response data based on configuration
        """
        for var_name, path in extract_config.items():
            # Split path into components
            path_components = path.split('.')
            current_data = response_data
            
            try:
                for component in path_components:
                    # handle list indexing if current_data is a list
                    if isinstance(current_data, list) and component.isdigit():
                        current_data = current_data[int(component)]
                    else:
                        current_data = current_data[component]
                variables[var_name] = current_data
            except (KeyError, TypeError, IndexError):
                print(f"Warning: Could not extract variable {var_name} from path {path}")

    def _filter_tests_by_tags(self, test_cases: List, include_tags: List[str], file_tags: List[str]) -> List:
        """
        Filter test cases based on tags
        
        Args:
            test_cases: List of test cases
            include_tags: List of tags to include. If None, include all tests
            file_tags: List of tags from the test file level
            
        Returns:
            Filtered list of test cases
        """
        if not include_tags:
            return test_cases
            
        filtered_tests = []
        for test in test_cases:
            # Get all tags for this test (file-level + test-level)
            test_tags = test.get('tags', [])
            if file_tags:
                test_tags.extend(file_tags)
            
            # Check if any of the test tags match the include tags
            if any(tag in test_tags for tag in include_tags):
                filtered_tests.append(test)
        return filtered_tests

    # ===== Refactored run_test into smaller helpers =====

    def _init_variables(self, default_config: Dict = None) -> Dict[str, Any]:
        """Initialize variables by merging common JSON data and test-file variables.

        Precedence:
        1) Common JSON variables (env-specific)
        2) Variables defined in the YAML test file (`testData` section)
        """
        variables: Dict[str, Any] = {}

        # Load common data
        # Load and preprocess common data
        raw_common = self._get_common_test_data()
        common_data = raw_common.get('testdata', raw_common)

        env_key = self.env
        for var_name, var_val in common_data.items():
            # Resolve env layer if dict
            chosen_val = None
            if isinstance(var_val, dict):
                chosen_val = (
                    var_val.get(env_key)
                    or var_val.get(env_key.lower())
                    or var_val.get(env_key.upper())
                    or var_val.get('default')
                )
            else:
                chosen_val = var_val

            if chosen_val is None:
                continue

            # If the resolved value is a dict, flatten like YAML testData convention
            if isinstance(chosen_val, dict):
                def _dot_flatten(prefix: str, data: Dict):
                    for sk, sv in data.items():
                        full_key = f"{prefix}.{sk}" if prefix else sk
                        if isinstance(sv, dict):
                            _dot_flatten(full_key, sv)
                        elif isinstance(sv, list):
                            for idx, item in enumerate(sv):
                                _dot_flatten(f"{full_key}.{idx}", item) if isinstance(item, dict) else variables[f"{full_key}.{idx}"] == item
                        else:
                            variables[full_key] = sv
                _dot_flatten(var_name, chosen_val)
            else:
                variables[var_name] = chosen_val

        # Override with variables from the test file if provided
        if default_config and 'variables' in default_config:
            variables.update(default_config['variables'])
        return variables

    def _run_preconditions(self, test_case: Dict, variables: Dict) -> Optional[TestResult]:
        if 'preconditions' not in test_case:
            return None
        for pre in test_case['preconditions']:
            if 'script' in pre:
                script_path = Path(pre['script'])
                if not script_path.is_absolute():
                    script_path = Path.cwd() / script_path
                cmd = ['python', str(script_path)]
                if 'args' in pre:
                    cmd.extend(pre['args'])
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      env={**os.environ, 'API_BASE_URL': self.base_url})
                if proc.returncode != 0:
                    return TestResult(status=False, response={}, error=f"PRECONDITION_SCRIPT_FAILED: {proc.stderr.strip()}")
                try:
                    script_vars = json.loads(proc.stdout)
                    variables.update(script_vars)
                except Exception as e:
                    return TestResult(status=False, response={}, error=f"PRECONDITION_SCRIPT_JSON_ERROR: {e}")
            else:
                pre_url = self._replace_variables(pre.get('url',''), variables)
                if pre_url and not pre_url.startswith('/'):
                    pre_url = f"/{pre_url}"
                full_pre = urljoin(self.base_url, pre_url)
                headers = self._replace_variables_dict(pre.get('headers', {}), variables)
                params = self._replace_variables_dict(pre.get('params', {}), variables)
                data = self._replace_variables_dict(pre.get('data', {}), variables)
                method = HttpMethod(pre.get('method', 'GET'))
                resp = self.session.request(method=method.value, url=full_pre,
                                            headers=headers, params=params, json=data)
                try:
                    resp_data = resp.json()
                except ValueError:
                    resp_data = {}
                if 'extract_variables' in pre:
                    self._extract_variables(resp_data, pre['extract_variables'], variables)
        return None

    def _prepare_request(self, test_case: Dict, variables: Dict) -> tuple:
        url = test_case.get('url','')
        if url:
            url = self._replace_variables(url, variables)
            if not url.startswith('/'):
                url = f"/{url}"
        full_url = urljoin(self.base_url, url)
        headers = self._replace_variables_dict(test_case.get('headers', {}), variables)
        params = self._replace_variables_dict(test_case.get('params', {}), variables)
        data = self._replace_variables_dict(test_case.get('data', {}), variables)
        method = HttpMethod(test_case.get('method', 'GET'))
        return method.value, full_url, headers, params, data

    def _execute_request(self, method: str, full_url: str, headers: Dict, params: Dict, data: Any) -> tuple:
        response = self.session.request(method=method, url=full_url,
                                        headers=headers, params=params, json=data)
        return response, response.url

    def _extract_response_data(self, response) -> Dict:
        try:
            return response.json()
        except ValueError:
            return {}

    def _validate_status(self, response, test_case: Dict, response_data: Dict, actual_url: str) -> Optional[TestResult]:
        exp = test_case.get('expected_status')
        if exp is not None and response.status_code != exp:
            return TestResult(
                status=False,
                response=response_data,
                error=f"EXPECTED_STATUS_MISMATCH: expected {exp}, got {response.status_code}",
                request_url=actual_url
            )
        return None

    def _prepare_expected_response(self, test_case: Dict, variables: Dict) -> None:
        expected = test_case.get('expected_response', {})
        expected = self._replace_variables_dict(expected, variables)
        test_case['expected_response'] = expected

    def _handle_schema_validation(self, response_data: Dict, test_case: Dict, actual_url: str) -> TestResult:
        # Use central validator to handle AI/Flow or static schema generation and validation
        valid, msg = self.validator.validate_response(response_data, test_case)
        if valid:
            return TestResult(status=True, response=response_data, request_url=actual_url)
        return TestResult(status=False, response=response_data, error=msg, request_url=actual_url)

    def _handle_business_validation(self, response_data: Dict, test_case: Dict, actual_url: str) -> TestResult:
        valid, msg = self.validator.validate_response(response_data, test_case)
        if valid:
            return TestResult(status=True, response=response_data, request_url=actual_url)
        return TestResult(status=False, response=response_data, error=msg, request_url=actual_url)

    def run_test(self, test_case: Dict, default_config: Dict = None) -> TestResult:
        try:
            variables = self._init_variables(default_config)
            pre_err = self._run_preconditions(test_case, variables)
            if pre_err:
                return pre_err

            method, full_url, headers, params, data = self._prepare_request(test_case, variables)
            response, actual_url = self._execute_request(method, full_url, headers, params, data)

            data = self._extract_response_data(response)
            status_err = self._validate_status(response, test_case, data, actual_url)
            if status_err:
                return status_err

            self._extract_variables(data, test_case.get('extract_variables', {}), variables)
            self._prepare_expected_response(test_case, variables)

            if 'schema' in test_case:
                return self._handle_schema_validation(data, test_case, actual_url)
            return self._handle_business_validation(data, test_case, actual_url)
        except Exception as e:
            return TestResult(status=False, response={}, error=str(e))

    def run_test_suite(self, test_suite_path: str, include_tags: List[str] = None) -> Dict:
        """
        Run test suite with optional tag filtering
        
        Args:
            test_suite_path: Path to the YAML test suite file
            include_tags: List of tags to include. If None, run all tests
            
        Returns:
            Dictionary of test results
        """
        with open(test_suite_path, 'r') as file:
            test_data = yaml.safe_load(file)
            
            # Extract default configuration if present
            default_config = {}
            if isinstance(test_data, dict):
                if 'base_url' in test_data:
                    default_config['base_url'] = test_data['base_url']
                
                # Load shared testData into variables
                if 'testData' in test_data:
                    td = test_data['testData']
                    default_config['variables'] = {}
                    for var_name, var_value in td.items():
                        if isinstance(var_value, dict):
                            for sub_name, sub_val in var_value.items():
                                default_config['variables'][f"{var_name}{sub_name[0].upper()}{sub_name[1:]}"] = sub_val
                        else:
                            default_config['variables'][var_name] = var_value
                
                # Get file-level tags if present
                file_tags = test_data.get('tags', [])
                
                # Get test cases
                test_cases = test_data.get('test_cases', [])
            else:
                test_cases = test_data
                file_tags = []

        # Filter tests by tags if specified
        if include_tags:
            test_cases = self._filter_tests_by_tags(test_cases, include_tags, file_tags)

        results = {}
        for test in test_cases:
            test_name = test['name']
            result = self.run_test(test, default_config)
            results[test_name] = {
                'status': result.status,
                'response': result.response,
                'error': result.error,
                'request_url': result.request_url,
                'request_headers': getattr(self, 'last_request_headers', {}),
                'request_data': getattr(self, 'last_request_data', None)
            }

        return results

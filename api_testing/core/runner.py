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

class TestRunner:
    def __init__(self, base_url: str, cookie: Optional[str] = None):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
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

    def run_test(self, test_case: Dict, default_config: Dict = None) -> TestResult:
        """
        Execute a single test case
        
        Args:
            test_case: Dictionary containing test case details
            default_config: Default configuration for the test suite
            
        Returns:
            TestResult object
        """
        try:
            # Initialize variables dictionary
            variables = {}
            
            # Store the response for later use
            response_data = None
            
            # Handle preconditions (HTTP or Python scripts) if defined
            if 'preconditions' in test_case:
                for pre in test_case['preconditions']:
                    # Script precondition
                    if 'script' in pre:
                        script_path = Path(pre['script'])
                        if not script_path.is_absolute():
                            script_path = Path.cwd() / script_path
                        # Build script command with optional args
                        cmd = ['python', str(script_path)]
                        if 'args' in pre:
                            cmd.extend(pre.get('args', []))
                        proc = subprocess.run(
                            cmd,
                            capture_output=True, text=True,
                            env={**os.environ, 'API_BASE_URL': self.base_url}
                        )
                        if proc.returncode != 0:
                            return TestResult(status=False, response={}, error=f"PRECONDITION_SCRIPT_FAILED: {proc.stderr.strip()}")
                        try:
                            script_vars = json.loads(proc.stdout)
                            variables.update(script_vars)
                        except Exception as e:
                            return TestResult(status=False, response={}, error=f"PRECONDITION_SCRIPT_JSON_ERROR: {e}")
                        continue
                    # HTTP precondition
                    pre_url = self._replace_variables(pre.get('url', ''), variables)
                    if pre_url and not pre_url.startswith('/'):
                        pre_url = f"/{pre_url}"
                    full_pre_url = urljoin(self.base_url, pre_url)
                    headers = self._replace_variables_dict(pre.get('headers', {}), variables)
                    params = self._replace_variables_list(pre.get('params', {}), variables)
                    data = self._replace_variables_list(pre.get('data', {}), variables)
                    method = HttpMethod(pre.get('method', 'GET'))
                    resp = self.session.request(
                        method=method.value,
                        url=full_pre_url,
                        headers=headers,
                        params=params,
                        json=data
                    )
                    try:
                        resp_data = resp.json()
                    except ValueError:
                        resp_data = {}
                    if 'extract_variables' in pre:
                        self._extract_variables(resp_data, pre['extract_variables'], variables)

            # Get URL - use test case URL if specified, otherwise use default
            url = test_case.get('url', '')
            
            # Replace variables in URL
            if url:
                url = self._replace_variables(url, variables)
                
                # Ensure URL starts with a slash if it's a relative path
                if not url.startswith('/'):
                    url = f"/{url}"
            
            # Join with base URL
            full_url = urljoin(self.base_url, url)
            
            # Replace variables in headers, params, and data
            headers = self._replace_variables_dict(test_case.get('headers', {}), variables)
            params = self._replace_variables_list(test_case.get('params', {}), variables)
            data = self._replace_variables_list(test_case.get('data', {}), variables)

            # Determine HTTP method from test case
            method = HttpMethod(test_case.get('method', 'GET'))

            # Make the request
            response = self.session.request(
                method=method.value,
                url=full_url,
                headers=headers,
                params=params,
                json=data
            )
            
            # capture the actual URL including query parameters
            actual_url = response.url
            
            # Validate HTTP status code
            exp_status = test_case.get('expected_status')
            if exp_status is not None and response.status_code != exp_status:
                return TestResult(
                    status=False,
                    response=response_data if 'response_data' in locals() else {},
                    error=f"EXPECTED_STATUS_MISMATCH: expected {exp_status}, got {response.status_code}",
                    request_url=actual_url
                )
            
            # Store response data for variable extraction
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}
            
            # Extract variables from response
            if 'extract_variables' in test_case:
                self._extract_variables(response_data, test_case['extract_variables'], variables)
            
            # Replace variables in expected response
            expected_response = test_case.get('expected_response', {})
            expected_response = self._replace_variables_dict(expected_response, variables)
            # Update test_case dict with replaced expected_response
            test_case['expected_response'] = expected_response
            
            # JSON Schema validation if provided
            if 'schema' in test_case:
                schema_path = test_case['schema']
                with open(schema_path) as f:
                    schema = yaml.safe_load(f) if schema_path.endswith(('.yaml', '.yml')) else json.load(f)
                try:
                    validate(instance=response_data, schema=schema)
                    return TestResult(status=True, response=response_data, request_url=actual_url)
                except ValidationError as e:
                    # detailed schema error
                    path = ".".join(str(p) for p in e.path) or "<root>"
                    validator = e.validator
                    expected = e.validator_value
                    return TestResult(
                        status=False,
                        response=response_data,
                        error=f"{SCHEMA_VALIDATION_FAILURE} : {e.message} at path '{path}' (validator: {validator}, expected: {expected})",
                        request_url=actual_url
                    )

            validation_result, validation_message = self.validator.validate_response(response_data, test_case)
            if validation_result:
                return TestResult(
                    status=True,
                    response=response_data,
                    request_url=actual_url
                )
            else:
                return TestResult(
                    status=False,
                    response=response_data,
                    error=validation_message,
                    request_url=actual_url
                )

        except Exception as e:
            return TestResult(
                status=False,
                response={},
                error=str(e)
            )

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

import json
from typing import Dict, Any, Union
from ..utils.regex_utils import validate_pattern, validate_regex
import jsonschema
import subprocess
from pathlib import Path
from ..utils.constants import SCHEMA_VALIDATION_FAILURE, PATTERN_DO_NOT_MATCH, MISSING_KEY, INCORRECT_VALUE
from ..utils.ai_schema_agent import generate_schema_with_ai

class ResponseValidator:
    def __init__(self):
        self.validation_modes = {
            'full': self._validate_full_response,
            'partial': self._validate_partial_response,
            'specific': self._validate_specific_value
        }

    def validate_response(self, response: Dict, test_case: Dict) -> tuple[bool, str]:
        """
        Validate the response against the expected response structure
        
        Args:
            response: The actual response from the API
            test_case: The test case containing expected response
            
        Returns:
            tuple: (validation_result, error_message)
        """
        try:
            # JSON Schema validation if 'schema' specified in test case
            schema_path = test_case.get('schema')
            if schema_path:
                return self._validate_schema(response, schema_path)
            
            # Get validation mode from test case (default to 'full')
            validation_mode = test_case.get('validation_mode', 'full')
            
            # Get expected response
            expected = test_case.get('expected_response', {})
            
            # Get specific validation path if using 'specific' mode
            validation_path = test_case.get('validation_path', [])
            
            # Validate based on mode
            if validation_mode == 'specific':
                return self._validate_specific_value(response, expected, validation_path)
            elif validation_mode == 'partial':
                return self._validate_partial_response(response, expected)
            else:  # full mode
                # Handle list responses in full mode
                if isinstance(expected, list):
                    return self._validate_list(response, expected)
                return self._validate_full_response(response, expected)
                
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _validate_full_response(self, actual: Dict, expected: Dict) -> tuple[bool, str]:
        """
        Validate entire response structure and values
        """
        return self._validate_dict(actual, expected)

    def _validate_partial_response(self, actual: Dict, expected: Dict) -> tuple[bool, str]:
        """
        Validate only specified keys in the response
        """
        for key, expected_value in expected.items():
            if key not in actual:
                return False, f"{MISSING_KEY} : Missing key: {key}"
            
            actual_value = actual[key]
            
            if isinstance(expected_value, dict):
                result, error = self._validate_dict(actual_value, expected_value)
                if not result:
                    return False, f"In key {key}: {error}"
            elif isinstance(expected_value, list):
                result, error = self._validate_list(actual_value, expected_value)
                if not result:
                    return False, f"In key {key}: {error}"
            else:
                # Validate primitive values
                # Support boolean literal strings 'true'/'false'
                if isinstance(expected_value, str) and expected_value.lower() in ('true','false'):
                    exp_bool = expected_value.lower() == 'true'
                    # coerce actual to bool
                    if isinstance(actual_value, str):
                        actual_bool = actual_value.lower() == 'true'
                    else:
                        actual_bool = bool(actual_value)
                    if actual_bool != exp_bool:
                        return False, f"{INCORRECT_VALUE} : Value mismatch for key {key}. Expected: {expected_value}, Actual: {actual_value}"
                    continue
                if isinstance(expected_value, str):
                    if expected_value.startswith('pattern:'):
                        pattern_name = expected_value.split(':')[1]
                        # Convert integer to string for pattern validation
                        if isinstance(actual_value, int):
                            actual_value = str(actual_value)
                        if not validate_pattern(pattern_name, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Pattern validation failed for key {key}. Value: {actual_value}"
                    elif expected_value.startswith('regex:'):
                        pattern = expected_value.split(':', 1)[1]
                        # Convert integer to string for regex validation
                        if isinstance(actual_value, int):
                            actual_value = str(actual_value)
                        if not validate_regex(pattern, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Regex validation failed for key {key}. Value: {actual_value}"
                    else:
                        if actual_value != expected_value:
                            return False, f"{INCORRECT_VALUE} : Value mismatch for key {key}. Expected: {expected_value}, Actual: {actual_value}"
                else:
                    if actual_value != expected_value:
                        return False, f"{INCORRECT_VALUE} : Value mismatch for key {key}. Expected: {expected_value}, Actual: {actual_value}"
        
        return True, ""

    def _validate_specific_value(self, response: Dict, expected_value: Any, path: Union[list, str]) -> tuple[bool, str]:
        """
        Validate a specific value in the response using a path
        
        Args:
            response: The actual response from the API
            expected_value: The expected value to validate against
            path: List of keys to navigate through the response
            
        Returns:
            tuple: (validation_result, error_message)
        """
        # allow dot-notation string for path
        if isinstance(path, str):
            path = path.split('.')
        try:
            current = response
            for key in path:
                if not isinstance(current, dict):
                    return False, f"Invalid path: {path}. Current value is not a dictionary"
                if key not in current:
                    return False, f"Invalid path: {path}. Key {key} not found"
                current = current[key]
            
            # Validate the final value
            if isinstance(expected_value, str):
                if expected_value.startswith('pattern:'):
                    pattern_name = expected_value.split(':')[1]
                    if not validate_pattern(pattern_name, current):
                        return False, f"{PATTERN_DO_NOT_MATCH} : Pattern validation failed. Value: {current}"
                elif expected_value.startswith('regex:'):
                    pattern = expected_value.split(':', 1)[1]
                    if not validate_regex(pattern, current):
                        return False, f"{PATTERN_DO_NOT_MATCH} : Regex validation failed. Value: {current}"
                else:
                    if current != expected_value:
                        return False, f"{INCORRECT_VALUE} : Value mismatch. Expected: {expected_value}, Actual: {current}"
            else:
                if current != expected_value:
                    return False, f"{INCORRECT_VALUE} : Value mismatch. Expected: {expected_value}, Actual: {current}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Error validating specific value: {str(e)}"

    def _validate_dict(self, actual: Dict, expected: Dict) -> tuple[bool, str]:
        """
        Validate dictionary structure and values
        """
        for key, expected_value in expected.items():
            if key not in actual:
                return False, f"{MISSING_KEY} : Missing key: {key}"
            
            actual_value = actual[key]
            
            if isinstance(expected_value, dict):
                if not isinstance(actual_value, dict):
                    return False, f"{INCORRECT_VALUE} : Type mismatch for key {key}. Expected dict, got {type(actual_value).__name__}"
                result, error = self._validate_dict(actual_value, expected_value)
                if not result:
                    return False, f"In key {key}: {error}"
            elif isinstance(expected_value, list):
                if not isinstance(actual_value, list):
                    return False, f"{INCORRECT_VALUE} : Type mismatch for key {key}. Expected list, got {type(actual_value).__name__}"
                result, error = self._validate_list(actual_value, expected_value)
                if not result:
                    return False, f"In key {key}: {error}"
            else:
                # Validate primitive values
                if isinstance(expected_value, str):
                    if expected_value.startswith('pattern:'):
                        pattern_name = expected_value.split(':')[1]
                        # Convert integer to string for pattern validation
                        if isinstance(actual_value, int):
                            actual_value = str(actual_value)
                        if not validate_pattern(pattern_name, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Pattern validation failed for key {key}. Value: {actual_value}"
                    elif expected_value.startswith('regex:'):
                        pattern = expected_value.split(':', 1)[1]
                        # Convert integer to string for regex validation
                        if isinstance(actual_value, int):
                            actual_value = str(actual_value)
                        if not validate_regex(pattern, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Regex validation failed for key {key}. Value: {actual_value}"
                    else:
                        if actual_value != expected_value:
                            return False, f"{INCORRECT_VALUE} : Value mismatch for key {key}. Expected: {expected_value}, Actual: {actual_value}"
                else:
                    if actual_value != expected_value:
                        return False, f"{INCORRECT_VALUE} : Value mismatch for key {key}. Expected: {expected_value}, Actual: {actual_value}"
        
        return True, ""

    def _validate_list(self, actual: list, expected: list) -> tuple[bool, str]:
        """
        Validate list structure and values
        """
        if len(expected) == 0:
            return True, ""
            
        if len(actual) == 0:
            return False, "Empty list"
            
        # If expected list has only one element, use it as a template for all elements
        template = expected[0]
        for i, actual_value in enumerate(actual):
            if isinstance(template, dict):
                result, error = self._validate_dict(actual_value, template)
                if not result:
                    return False, f"In element {i}: {error}"
            elif isinstance(template, list):
                result, error = self._validate_list(actual_value, template)
                if not result:
                    return False, f"In element {i}: {error}"
            else:
                if isinstance(template, str):
                    if template.startswith('pattern:'):
                        pattern_name = template.split(':')[1]
                        if not validate_pattern(pattern_name, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Pattern validation failed for element {i}. Value: {actual_value}"
                    elif template.startswith('regex:'):
                        pattern = template.split(':', 1)[1]
                        if not validate_regex(pattern, actual_value):
                            return False, f"{PATTERN_DO_NOT_MATCH} : Regex validation failed for element {i}. Value: {actual_value}"
                    else:
                        if actual_value != template:
                            return False, f"{INCORRECT_VALUE} : Value mismatch for element {i}. Expected: {template}, Actual: {actual_value}"
                else:
                    if actual_value != template:
                        return False, f"{INCORRECT_VALUE} : Value mismatch for element {i}. Expected: {template}, Actual: {actual_value}"
        
        return True, ""

    def _validate_schema(self, actual: Union[Dict, list], schema_path: Union[str, Dict]) -> tuple[bool, str]:
        """
        Validate the response against a JSON Schema file at schema_path['path'],
        or generate it via AI spec if missing. schema_path must be a dict with:
          path: path to JSON schema file
          ai: dict with keys 'file' (Flow type file) and 'type' (Flow type name)
        """
        # Load or generate schema
        spec = schema_path
        schema_file = Path(spec['path'])
        try:
            if not schema_file.exists():
                # Generate via AI agent and save
                schema = generate_schema_with_ai(spec['ai'], str(schema_file))
            else:
                schema = json.loads(schema_file.read_text())
            # Validate response
            jsonschema.validate(instance=actual, schema=schema)
            return True, ""
        except jsonschema.exceptions.ValidationError as e:
            path = ".".join(str(p) for p in e.path) or "<root>"
            validator = e.validator
            expected = e.validator_value
            return False, f"{SCHEMA_VALIDATION_FAILURE} : {e.message} at path '{path}' (validator: {validator}, expected: {expected})"
        except Exception as e:
            return False, f"{SCHEMA_VALIDATION_FAILURE} : {str(e)}"

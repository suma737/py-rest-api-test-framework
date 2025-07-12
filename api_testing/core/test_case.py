import yaml
from typing import Dict, Any, List, Optional
import requests
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"

@dataclass
class TestCase:
    name: str
    endpoint: str
    method: HTTPMethod
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    body: Optional[Any] = None
    expected_status: int = 200
    expected_response: Optional[Dict[str, Any]] = None
    validation_rules: Optional[List[Dict[str, Any]]] = None
    
    def run(self, base_url: str) -> Dict[str, Any]:
        """Execute the test case and return results"""
        url = f"{base_url}{self.endpoint}"
        
        try:
            # Bypass environment proxies
            session = requests.Session()
            session.trust_env = False
            response = session.request(
                method=self.method.value,
                url=url,
                headers=self.headers,
                params=self.params,
                json=self.body
            )
            
            # Attempt to parse JSON response, fallback to text
            try:
                resp_content = response.json()
            except ValueError:
                resp_content = response.text
            result = {
                "test_name": self.name,
                "status_code": response.status_code,
                "response": resp_content,
                "response_time": response.elapsed.total_seconds(),
                "timestamp": datetime.now().isoformat(),
                "success": response.status_code == self.expected_status
            }
            
            if self.validation_rules:
                result["validation_results"] = self.validate_response(resp_content)
            
            return result
            
        except Exception as e:
            print(f"Test {self.name} failed with error: {str(e)}")
            return {
                "test_name": self.name,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate response against expected rules"""
        results = {}
        if not self.validation_rules:
            return results
            
        for rule in self.validation_rules:
            field = rule.get("field")
            expected_value = rule.get("expected_value")
            comparison = rule.get("comparison", "equals")
            
            actual_value = response.get(field)
            
            if comparison == "equals":
                result = actual_value == expected_value
            elif comparison == "contains":
                result = str(expected_value) in str(actual_value)
            else:
                result = False
            
            results[field] = result
            
        return results

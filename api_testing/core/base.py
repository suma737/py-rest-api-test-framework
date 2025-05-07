from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any

@dataclass
class TestResult:
    status: bool
    response: Dict
    error: str = None
    # Actual URL used for this test (after variable substitution)
    request_url: str = ""

class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

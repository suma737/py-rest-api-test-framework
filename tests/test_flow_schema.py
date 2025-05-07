import json
import subprocess
import tempfile
import pytest
from api_testing.core.validator import ResponseValidator


def test_flow_schema_generation_and_validation(monkeypatch):
    # Create a temporary Flow type file
    flow_code = """
    // @flow
    export type Person = { name: string, age: number };
    """
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.js', delete=False) as f:
        f.write(flow_code)
        f.flush()
        # Prepare fake JSON Schema output
        fake_schema = {
            "title": "Person",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }

        # Monkeypatch subprocess.run to simulate npx output
        class DummyProc:
            returncode = 0
            stdout = json.dumps(fake_schema)
            stderr = ""

        monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: DummyProc())
        validator = ResponseValidator()

        # Valid object should pass
        actual_valid = {"name": "Alice", "age": 30}
        ok, msg = validator._validate_schema(actual_valid, {'flow': {'file': f.name, 'type': 'Person'}})
        assert ok, f"Expected valid, got error: {msg}"

        # Invalid object (wrong type) should fail
        actual_invalid = {"name": "Alice", "age": "thirty"}
        ok2, msg2 = validator._validate_schema(actual_invalid, {'flow': {'file': f.name, 'type': 'Person'}})
        assert not ok2
        assert 'type' in msg2.lower()

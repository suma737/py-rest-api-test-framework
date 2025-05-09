# REST API Testing Framework

A Python-based REST API testing framework using YAML test definitions.

## Features

- YAML-based test case definitions
- Interactive new app creation: select `AddMeToYourFamily` to add and configure a new application on the fly
- Support for HTTP methods: GET, POST, PUT, DELETE, PATCH
- Header, query parameter, and JSON body support
- Dynamic test preconditions (HTTP calls or Python scripts)
- JSON schema and pattern validation
- Automatic cookie header injection via CLI (`--cookie`)
- HTML report generation including request details (URL, headers, data)
- Reports saved to `api_testing/reports/`

## Installation

Clone the repository and install in editable mode:

```bash
git clone <repo_url>
cd python-api-test-framework
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

### Console Script (installer entry point)

After `pip install -e .`, run:

```bash
api_tester --app users --env dev [--tags tag1 tag2] [--cookie "SESSIONID=...; Other=..."]
# Or to add a new application interactively:
api_tester --app AddMeToYourFamily
```

### Module Entrypoint

Without installing, run:

```bash
python -m api_testing.main --app products --env staging \
  --tags smoke regression \
  --cookie "SESSIONID=abc123; Other=def456"
```

### Script Entrypoint

Or use the standalone script:

```bash
python scripts/run_tests.py --app orders --env prod --cookie "SESSIONID=..."
```

## Test Case Format

Place YAML files under `tests/<app>/`. Example `tests/users/sample_test.yaml`:

```yaml
base_url: http://127.0.0.1:5000
tags: [smoke]
test_cases:
  - name: Get User Info
    description: Retrieve user details
    method: GET
    url: /users/${userId}
    headers:
      Accept: application/json
    params:
      id: 1
    expected_status: 200
    expected_response:
      id: ${userId}
    schema: tests/users/user_schema.yaml
```

- `base_url`: Optional override for this suite.
- `tags`: File-level tags for filtering.
- `test_cases`: List of individual test definitions.

## Reports

HTML reports are generated after each run and saved to:

```
api_testing/reports/<app>_test_report.html
```

Reports include a summary table and a detailed section with clickable tables showing:

- Test description
- Request details (URL, headers, data)
- Pass/Fail status
- Error notes (if any)

## Contributing

Please open issues or pull requests for feature requests, bugs, or improvements.

---

Written and maintained by the Windsurf engineering team.

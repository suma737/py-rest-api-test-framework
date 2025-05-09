#!/usr/bin/env python3
"""
Standalone AI agent to generate YAML integration tests from a Python unit-test file.
"""
import os
import argparse
from pathlib import Path
import openai

# Hardcoded OpenAI API key
openai.api_key = "YOUR_API_KEY"

def generate_integration_tests(unit_file: Path, output_dir: Path):
    """
    Read a Python unit-test file, call OpenAI to generate YAML integration tests,
    and write them to the specified output directory.
    """
    # API key is hardcoded; skipping environment variable check
    spec_content = unit_file.read_text()
    prompt = (
        "You are given a Python unit-test. "
        "Generate corresponding YAML integration testcases based on it."
        f"\n\n{spec_content}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt}
            ]
        )
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        exit(1)

    integration_yaml = response.choices[0].message.content.strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{unit_file.stem}_integration.yaml"
    target.write_text(integration_yaml)
    print(f"Integration tests saved to {target}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate YAML integration tests from a Python unit-test file using OpenAI."
    )
    parser.add_argument(
        "unit_file",
        help="Path to the Python unit-test file (.py)"
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save generated integration tests (default: <unit_file_parent>/integration)",
        dest="output_dir"
    )
    args = parser.parse_args()

    unit_path = Path(args.unit_file)
    if not unit_path.exists() or not unit_path.is_file() or unit_path.suffix.lower() != '.py':
        print("Error: Provide a valid Python file with .py extension.")
        exit(1)

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = unit_path.parent / 'integration'

    generate_integration_tests(unit_path, out_dir)


if __name__ == '__main__':
    main()

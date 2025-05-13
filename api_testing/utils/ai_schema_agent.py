import os
import json
from pathlib import Path
import openai

def generate_schema_with_ai(ai_spec: dict, target_path: str) -> dict:
    """
    Generate or load a JSON Schema using OpenAI.
    ai_spec should contain:
      - file: path to the Flow type file
      - type: Flow type name
      - (optional) model: OpenAI model to use (default gpt-4)
    target_path is where to save the generated schema.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    openai.api_key = api_key

    target = Path(target_path)
    if target.exists():
        return json.loads(target.read_text())

    flow_file = Path(ai_spec["file"])
    type_name = ai_spec["type"]
    if not flow_file.exists():
        raise FileNotFoundError(f"Flow type file not found: {flow_file}")

    content = flow_file.read_text()
    prompt = (
        f"Generate a JSON Schema for the Flow type `{type_name}` defined in this file:\n\n"
        f"{content}\n\n"
        "Respond with valid JSON schema only."
    )
    response = openai.ChatCompletion.create(
        model=ai_spec.get("model", "gpt-4"),
        messages=[{"role": "system", "content": prompt}]
    )
    schema_str = response.choices[0].message.content.strip()
    try:
        schema = json.loads(schema_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI response is not valid JSON: {e}\nResponse:\n{schema_str}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2))
    return schema

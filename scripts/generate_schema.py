"""
Generate config.schema.json from the Pydantic AgentSettings model.

This script outputs a JSON Schema compatible with Taplo. Run with:
    uv run scripts/generate_schema.py
It also supports a --diff flag to check if the generated schema matches the checked-in one.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

from ok.config import ConfigModel


def generate_schema() -> dict:
    """Generate the JSON schema from the AgentSettings Pydantic model."""
    schema = ConfigModel.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "AgentSettings"
    if "properties" in schema:
        schema["properties"]["$schema"] = {"type": "string", "description": "The schema URL for validation."}
    return schema


def write_schema(schema: dict, out_path: Path) -> None:
    """Write the generated schema to the specified file path."""
    schema_str = json.dumps(schema, indent=2) + "\n"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(schema_str)
    print(f"Schema written to {out_path.relative_to(Path.cwd())}")


def check_repo_schema(schema: dict, out_path: Path) -> bool:
    """
    Compare the generated schema to the checked-in schema file and print a unified diff if they differ.

    Returns:
        True if the schemas match, False if they differ.
    """
    schema_str = json.dumps(schema, indent=2) + "\n"
    if not out_path.exists():
        print(f"{out_path.relative_to(Path.cwd())} does not exist.")
        return False
    with out_path.open("r", encoding="utf-8") as f:
        existing = f.read()
    if existing != schema_str:
        print("Schema differs from checked-in config.schema.json:")
        diff = difflib.unified_diff(
            existing.splitlines(keepends=True),
            schema_str.splitlines(keepends=True),
            fromfile=str(out_path.relative_to(Path.cwd())),
            tofile="generated (from model)",
        )
        print("".join(diff))
        return False
    else:
        print("Schema matches checked-in config.schema.json.")
        return True


def main():
    """Parse arguments and run schema generation or diff logic."""
    parser = argparse.ArgumentParser(description="Generate or diff config.schema.json from Pydantic AgentSettings.")
    parser.add_argument(
        "--diff", action="store_true", help="Check if generated schema matches checked-in config.schema.json"
    )
    args = parser.parse_args()

    out_path = Path(__file__).parent.parent / "config.schema.json"
    schema = generate_schema()

    if args.diff:
        result = check_repo_schema(schema, out_path)
        if not result:
            sys.exit(1)
    else:
        write_schema(schema, out_path)


if __name__ == "__main__":
    main()

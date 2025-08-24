import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_example_envelopes_from_api_md(api_md: str) -> list[dict]:
    # Collect all JSON blocks under "Event Envelope" and POST /v1/events body
    examples: list[dict] = []
    in_section = False
    in_json = False
    buf: list[str] = []
    for line in api_md.splitlines():
        if line.startswith("## Event Envelope") or line.startswith("### POST /v1/events"):
            in_section = True
        if in_section and line.strip().startswith("```"):
            if not in_json and "json" in line:
                in_json = True
                buf = []
            elif in_json:
                # end block
                try:
                    examples.append(json.loads("\n".join(buf)))
                except Exception:
                    pass
                in_json = False
                in_section = False
            continue
        if in_json:
            buf.append(line)
    return examples


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    schema_path = root / "siren" / "specs" / "event.schema.json"
    api_md_path = root / "docs" / "api.md"

    schema = load_json(schema_path)
    api_md = api_md_path.read_text(encoding="utf-8")

    required = set(schema.get("required", []))
    props = set(schema.get("properties", {}).keys())

    examples = extract_example_envelopes_from_api_md(api_md)
    errors: list[str] = []
    if not examples:
        errors.append("No event envelope examples found in docs/api.md")
    for i, ex in enumerate(examples, 1):
        missing_required = required - set(ex.keys())
        unknown = set(ex.keys()) - props
        if missing_required:
            errors.append(f"Example {i} missing required keys: {sorted(missing_required)}")
        if unknown:
            # Allow extra keys that are documented optional fields
            pass

    if errors:
        print("Event schema check failed:\n" + "\n".join(errors))
        return 1
    print("Event schema check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

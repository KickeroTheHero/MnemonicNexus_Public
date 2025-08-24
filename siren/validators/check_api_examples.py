import json
import sys
from pathlib import Path


def load_openapi_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_example_bodies_from_api_md(api_md: str) -> dict:
    # Very light heuristic: collect JSON blocks under endpoint sections
    examples: dict[str, list[str]] = {}
    current_section: str | None = None
    in_json = False
    buf: list[str] = []
    for line in api_md.splitlines():
        if line.startswith("### "):
            # New endpoint section
            current_section = line[4:].strip()
            continue
        if line.strip().startswith("```"):
            if not in_json and "json" in line:
                in_json = True
                buf = []
            elif in_json:
                # end block
                if current_section:
                    examples.setdefault(current_section, []).append("\n".join(buf).strip())
                in_json = False
            continue
        if in_json:
            buf.append(line)
    return examples


def expected_examples_from_openapi(spec: dict) -> dict:
    # We only validate presence of schemas and do a minimal shape check by keys
    expected: dict[str, list[set[str]]] = {}
    # Map section headings in api.md to openapi operations
    mapping = {
        "POST /v1/events — Append event": ("/v1/events", "post", "EventEnvelope", "EventAccepted"),
        "GET /v1/events — List events": ("/v1/events", "get", None, "EventListResponse"),
        "GET /v1/events/{id} — Get event": ("/v1/events/{id}", "get", None, "Event"),
        "POST /v1/search/hybrid": (
            "/v1/search/hybrid",
            "post",
            "HybridSearchRequest",
            "HybridSearchResponse",
        ),
        "POST /v1/graph/query": (
            "/v1/graph/query",
            "post",
            "GraphQueryRequest",
            "GraphQueryResponse",
        ),
    }
    components = spec.get("components", {}).get("schemas", {})
    for heading, (path, method, req_schema, res_schema) in mapping.items():
        shapes: list[set[str]] = []
        if req_schema and req_schema in components:
            shapes.append(set(components[req_schema].get("properties", {}).keys()))
        if res_schema and res_schema in components:
            shapes.append(set(components[res_schema].get("properties", {}).keys()))
        expected[heading] = shapes
    return expected


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    api_md_path = root / "docs" / "api.md"
    # Use JSON snapshot to avoid external YAML dependency
    openapi_path = root / "siren" / "specs" / "openapi.json"

    api_md = api_md_path.read_text(encoding="utf-8")
    spec = load_openapi_json(openapi_path)

    examples = extract_example_bodies_from_api_md(api_md)
    expected = expected_examples_from_openapi(spec)

    errors: list[str] = []
    # For each expected heading, ensure examples exist and roughly match shape by top-level keys
    for heading, shapes in expected.items():
        got = examples.get(heading, [])
        if not got:
            errors.append(f"Missing JSON examples under section: {heading}")
            continue
        # Compare first example per shape slot if present
        for i, shape in enumerate(shapes):
            if i >= len(got):
                errors.append(f"Section {heading}: expected at least {i+1} JSON blocks")
                continue
            try:
                import json

                got_keys = set(json.loads(got[i]).keys())
            except Exception:
                errors.append(f"Section {heading}: example {i+1} is not valid JSON")
                continue
            missing = shape - got_keys
            if missing:
                errors.append(f"Section {heading}: example {i+1} missing keys: {sorted(missing)}")

    if errors:
        print("API examples check failed:\n" + "\n".join(errors))
        return 1
    print("API examples check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

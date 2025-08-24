"""
JSON Validators and Decision Hash Computation

Validates controller outputs against schemas and computes deterministic hashes
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema


class ValidationError(Exception):
    """Schema validation error"""

    pass


class JSONValidator:
    """
    JSON schema validator for MoE controller outputs

    Loads schemas from schemas/json/ and validates against them
    """

    def __init__(self):
        self.schemas = {}
        self.schemas_dir = Path("schemas/json")
        self._load_schemas()

    def _load_schemas(self):
        """Load all JSON schemas from schemas/json/"""
        if not self.schemas_dir.exists():
            return

        for schema_file in self.schemas_dir.glob("*.json"):
            try:
                with open(schema_file, encoding="utf-8") as f:
                    schema = json.load(f)

                schema_name = schema_file.stem  # filename without .json
                self.schemas[schema_name] = schema

            except Exception as e:
                print(f"Warning: Failed to load schema {schema_file}: {e}")

    def validate(self, data: dict[str, Any], schema_name: str) -> bool:
        """
        Validate data against named schema

        Args:
            data: Data to validate
            schema_name: Name of schema (e.g., 'tool_intent.v1')

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        if schema_name not in self.schemas:
            raise ValidationError(f"Schema '{schema_name}' not found")

        schema = self.schemas[schema_name]

        try:
            jsonschema.validate(data, schema)
            return True
        except jsonschema.ValidationError as e:
            raise ValidationError(f"Schema validation failed: {e.message}")
        except jsonschema.SchemaError as e:
            raise ValidationError(f"Invalid schema: {e.message}")

    def validate_with_retry(self, data: dict[str, Any], schema_name: str) -> tuple[bool, bool]:
        """
        Validate with single retry policy

        Args:
            data: Data to validate
            schema_name: Schema to validate against

        Returns:
            (is_valid, validation_failed) tuple
            - is_valid: True if data is valid
            - validation_failed: True if validation was attempted but failed
        """
        try:
            self.validate(data, schema_name)
            return True, False
        except ValidationError:
            # This represents the "retry once" - in real implementation
            # this would re-prompt the model, but for now we just mark failure
            return False, True

    def get_available_schemas(self) -> list[str]:
        """Get list of available schema names"""
        return list(self.schemas.keys())


def decision_hash(
    controller_version: str,
    policy_version: str,
    prompt_version: str,
    rng_seed: int,
    rank_version: str | None,
    tool_intent: dict[str, Any],
    brief: dict[str, Any],
) -> str:
    """
    Compute deterministic hash for decision replay

    Hash input tuple: (controller_version, policy_version, prompt_version,
                      rng_seed, rank_version, normalized_tool_intent, normalized_brief)

    Args:
        controller_version: Version of the controller
        policy_version: Version of the policy
        prompt_version: Version of the prompts
        rng_seed: Random seed used
        rank_version: Ranking version (or None)
        tool_intent: Normalized tool intent object
        brief: Normalized brief object

    Returns:
        SHA-256 hash string
    """

    # Build the hash basis
    basis = {
        "controller_version": controller_version,
        "policy_version": policy_version,
        "prompt_version": prompt_version,
        "rng_seed": rng_seed,
        "rank_version": rank_version,
    }

    # Add normalized objects
    hash_input = {
        **basis,
        "tool_intent": _normalize_json(tool_intent),
        "brief": _normalize_json(brief),
    }

    # Canonicalize JSON (sorted keys, no whitespace variance)
    canonical_json = json.dumps(hash_input, sort_keys=True, separators=(",", ":"))

    # Compute SHA-256 hash
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _normalize_json(obj: Any) -> Any:
    """
    Normalize JSON object for consistent hashing

    Recursively sorts dictionaries and handles special cases
    """
    if isinstance(obj, dict):
        # Sort dictionary keys and normalize values
        return {k: _normalize_json(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        # Normalize list elements (but preserve order)
        return [_normalize_json(item) for item in obj]
    elif isinstance(obj, float):
        # Round floats to avoid precision issues
        return round(obj, 10)
    else:
        # Return as-is for primitives
        return obj

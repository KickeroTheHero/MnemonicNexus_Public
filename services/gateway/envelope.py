"""
MnemonicNexus V2 Event Envelope Validation Library
Comprehensive validation for V2 event envelopes with audit and integrity features
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Dict

from dateutil.parser import parse as parse_datetime  # type: ignore[import-untyped]


class EventEnvelope:
    """V2 Event Envelope with comprehensive validation"""

    def __init__(self, envelope_data: Dict[str, Any]):
        self.data = envelope_data
        self._validate()

    def _validate(self) -> None:
        """Comprehensive envelope validation"""
        # Required fields
        required = ["world_id", "branch", "kind", "payload", "by"]
        for field in required:
            if field not in self.data:
                raise ValueError(f"Missing required field: {field}")

        # UUID validation
        try:
            uuid.UUID(self.data["world_id"])
        except ValueError:
            raise ValueError("world_id must be valid UUID")

        # Agent validation
        if "agent" not in self.data["by"]:
            raise ValueError("by.agent is required for audit trail")

        # Timestamp validation
        if "occurred_at" in self.data:
            self._validate_timestamp(self.data["occurred_at"])

        # Version validation (optional forward compatibility)
        if "version" in self.data:
            version = self.data["version"]
            if not isinstance(version, int) or version < 1 or version > 2:
                raise ValueError(
                    f"Unsupported envelope version: {version}. Supported versions: 1, 2"
                )

    def _validate_timestamp(self, timestamp_str: str) -> None:
        """Validate strict RFC3339/ISO8601 timestamp format"""
        try:
            # Parse with dateutil
            dt = parse_datetime(timestamp_str)

            # Ensure it's a valid ISO8601/RFC3339 format by round-trip
            # This catches permissive parsing that accepts invalid forms
            if dt.isoformat() not in [
                timestamp_str.rstrip("Z"),
                timestamp_str.rstrip("Z") + "Z",
            ]:
                # Allow either with or without Z suffix
                if not (
                    timestamp_str.endswith("Z") or timestamp_str.endswith("+00:00")
                ):
                    raise ValueError("Timestamp must be UTC (end with Z or +00:00)")

        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid RFC3339 timestamp format: {timestamp_str}. Expected: YYYY-MM-DDTHH:MM:SSZ"
            )

    def compute_payload_hash(self) -> str:
        """Generate SHA-256 hash of canonical payload only.

        Aligns with server-side hashing to ensure parity across systems.
        """
        payload = self.data.get("payload")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _canonicalize(self) -> str:
        """Create canonical JSON representation for hashing (envelope-wide).

        Note: compute_payload_hash uses payload-only canonicalization.
        """
        return json.dumps(self.data, sort_keys=True, separators=(",", ":"))

    def enrich_with_server_fields(self) -> Dict[str, Any]:
        """Add server-assigned fields"""
        enriched = self.data.copy()
        # Ensure proper UTC timezone formatting
        enriched["received_at"] = (
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
        )  # Truncate to milliseconds
        enriched["payload_hash"] = self.compute_payload_hash()
        return enriched

    def verify_payload_hash(self, expected_hash: str) -> bool:
        """Verify envelope integrity against expected hash"""
        computed_hash = self.compute_payload_hash()
        return computed_hash == expected_hash

    @classmethod
    def verify_envelope_integrity(cls, envelope_data: Dict[str, Any]) -> bool:
        """Verify stored envelope hasn't been tampered with.

        Accepts either a dict or a JSON string (as commonly returned by DB drivers).
        """
        try:
            # Parse if JSON string
            if isinstance(envelope_data, str):
                parsed: Dict[str, Any] = json.loads(envelope_data)
            else:
                # Work on a shallow copy to avoid mutating the caller
                parsed = dict(envelope_data)

            expected_hash = parsed.pop("payload_hash", None)
            if not expected_hash:
                return False

            envelope = cls(parsed)
            return envelope.verify_payload_hash(expected_hash)
        except Exception:
            return False

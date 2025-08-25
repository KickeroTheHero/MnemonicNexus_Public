"""
Decision Event Emitter

Builds decision records and emits them to the Gateway
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

import aiohttp

from .validators import decision_hash


class EmissionError(Exception):
    """Error emitting decision record"""

    pass


class DecisionEventEmitter:
    """
    Emits decision records to the Gateway

    Builds decision_record.v1 objects and POSTs them to the Gateway
    """

    def __init__(self):
        self.gateway_url = os.getenv("MNX_GATEWAY_URL", "http://localhost:8080")
        self.controller_version = os.getenv("CONTROLLER_VERSION", "2.0.0-s0")
        self.timeout = 10.0

    def build_decision_record(
        self,
        world_id: str,
        branch: str,
        correlation_id: str,
        tool_intent: dict[str, Any],
        brief: dict[str, Any],
        tool_results: list[Any],
        validation_failed: bool = False,
        rank_version: str | None = None,
    ) -> dict[str, Any]:
        """
        Build a decision_record.v1 object

        Args:
            world_id: Tenancy key
            branch: Branch name
            correlation_id: Correlation ID for tracing
            tool_intent: Tool intent object
            brief: Brief object
            tool_results: Results from tool execution
            validation_failed: Whether validation failed but we recovered
            rank_version: Ranking version if fusion is enabled

        Returns:
            Complete decision record
        """

        # Get determinism stamps from environment
        rng_seed = int(os.getenv("rng_seed", "12345"))
        policy_version = os.getenv("policy_versions", '{"content":"cv1","tools":"tv1"}')
        prompt_version = os.getenv("prompt_version", "pv1")

        # Parse policy version if it's JSON
        try:
            if isinstance(policy_version, str):
                policy_obj = json.loads(policy_version)
                policy_version = f"content:{policy_obj.get('content', 'cv1')},tools:{policy_obj.get('tools', 'tv1')}"
        except (json.JSONDecodeError, AttributeError):
            policy_version = str(policy_version)

        # Create artifacts
        artifacts = [
            {"type": "tool_intent", "data": tool_intent},
            {"type": "brief", "data": brief},
            {"type": "tool_results", "data": tool_results},
        ]

        # Compute decision hash
        hash_value = decision_hash(
            controller_version=self.controller_version,
            policy_version=policy_version,
            prompt_version=prompt_version,
            rng_seed=rng_seed,
            rank_version=rank_version,
            tool_intent=tool_intent,
            brief=brief,
        )

        # Build decision record
        decision_record = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "world_id": world_id,
            "branch": branch,
            "correlation_id": correlation_id,
            "controller_version": self.controller_version,
            "rng_seed": rng_seed,
            "policy_version": policy_version,
            "prompt_version": prompt_version,
            "rank_version": rank_version,
            "validation_failed": validation_failed,
            "artifacts": artifacts,
            "hash": hash_value,
        }

        return decision_record

    async def emit_decision(self, decision_record: dict[str, Any]) -> bool:
        """
        Emit decision record to Gateway

        Args:
            decision_record: Complete decision record

        Returns:
            True if successfully emitted

        Raises:
            EmissionError: If emission fails
        """

        try:
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-ID": decision_record.get("correlation_id", ""),
                "Idempotency-Key": decision_record.get("id", str(uuid.uuid4())),
            }

            # Create event envelope for Gateway
            event_envelope = {
                "world_id": decision_record["world_id"],
                "branch": decision_record["branch"],
                "kind": "decision.recorded",
                "payload": decision_record,
                "by": {"agent": "mnx-moe-controller"},
                "version": 1,
                "occurred_at": decision_record["timestamp"],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.gateway_url}/v1/events",
                    json=event_envelope,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status in [200, 201]:
                        return True
                    elif response.status == 409:
                        # Idempotency conflict - already recorded
                        return True
                    else:
                        error_text = await response.text()
                        raise EmissionError(
                            f"Gateway error {response.status}: {error_text}"
                        )

        except aiohttp.ClientError as e:
            raise EmissionError(f"HTTP client error: {e}")
        except Exception as e:
            raise EmissionError(f"Unexpected error: {e}")

    def get_config(self) -> dict[str, Any]:
        """Get current emitter configuration"""
        return {
            "gateway_url": self.gateway_url,
            "controller_version": self.controller_version,
            "timeout": self.timeout,
        }

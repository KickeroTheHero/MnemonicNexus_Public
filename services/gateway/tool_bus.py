"""
Tool Bus - S0 Migration Implementation

Implements timeout, retry, and degradation semantics for tool calls with
comprehensive metrics tracking and correlation ID propagation.
"""

import asyncio
import os
import time
import uuid
from typing import Any

from monitoring import GatewayMetrics


class ToolBusError(Exception):
    """Base exception for tool bus errors"""

    pass


class ToolTimeout(ToolBusError):
    """Tool call timeout exception"""

    pass


class RowCapExceeded(ToolBusError):
    """Row cap exceeded exception"""

    pass


class ToolBus:
    """
    S0 Tool Bus with timeout, retry, and degradation semantics

    Features:
    - Configurable timeouts per tool call
    - Single retry on failure, then degrade
    - Row cap enforcement
    - Correlation ID propagation
    - Comprehensive metrics
    """

    def __init__(self, metrics: GatewayMetrics):
        self.metrics = metrics
        self.timeout_ms = int(os.getenv("TOOL_TIMEOUT_MS", "8000"))
        self.row_cap = int(os.getenv("TOOL_ROW_CAP", "200"))

    async def call_tool(
        self, tool_name: str, payload: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """
        Call a tool with timeout, retry, and degradation semantics

        Args:
            tool_name: Name of the tool to invoke
            payload: Tool-specific parameters
            correlation_id: Correlation ID for tracing

        Returns:
            Tool response data (may be degraded on failures)
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        start_time = time.time()

        try:
            # First attempt
            result = await self._invoke_tool(tool_name, payload, correlation_id)

            # Success - record metrics and apply row cap
            duration = time.time() - start_time
            self.metrics.record_tool_call(tool_name, "ok", duration)
            return self._apply_row_cap(result, tool_name)

        except (ToolTimeout, asyncio.TimeoutError):
            # Timeout - try once more then degrade
            try:
                result = await self._invoke_tool(tool_name, payload, correlation_id)
                duration = time.time() - start_time
                self.metrics.record_tool_call(tool_name, "ok", duration)
                return self._apply_row_cap(result, tool_name)
            except Exception:
                # Second failure - record timeout and degrade
                duration = time.time() - start_time
                self.metrics.record_tool_call(tool_name, "timeout", duration)
                return self._degrade_result(tool_name)

        except RowCapExceeded:
            # Row cap exceeded - record and return capped result
            duration = time.time() - start_time
            self.metrics.record_tool_call(tool_name, "rowcap", duration)
            return self._degrade_result(tool_name)

        except Exception:
            # Other error - try once more then degrade
            try:
                result = await self._invoke_tool(tool_name, payload, correlation_id)
                duration = time.time() - start_time
                self.metrics.record_tool_call(tool_name, "ok", duration)
                return self._apply_row_cap(result, tool_name)
            except Exception:
                # Second failure - record error and degrade
                duration = time.time() - start_time
                self.metrics.record_tool_call(tool_name, "error", duration)
                return self._degrade_result(tool_name)

    async def _invoke_tool(
        self, tool_name: str, payload: dict[str, Any], correlation_id: str
    ) -> dict[str, Any]:
        """
        Low-level tool invocation with timeout

        This is a placeholder implementation - in practice this would
        make HTTP calls or other RPC to actual tools.
        """

        # Simulate tool call with timeout
        try:
            timeout_seconds = self.timeout_ms / 1000.0

            # For now, simulate different tool behaviors
            if tool_name == "search":
                await asyncio.sleep(0.1)  # Fast tool
                return {
                    "results": [
                        {"id": "1", "title": "Sample Result 1", "score": 0.9},
                        {"id": "2", "title": "Sample Result 2", "score": 0.8},
                    ]
                }
            elif tool_name == "analyze":
                await asyncio.sleep(0.5)  # Slower tool
                return {
                    "analysis": {
                        "sentiment": "positive",
                        "confidence": 0.85,
                        "categories": ["tech", "ai"],
                    }
                }
            elif tool_name == "timeout_test":
                # Simulate timeout for testing
                await asyncio.sleep(timeout_seconds + 1)
                return {"never": "reached"}
            else:
                # Generic tool response
                await asyncio.sleep(0.2)
                return {"tool": tool_name, "status": "completed", "data": payload}

        except asyncio.TimeoutError:
            raise ToolTimeout(f"Tool {tool_name} timed out after {self.timeout_ms}ms")

    def _apply_row_cap(self, result: dict[str, Any], tool_name: str) -> dict[str, Any]:
        """
        Apply row cap to tool results

        Truncates arrays/lists in the result to the configured row cap.
        """
        if not isinstance(result, dict):
            return result

        capped_result = {}
        for key, value in result.items():
            if isinstance(value, list) and len(value) > self.row_cap:
                # Apply row cap and add metadata
                capped_result[key] = value[: self.row_cap]
                capped_result[f"{key}_truncated"] = True
                capped_result[f"{key}_original_count"] = len(value)
            elif isinstance(value, dict):
                # Recursively apply to nested dicts
                capped_result[key] = self._apply_row_cap(value, tool_name)
            else:
                capped_result[key] = value

        return capped_result

    def _degrade_result(self, tool_name: str) -> dict[str, Any]:
        """
        Return a safe degraded result when tool calls fail

        Each tool type gets a safe default response appropriate for its contract.
        """
        degraded_responses = {
            "search": {
                "results": [],
                "degraded": True,
                "reason": "Tool failure - returning empty results",
            },
            "analyze": {
                "analysis": {
                    "sentiment": "neutral",
                    "confidence": 0.0,
                    "categories": [],
                },
                "degraded": True,
                "reason": "Tool failure - returning neutral analysis",
            },
            "summarize": {
                "summary": "Summary unavailable due to tool failure",
                "degraded": True,
                "reason": "Tool failure",
            },
        }

        return degraded_responses.get(
            tool_name,
            {
                "degraded": True,
                "reason": "Tool failure - no safe default available",
                "tool": tool_name,
            },
        )


class ControllerContext:
    """
    Context for controller decisions with correlation tracking
    """

    def __init__(self, world_id: str, branch: str, correlation_id: str | None = None):
        self.world_id = world_id
        self.branch = branch
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.rank_version: str | None = None
        self.validation_failed = False

    def enable_fusion(self, rank_version: str):
        """Enable search fusion with specified ranking version"""
        self.rank_version = rank_version

    def mark_validation_failed(self):
        """Mark that validation failed but controller recovered/degraded"""
        self.validation_failed = True

"""
Single-MoE Controller

Main controller implementing the Single-MoE architecture with structured JSON output
"""

import os
import uuid
from datetime import datetime
from typing import Any

from .client_lmstudio import LMStudioClient, LMStudioError
from .event_emitter import DecisionEventEmitter, EmissionError
from .tool_bus import ToolBus
from .validators import JSONValidator


class ControllerError(Exception):
    """Base controller error"""

    pass


class MoEController:
    """
    Single Mixture-of-Experts Controller

    Implements the complete flow:
    1. Prompt model → tool_intent.v1 (JSON only)
    2. Tool bus executes across lenses/web
    3. Prompt model → brief.v1 (JSON only)
    4. Build decision_record.v1, compute hash, POST to Gateway
    """

    def __init__(self):
        self.lm_client = LMStudioClient()
        self.tool_bus = ToolBus()
        self.validator = JSONValidator()
        self.event_emitter = DecisionEventEmitter()

        # Load determinism configuration
        self.rng_seed = int(os.getenv("rng_seed", "12345"))
        self.fusion_enabled = os.getenv("FUSION_ENABLE", "false").lower() == "true"
        self.fusion_rank_version = os.getenv("FUSION_RANK_VERSION", "v1")

    async def make_decision(
        self,
        query: str,
        world_id: str,
        branch: str,
        correlation_id: str | None = None,
        rank_version: str | None = None,
    ) -> dict[str, Any]:
        """
        Core decision making method

        Args:
            query: User query/request
            world_id: Tenancy key
            branch: Branch name
            correlation_id: Optional correlation ID for tracing
            rank_version: Optional ranking version override

        Returns:
            Decision record
        """

        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        validation_failed = False

        try:
            # Step 1: Generate tool intent
            tool_intent = await self._generate_tool_intent(query)

            # Validate tool intent
            intent_valid, intent_validation_failed = self.validator.validate_with_retry(
                tool_intent, "tool_intent.v1"
            )
            if intent_validation_failed:
                validation_failed = True

            # Step 2: Execute tools
            tool_results = await self.tool_bus.execute_tools(
                tool_intent, world_id, branch
            )

            # Step 3: Generate brief
            tool_results_data = [r.data for r in tool_results]
            brief = await self._generate_brief(query, tool_intent, tool_results_data)

            # Validate brief
            brief_valid, brief_validation_failed = self.validator.validate_with_retry(
                brief, "brief.v1"
            )
            if brief_validation_failed:
                validation_failed = True

            # Step 4: Build and emit decision record
            effective_rank_version = rank_version or (
                self.fusion_rank_version if self.fusion_enabled else None
            )

            decision_record = self.event_emitter.build_decision_record(
                world_id=world_id,
                branch=branch,
                correlation_id=correlation_id,
                tool_intent=tool_intent,
                brief=brief,
                tool_results=tool_results_data,
                validation_failed=validation_failed,
                rank_version=effective_rank_version,
            )

            # Emit to Gateway
            await self.event_emitter.emit_decision(decision_record)

            return decision_record

        except Exception as e:
            # Build degraded decision record on critical failure
            degraded_decision = await self._build_degraded_decision(
                world_id, branch, correlation_id, query, str(e)
            )

            try:
                await self.event_emitter.emit_decision(degraded_decision)
            except EmissionError:
                pass  # Don't fail on emission error during degradation

            return degraded_decision

    async def _generate_tool_intent(self, query: str) -> dict[str, Any]:
        """
        Generate tool_intent.v1 from query

        Args:
            query: User query

        Returns:
            Tool intent object
        """

        # Load tool intent prompt
        prompt = await self._load_prompt("tool_intent", query)

        try:
            result = await self.lm_client.generate_structured_output(
                prompt=prompt,
                schema_name="tool_intent.v1",
                seed=self.rng_seed,
                temperature=0.1,
                max_tokens=1024,
            )
            return result

        except LMStudioError as e:
            # Return degraded tool intent on LM Studio failure
            return {
                "intent_id": str(uuid.uuid4()),
                "correlation_id": str(uuid.uuid4()),
                "tools": [],
                "degraded": True,
                "error": str(e),
            }

    async def _generate_brief(
        self,
        query: str,
        tool_intent: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate brief.v1 from query and tool results

        Args:
            query: Original user query
            tool_intent: Tool intent that was executed
            tool_results: Results from tool execution

        Returns:
            Brief object
        """

        # Load brief prompt with context
        prompt = await self._load_prompt(
            "brief",
            query,
            {"tool_intent": tool_intent, "tool_results": tool_results},
        )

        try:
            result = await self.lm_client.generate_structured_output(
                prompt=prompt,
                schema_name="brief.v1",
                seed=self.rng_seed,
                temperature=0.1,
                max_tokens=2048,
            )
            return result

        except LMStudioError as e:
            # Return degraded brief on LM Studio failure
            return {
                "brief_id": str(uuid.uuid4()),
                "correlation_id": str(uuid.uuid4()),
                "summary": f"Brief generation failed: {e}",
                "context": {"query": query, "degraded": True, "error": str(e)},
            }

    async def _load_prompt(
        self, prompt_type: str, query: str, context: dict | None = None
    ) -> str:
        """
        Load prompt template for given type

        Args:
            prompt_type: Type of prompt (tool_intent, brief)
            query: User query
            context: Optional context for brief prompts

        Returns:
            Formatted prompt string
        """

        # For now, use simple inline prompts
        # TODO: Load from prompts/ directory in PR-3

        if prompt_type == "tool_intent":
            return f"""
Analyze this query and determine what tools to use. Output ONLY JSON conforming to tool_intent.v1 schema.

Query: {query}

Consider these available tools:
- relational_search: Search structured note data
- semantic_search: Semantic similarity search
- graph_query: Graph relationship queries
- web_search: Web search for external information

Output format:
{{
  "intent_id": "uuid",
  "correlation_id": "uuid",
  "tools": [
    {{"name": "tool_name", "parameters": {{"key": "value"}}}}
  ]
}}
"""

        elif prompt_type == "brief":
            tool_results_text = ""
            if context and "tool_results" in context:
                tool_results_text = f"\nTool Results: {context['tool_results']}"

            return f"""
Create a structured brief based on this query and tool results. Output ONLY JSON conforming to brief.v1 schema.

Query: {query}{tool_results_text}

Output format:
{{
  "brief_id": "uuid",
  "correlation_id": "uuid",
  "summary": "concise summary of findings",
  "context": {{
    "key": "contextual information"
  }}
}}
"""

        else:
            raise ControllerError(f"Unknown prompt type: {prompt_type}")

    async def _build_degraded_decision(
        self, world_id: str, branch: str, correlation_id: str, query: str, error: str
    ) -> dict[str, Any]:
        """Build degraded decision record on critical failure"""

        degraded_tool_intent = {
            "intent_id": str(uuid.uuid4()),
            "correlation_id": correlation_id,
            "tools": [],
            "degraded": True,
            "error": error,
        }

        degraded_brief = {
            "brief_id": str(uuid.uuid4()),
            "correlation_id": correlation_id,
            "summary": f"Critical controller failure: {error}",
            "context": {"query": query, "degraded": True, "error": error},
        }

        return self.event_emitter.build_decision_record(
            world_id=world_id,
            branch=branch,
            correlation_id=correlation_id,
            tool_intent=degraded_tool_intent,
            brief=degraded_brief,
            tool_results=[],
            validation_failed=True,
        )

    async def process_request(
        self, world_id: str, branch: str, query: str, correlation_id: str | None = None
    ) -> dict[str, Any]:
        """
        Process a complete decision request (used by replay harness)

        This is an alias for the main decision flow to match the replay harness interface.
        """
        return await self.make_decision(query, world_id, branch, correlation_id)

    async def health_check(self) -> dict[str, Any]:
        """
        Comprehensive health check of all components

        Returns:
            Health status dictionary
        """

        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "components": {},
        }

        # Check LM Studio
        lm_healthy = await self.lm_client.health_check()
        health["components"]["lm_studio"] = {
            "status": "healthy" if lm_healthy else "unhealthy",
            "config": self.lm_client.get_config(),
        }

        # Check schemas
        schemas = self.validator.get_available_schemas()
        health["components"]["schemas"] = {
            "status": "healthy" if len(schemas) >= 3 else "degraded",
            "available_schemas": schemas,
        }

        # Check tool bus
        health["components"]["tool_bus"] = {
            "status": "healthy",
            "config": self.tool_bus.get_config(),
        }

        # Check event emitter
        health["components"]["event_emitter"] = {
            "status": "healthy",
            "config": self.event_emitter.get_config(),
        }

        # Overall status
        component_statuses = [
            c.get("status", "unknown") for c in health["components"].values()
        ]
        if any(status == "unhealthy" for status in component_statuses):
            health["status"] = "unhealthy"
        elif any(status == "degraded" for status in component_statuses):
            health["status"] = "degraded"

        return health

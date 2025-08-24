"""
LM Studio Client for MoE Controller

Handles communication with LM Studio API using structured output
"""

import asyncio
import json
import os
from typing import Any

import aiohttp


class LMStudioError(Exception):
    """Base exception for LM Studio errors"""

    pass


class LMStudioClient:
    """
    LM Studio API client for structured JSON output

    Configured for Mixtral-8x7B-Instruct model with JSON mode enforcement
    """

    def __init__(self):
        self.base_url = os.getenv("LM_STUDIO_BASE", "http://localhost:1234")
        self.model_id = os.getenv(
            "LM_STUDIO_MODEL_ID",
            "Mixtral-8x7B-Instruct-v0.1-GGUF/mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf",
        )
        self.timeout = 30.0

    async def generate_structured_output(
        self,
        prompt: str,
        schema_name: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """
        Generate structured JSON output using LM Studio

        Args:
            prompt: The input prompt
            schema_name: Name of the target schema for validation
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature (low for determinism)
            seed: Random seed for deterministic output

        Returns:
            Parsed JSON response

        Raises:
            LMStudioError: If generation fails or returns invalid JSON
        """

        # Construct request payload
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a precise AI assistant that ONLY outputs valid JSON conforming to the {schema_name} schema. Never include explanations, markdown, or any text outside the JSON object.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},  # Force JSON mode
            "stream": False,
        }

        # Add seed if provided for determinism
        if seed is not None:
            payload["seed"] = seed

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise LMStudioError(f"LM Studio API error {response.status}: {error_text}")

                    result = await response.json()

                    # Extract content from response
                    choices = result.get("choices", [])
                    if not choices:
                        raise LMStudioError("No choices returned from LM Studio")

                    content = choices[0].get("message", {}).get("content", "")
                    if not content:
                        raise LMStudioError("Empty content returned from LM Studio")

                    # Parse JSON response
                    try:
                        parsed_json = json.loads(content)
                        return parsed_json
                    except json.JSONDecodeError as e:
                        raise LMStudioError(f"Invalid JSON returned: {e}\nContent: {content}")

        except asyncio.TimeoutError:
            raise LMStudioError(f"Request timed out after {self.timeout} seconds")
        except aiohttp.ClientError as e:
            raise LMStudioError(f"HTTP client error: {e}")

    async def health_check(self) -> bool:
        """
        Check if LM Studio is running and the model is loaded

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v1/models", timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response:
                    if response.status != 200:
                        return False

                    models = await response.json()
                    model_ids = [model.get("id", "") for model in models.get("data", [])]

                    # Check if our target model is available
                    return self.model_id in model_ids

        except Exception:
            return False

    def get_config(self) -> dict[str, Any]:
        """Get current client configuration"""
        return {"base_url": self.base_url, "model_id": self.model_id, "timeout": self.timeout}

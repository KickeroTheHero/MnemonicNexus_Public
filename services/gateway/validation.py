"""
Comprehensive event validation middleware for MnemonicNexus V2 Gateway

Handles header validation, envelope validation, and business rule enforcement.
"""

import re
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from models import EventEnvelope


class ConflictError(Exception):
    """Idempotency conflict error"""

    pass


class ValidationError(Exception):
    """Envelope validation error"""

    pass


class EventValidationMiddleware:
    """Comprehensive event validation middleware"""

    @staticmethod
    def validate_headers(
        idempotency_key: Optional[str], correlation_id: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """Validate and normalize HTTP headers"""

        # Validate idempotency key format if provided
        if idempotency_key and len(idempotency_key.strip()) == 0:
            raise ValidationError("Idempotency-Key cannot be empty string")

        # Validate correlation ID format if provided
        if correlation_id:
            try:
                uuid.UUID(correlation_id)
            except ValueError:
                raise ValidationError("X-Correlation-Id must be valid UUID format")

        return {
            "idempotency_key": idempotency_key.strip() if idempotency_key else None,
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }

    @staticmethod
    def validate_envelope(envelope_data: Dict[str, Any]) -> "EventEnvelope":
        """Validate complete event envelope"""
        from models import EventEnvelope

        try:
            # Pydantic validation handles structure and types
            envelope = EventEnvelope(**envelope_data)

            # Additional business logic validation
            EventValidationMiddleware._validate_business_rules(envelope)

            return envelope

        except Exception as e:
            raise ValidationError(f"Envelope validation failed: {str(e)}")

    @staticmethod
    def _validate_business_rules(envelope: "EventEnvelope"):
        """Additional business logic validation"""

        # Validate branch name format
        if not re.match(r"^[a-zA-Z0-9_-]+$", envelope.branch):
            raise ValidationError(
                "Branch name must be alphanumeric with hyphens/underscores"
            )

        # Validate event kind format
        if "." not in envelope.kind or len(envelope.kind.split(".")) != 2:
            raise ValidationError("Event kind must be in format 'category.action'")

        # Validate payload is not empty
        if not envelope.payload:
            raise ValidationError("Event payload cannot be empty")

        # Validate version is supported
        if envelope.version < 1 or envelope.version > 2:
            raise ValidationError("Event envelope version must be 1 or 2")

        # Validate branch name length
        if len(envelope.branch) > 100:
            raise ValidationError("Branch name cannot exceed 100 characters")

        # Validate event kind components
        category, action = envelope.kind.split(".")
        if not category or not action:
            raise ValidationError("Event kind category and action cannot be empty")

        # Validate audit agent format
        agent = envelope.by.get("agent", "")
        if not agent or len(agent.strip()) == 0:
            raise ValidationError("Audit agent cannot be empty")


class RequestValidator:
    """Additional request-level validation"""

    @staticmethod
    def validate_pagination_params(
        after_global_seq: Optional[int], limit: int
    ) -> Dict[str, Any]:
        """Validate pagination parameters"""

        if limit <= 0:
            raise ValidationError("Limit must be positive integer")

        if limit > 1000:
            raise ValidationError("Limit cannot exceed 1000")

        if after_global_seq is not None and after_global_seq < 0:
            raise ValidationError("after_global_seq must be non-negative")

        return {
            "after_global_seq": after_global_seq,
            "limit": min(limit, 1000),  # Enforce hard limit
        }

    @staticmethod
    def validate_world_id(world_id: str) -> str:
        """Validate world_id parameter"""
        try:
            uuid.UUID(world_id)
            return world_id
        except ValueError:
            raise ValidationError("world_id must be a valid UUID")

    @staticmethod
    def validate_event_id(event_id: str) -> str:
        """Validate event_id parameter"""
        try:
            uuid.UUID(event_id)
            return event_id
        except ValueError:
            raise ValidationError("event_id must be a valid UUID")

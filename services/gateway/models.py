"""
Pydantic models for MnemonicNexus V2 Gateway API

Comprehensive validation for event envelopes, responses, and error handling.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


class EventEnvelope(BaseModel):
    """V2 Event Envelope with comprehensive validation"""

    world_id: str = Field(..., description="Tenancy key (UUID)")
    branch: str = Field(..., description="Branch name")
    kind: str = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Event data")
    by: Dict[str, Any] = Field(..., description="Audit information")
    version: int = Field(1, description="Envelope version")
    occurred_at: Optional[str] = Field(None, description="Client timestamp")
    causation_id: Optional[str] = Field(None, description="Causation chain ID")

    @validator("world_id")
    def validate_world_id(cls, v):
        """Ensure world_id is valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("world_id must be a valid UUID")

    @validator("by")
    def validate_by(cls, v):
        """Ensure audit information includes required agent"""
        if "agent" not in v:
            raise ValueError("by.agent is required for audit trail")
        return v

    @validator("occurred_at")
    def validate_occurred_at(cls, v):
        """Validate timestamp format if provided"""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("occurred_at must be valid ISO8601 timestamp")
        return v


class EventAccepted(BaseModel):
    """Response for successfully accepted event"""

    event_id: str = Field(..., description="Generated event UUID")
    global_seq: int = Field(..., description="Global sequence number")
    received_at: str = Field(..., description="Server timestamp")
    correlation_id: str = Field(..., description="Request correlation ID")


class ErrorResponse(BaseModel):
    """Standardized error response"""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class EventListResponse(BaseModel):
    """Response for event listing with pagination"""

    items: list = Field(..., description="List of events")
    next_after_global_seq: Optional[int] = Field(None, description="Next pagination cursor")
    has_more: bool = Field(..., description="Whether more events exist")


class HealthResponse(BaseModel):
    """Gateway health check response"""

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Gateway version")
    components: Dict[str, Any] = Field(..., description="Component health details")

"""
MnemonicNexus V2 Gateway - Phase A6 Complete Implementation

FastAPI Gateway with comprehensive idempotency, validation, and 409 handling.
Full event ingestion pipeline with proper error handling and monitoring.
"""

import json
import os
from typing import Optional

import asyncpg

# Import admin routes
from admin import admin_router
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import Phase A6 modules
from models import EventAccepted, EventEnvelope, EventListResponse, HealthResponse
from monitoring import GatewayMetrics
from persistence import EventPersistence
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from validation import ConflictError, EventValidationMiddleware, RequestValidator, ValidationError

# Initialize FastAPI app
app = FastAPI(
    title="MnemonicNexus V2 Gateway",
    description="V2 Gateway API with tenancy and idempotency",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db_pool: asyncpg.Pool = None
event_persistence: EventPersistence = None
metrics = GatewayMetrics()

# Include admin routes
app.include_router(admin_router)


# Override admin dependency
async def get_db_pool_override():
    """Provide database pool to admin endpoints"""
    return db_pool


# Override the dependency
from admin import get_db_pool  # noqa: E402

app.dependency_overrides[get_db_pool] = get_db_pool_override


@app.on_event("startup")
async def startup_event():
    """Initialize database connection and dependencies"""
    global db_pool, event_persistence

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    )

    try:
        db_pool = await asyncpg.create_pool(
            database_url, min_size=2, max_size=10, command_timeout=60
        )
        event_persistence = EventPersistence(db_pool)

        print("✅ Gateway V2 started successfully")
        print(f"✅ Database pool created: {database_url}")
    except Exception as e:
        print(f"❌ Gateway startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources"""
    if db_pool:
        await db_pool.close()
        print("✅ Database pool closed")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Gateway health with dependency status"""
    try:
        # Check database connectivity
        async with db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")

            # Test vector extension
            await conn.fetchval("SELECT '[1,2,3]'::vector(3)")

            # Test AGE extension
            await conn.fetchval("SELECT ag_catalog.agtype_in('1')")

        # Check projector lag (basic health indicator)
        lag_data = await event_persistence.get_projector_lag()

        # Update metrics
        metrics.update_database_connections(db_pool.get_size())
        for projector, info in lag_data.get("projectors", {}).items():
            metrics.update_projector_lag(projector, info.get("lag", 0))

        return {
            "status": "healthy",
            "version": "2.0.0",
            "components": {
                "database": {"status": "up", "version": version.split(" ")[1], "latency_ms": 2},
                "vector_extension": {"status": "healthy"},
                "age_extension": {"status": "healthy"},
                "projector_lag": lag_data,
            },
        }
    except Exception as e:
        print(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.post("/v1/events", response_model=EventAccepted)
async def create_event(
    envelope: EventEnvelope,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-Id"),
) -> EventAccepted:
    """Append event to event log with comprehensive validation"""

    # Generate correlation ID if not provided
    import uuid

    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    with metrics.request_in_progress("/v1/events") as tracker:
        try:
            # Record event size for monitoring
            envelope_json = json.dumps(envelope.dict())
            metrics.record_event_size(len(envelope_json.encode("utf-8")))

            # Validate headers
            headers = EventValidationMiddleware.validate_headers(idempotency_key, correlation_id)

            # Validate envelope structure
            validated_envelope = EventValidationMiddleware.validate_envelope(envelope.dict())

            # Store event with idempotency checking
            result = await event_persistence.store_event(validated_envelope, headers)

            # Record metrics
            metrics.record_event_created(envelope.world_id, envelope.branch, envelope.kind)

            tracker.set_status_code(201)
            return EventAccepted(
                event_id=result["event_id"],
                global_seq=result["global_seq"],
                received_at=result["received_at"],
                correlation_id=correlation_id,
            )

        except ConflictError as e:
            # Return 409 for idempotency conflicts
            tracker.set_status_code(409)
            metrics.record_idempotency_conflict(envelope.world_id, envelope.branch)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": str(e),
                    "correlation_id": correlation_id,
                },
            )
        except ValidationError as e:
            tracker.set_status_code(400)
            metrics.record_validation_error(envelope.world_id, envelope.branch)
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "validation_error",
                    "message": str(e),
                    "correlation_id": correlation_id,
                },
            )
        except Exception as e:
            tracker.set_status_code(500)
            print(f"Event creation failed: {e}")
            metrics.record_internal_error()
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "internal_error",
                    "message": "Internal server error",
                    "correlation_id": correlation_id,
                },
            )


@app.get("/v1/events", response_model=EventListResponse)
async def list_events(
    world_id: str,
    branch: str = "main",
    kind: Optional[str] = None,
    after_global_seq: Optional[int] = None,
    limit: int = 100,
):
    """List events with pagination and filtering"""
    with metrics.request_in_progress("/v1/events") as tracker:
        try:
            # Validate parameters
            RequestValidator.validate_world_id(world_id)
            params = RequestValidator.validate_pagination_params(after_global_seq, limit)

            events = await event_persistence.list_events(
                world_id, branch, kind, params["after_global_seq"], params["limit"]
            )

            return {
                "items": events,
                "next_after_global_seq": events[-1]["global_seq"] if events else None,
                "has_more": len(events) == params["limit"],
            }

        except ValidationError as e:
            tracker.set_status_code(400)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            tracker.set_status_code(500)
            print(f"Event listing failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/events/{event_id}")
async def get_event(event_id: str):
    """Get specific event by ID"""
    with metrics.request_in_progress("/v1/events/{id}") as tracker:
        try:
            # Validate event ID
            RequestValidator.validate_event_id(event_id)

            event = await event_persistence.get_event_by_id(event_id)
            if not event:
                tracker.set_status_code(404)
                raise HTTPException(status_code=404, detail="Event not found")

            return event

        except HTTPException:
            raise
        except ValidationError as e:
            tracker.set_status_code(400)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            tracker.set_status_code(500)
            print(f"Event retrieval failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return generate_latest().decode("utf-8"), {"content-type": CONTENT_TYPE_LATEST}


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "MnemonicNexus V2 Gateway",
        "version": "2.0.0",
        "phase": "A6 - Gateway 409 Handling",
        "status": "ready",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {"events": "/v1/events", "metrics": "/metrics", "admin": "/admin"},
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Standardized error response format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": (
                getattr(exc.detail, "code", "http_error")
                if isinstance(exc.detail, dict)
                else "http_error"
            ),
            "message": (
                getattr(exc.detail, "message", str(exc.detail))
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
            "correlation_id": (
                getattr(exc.detail, "correlation_id", None)
                if isinstance(exc.detail, dict)
                else None
            ),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")

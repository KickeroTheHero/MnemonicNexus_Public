#!/usr/bin/env python3
"""
MoE Controller Service Main Entry Point - PR-4

HTTP service wrapper around the Single-MoE Controller with health endpoints,
Prometheus metrics, and proper async lifecycle management.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from mnx.inference.moe_controller.client_lmstudio import LMStudioClient  # noqa: E402
from mnx.inference.moe_controller.controller import MoEController  # noqa: E402
from mnx.inference.moe_controller.event_emitter import (
    DecisionEventEmitter,
)  # noqa: E402
from mnx.inference.moe_controller.tool_bus import ToolBus  # noqa: E402
from mnx.inference.moe_controller.validators import JSONValidator  # noqa: E402

# Configure logging first
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("moe_controller")

# Monitoring disabled to maintain import boundaries - MoE Controller is independent
ServiceMonitoring = None
logger.warning("⚠️ ServiceMonitoring disabled - maintaining import boundaries")

app = FastAPI(
    title="MoE Controller Service",
    description="Single-MoE Controller for structured decision making with lens integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if os.getenv("ENVIRONMENT", "production") != "production" else []
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
controller: MoEController | None = None
monitoring: ServiceMonitoring | None = None


class DecisionRequest(BaseModel):
    """Request model for decision endpoint"""

    query: str
    world_id: str
    branch: str = "main"
    correlation_id: str | None = None
    rank_version: str = "v1"


class DecisionResponse(BaseModel):
    """Response model for decision endpoint"""

    success: bool
    decision_record: dict[str, Any] | None = None
    error: str | None = None
    correlation_id: str | None = None
    duration_ms: float
    validation_failed: bool = False


@app.on_event("startup")
async def startup_event():
    """Initialize controller service and dependencies"""
    global controller, monitoring

    logger.info("🚀 Starting MoE Controller Service...")

    try:
        # Initialize monitoring (optional)
        if ServiceMonitoring:
            monitoring = ServiceMonitoring(
                service_name="moe_controller", version="1.0.0", phase="S0"
            )
            logger.info("✅ Monitoring initialized")
        else:
            monitoring = None
            logger.info("⚠️ Monitoring disabled - ServiceMonitoring not available")

        # Initialize LM Studio client
        lm_studio_endpoint = os.getenv(
            "LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/completions"
        )
        lm_model = os.getenv(
            "LMSTUDIO_MODEL", "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
        )

        lm_client = LMStudioClient(endpoint=lm_studio_endpoint, model=lm_model)
        logger.info(f"✅ LM Studio client configured: {lm_studio_endpoint}")

        # Initialize tool bus
        tool_bus = ToolBus()
        await tool_bus.initialize_db_pool()
        logger.info("✅ Tool bus initialized with database pool")

        # Initialize event emitter
        gateway_endpoint = os.getenv("GATEWAY_ENDPOINT", "http://localhost:8081")
        event_emitter = DecisionEventEmitter(gateway_endpoint=gateway_endpoint)
        logger.info(f"✅ Event emitter configured: {gateway_endpoint}")

        # Initialize JSON validator
        validator = JSONValidator()
        logger.info("✅ JSON schema validator initialized")

        # Initialize controller
        controller = MoEController(
            lm_client=lm_client,
            tool_bus=tool_bus,
            event_emitter=event_emitter,
            validator=validator,
        )
        logger.info("✅ MoE Controller initialized successfully")

        logger.info("🎯 MoE Controller Service ready for requests!")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources"""
    global controller

    logger.info("🛑 Shutting down MoE Controller Service...")

    try:
        if controller and controller.tool_bus:
            await controller.tool_bus.close_db_pool()
            logger.info("✅ Database pool closed")

        logger.info("✅ MoE Controller Service shutdown complete")

    except Exception as e:
        logger.warning(f"⚠️ Shutdown warning: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    if not controller:
        raise HTTPException(status_code=503, detail="Controller not initialized")

    # Quick health checks
    health_status = {
        "status": "healthy",
        "service": "moe_controller",
        "version": "1.0.0",
        "timestamp": time.time(),
        "components": {
            "controller": controller is not None,
            "tool_bus": (
                controller.tool_bus._db_pool_initialized if controller else False
            ),
            "lm_client": controller.lm_client is not None if controller else False,
        },
    }

    # Check if any critical components are down
    if not all(health_status["components"].values()):
        raise HTTPException(status_code=503, detail="Service components unhealthy")

    return health_status


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    if not monitoring:
        raise HTTPException(status_code=503, detail="Monitoring not initialized")

    # Return Prometheus metrics format
    return Response(
        content=monitoring.generate_prometheus_output(),
        media_type="text/plain; charset=utf-8",
    )


@app.post("/v1/decisions", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest):
    """
    Primary decision endpoint - processes query through MoE controller

    Takes a user query and context, executes tool calls via lens integration,
    generates structured brief, and emits decision record to gateway.
    """
    if not controller:
        raise HTTPException(status_code=503, detail="Controller not initialized")

    start_time = time.time()

    try:
        # Generate correlation ID if not provided
        correlation_id = request.correlation_id or f"ctrl-{int(time.time()*1000)}"

        logger.info(
            f"🎯 Decision request: {request.query[:100]}... (correlation: {correlation_id})"
        )

        # Execute decision through controller
        decision_record = await controller.make_decision(
            query=request.query,
            world_id=request.world_id,
            branch=request.branch,
            correlation_id=correlation_id,
            rank_version=request.rank_version,
        )

        duration_ms = (time.time() - start_time) * 1000

        # Record metrics
        if monitoring:
            outcome = (
                "validation_failed"
                if decision_record.get("validation_failed")
                else "ok"
            )
            monitoring.record_controller_decision(outcome, duration_ms)

        logger.info(
            f"✅ Decision completed in {duration_ms:.1f}ms (correlation: {correlation_id})"
        )

        return DecisionResponse(
            success=True,
            decision_record=decision_record,
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            validation_failed=decision_record.get("validation_failed", False),
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # Record error metrics
        if monitoring:
            monitoring.record_controller_decision("error", duration_ms)

        logger.error(
            f"❌ Decision failed: {e} (correlation: {correlation_id or 'unknown'})"
        )

        return DecisionResponse(
            success=False,
            error=str(e),
            correlation_id=correlation_id if "correlation_id" in locals() else None,
            duration_ms=duration_ms,
        )


@app.get("/v1/status")
async def service_status():
    """Detailed service status for debugging and monitoring"""
    if not controller:
        raise HTTPException(status_code=503, detail="Controller not initialized")

    return {
        "service": "moe_controller",
        "version": "1.0.0",
        "phase": "S0",
        "timestamp": time.time(),
        "configuration": {
            "lmstudio_endpoint": os.getenv(
                "LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/completions"
            ),
            "lmstudio_model": os.getenv(
                "LMSTUDIO_MODEL", "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
            ),
            "gateway_endpoint": os.getenv("GATEWAY_ENDPOINT", "http://localhost:8081"),
            "tool_timeout_ms": os.getenv("TOOL_TIMEOUT_MS", "8000"),
            "tool_row_cap": os.getenv("TOOL_ROW_CAP", "200"),
            "rag_enabled": os.getenv("RAG_ENABLE", "0") == "1",
        },
        "tool_bus_config": controller.tool_bus.get_config() if controller else None,
        "uptime_seconds": time.time()
        - (getattr(controller, "_start_time", time.time())),
    }


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "MoE Controller Service",
        "version": "1.0.0",
        "description": "Single-MoE Controller for structured decision making",
        "endpoints": {
            "decisions": "/v1/decisions",
            "health": "/health",
            "metrics": "/metrics",
            "status": "/v1/status",
            "docs": "/docs",
        },
    }


if __name__ == "__main__":
    host = os.getenv("CONTROLLER_HOST", "0.0.0.0")
    port = int(os.getenv("CONTROLLER_PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(f"🚀 Starting MoE Controller Service on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False,  # Disable reload in production
    )

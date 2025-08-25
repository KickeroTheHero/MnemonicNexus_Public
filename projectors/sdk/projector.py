import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directories to path for common imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from services.common.tenancy import TenancyManager
except ImportError:  # pragma: no cover - runtime fallback
    # Fallback for when running projector independently
    TenancyManager = None  # type: ignore[assignment]

try:
    from monitoring import MetricsIntegration
except ImportError:
    from .monitoring import MetricsIntegration


class EventPayload(BaseModel):
    """Event payload received from CDC Publisher"""

    global_seq: int
    event_id: str
    envelope: Dict[str, Any]
    payload_hash: Optional[str] = None


class EventResponse(BaseModel):
    """Response sent back to CDC Publisher"""

    status: str
    global_seq: int
    message: Optional[str] = None


class ProjectorSDK(ABC):
    """Base class for all V2 projectors with HTTP event reception"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_pool = None
        self.running = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = FastAPI(title=f"Projector {self.name}")
        self.metrics = MetricsIntegration(self.name)
        self._setup_routes()

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique projector identifier"""
        pass

    @property
    @abstractmethod
    def lens(self) -> str:
        """Target lens: 'rel', 'sem', 'graph'"""
        pass

    @abstractmethod
    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to lens with idempotency guarantee"""
        pass

    def _setup_routes(self):
        """Setup FastAPI routes for event reception"""

        @self.app.post("/events", response_model=EventResponse)
        async def receive_event(event_data: EventPayload):
            """Receive event from CDC Publisher"""
            start_time = time.time()
            try:
                # Verify payload integrity if hash provided
                if event_data.payload_hash:
                    if not self._verify_payload_hash(
                        event_data.envelope, event_data.payload_hash
                    ):
                        raise HTTPException(
                            status_code=400, detail="Payload hash mismatch"
                        )

                # Set tenant context for RLS enforcement
                world_id = UUID(event_data.envelope["world_id"])
                if TenancyManager is not None and self.db_pool is not None:
                    async with self.db_pool.acquire() as conn:
                        await TenancyManager.set_world_context(conn, world_id)

                # Apply event idempotently
                await self.apply(event_data.envelope, event_data.global_seq)

                # Update watermark after successful processing
                await self.set_watermark(
                    event_data.envelope["world_id"],
                    event_data.envelope["branch"],
                    event_data.global_seq,
                )

                # Record metrics
                duration = time.time() - start_time
                self.metrics.record_processing(
                    event_data.envelope["world_id"],
                    event_data.envelope["branch"],
                    event_data.envelope["kind"],
                    duration,
                )

                self.logger.debug(
                    f"Processed event {event_data.global_seq} for {event_data.envelope['world_id']}/{event_data.envelope['branch']}"
                )
                return EventResponse(
                    status="processed", global_seq=event_data.global_seq
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to process event {event_data.global_seq}: {e}"
                )
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            watermark_count = await self._get_watermark_count()
            return {
                "service": f"projector-{self.lens}",
                "status": "healthy",
                "projector_name": self.name,
                "lens": self.lens,
                "watermark_count": watermark_count,
            }

        @self.app.get("/metrics")
        async def metrics():
            """Metrics endpoint for monitoring"""
            base_metrics = await self._get_metrics_data()
            prometheus_summary = self.metrics.get_metrics_summary()
            return {**base_metrics, **prometheus_summary}

    async def start(self):
        """Start projector HTTP server and background tasks"""
        self.running = True

        # Initialize database pool with AGE extension loading
        async def init_connection(conn):
            """Initialize each database connection with AGE extension"""
            try:
                await conn.execute("LOAD 'age'")
                await conn.execute("SET search_path TO ag_catalog, public")
            except Exception as e:
                # Log but don't fail - not all projectors need AGE
                self.logger.debug(
                    f"AGE extension initialization failed (non-graph projector?): {e}"
                )

        self.db_pool = await asyncpg.create_pool(
            self.config["database_url"], init=init_connection
        )

        self.logger.info(
            f"Starting projector {self.name} on port {self.config.get('port', 8000)}"
        )

        # Start background monitoring tasks
        background_tasks = [
            asyncio.create_task(self._state_hash_monitor()),
            asyncio.create_task(self._metrics_updater()),
            asyncio.create_task(self.metrics.start_background_updater(self.db_pool)),
        ]

        # Start FastAPI server
        config = uvicorn.Config(
            self.app,
            host=self.config.get("host", "0.0.0.0"),
            port=self.config.get("port", 8000),
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Run server and background tasks concurrently
        try:
            await asyncio.gather(server.serve(), *background_tasks)
        finally:
            self.running = False
            if self.db_pool:
                await self.db_pool.close()

    def _verify_payload_hash(
        self, envelope: Dict[str, Any], expected_hash: str
    ) -> bool:
        """Verify payload integrity against expected hash"""
        # Remove server-added fields for canonical hashing
        canonical_envelope = {
            k: v
            for k, v in envelope.items()
            if k not in ["received_at", "payload_hash"]
        }

        canonical_json = json.dumps(
            canonical_envelope, sort_keys=True, separators=(",", ":")
        )
        computed_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return computed_hash == expected_hash

    async def _get_watermark_count(self) -> int:
        """Get total number of watermarks tracked by this projector"""
        if not self.db_pool:
            return 0

        async with self.db_pool.acquire() as conn:
            return (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM event_core.projector_watermarks 
                WHERE projector_name = $1
            """,
                    self.name,
                )
                or 0
            )

    async def _get_metrics_data(self) -> Dict[str, Any]:
        """Get current metrics data for monitoring"""
        if not self.db_pool:
            return {
                "projector_name": self.name,
                "lens": self.lens,
                "watermark_count": 0,
                "watermarks": [],
                "last_activity": None,
            }

        async with self.db_pool.acquire() as conn:
            watermarks = await conn.fetch(
                """
                SELECT world_id, branch, last_processed_seq, updated_at
                FROM event_core.projector_watermarks 
                WHERE projector_name = $1
                ORDER BY updated_at DESC
            """,
                self.name,
            )

            return {
                "projector_name": self.name,
                "lens": self.lens,
                "watermark_count": len(watermarks),
                "watermarks": [dict(w) for w in watermarks],
                "last_activity": (
                    watermarks[0]["updated_at"].isoformat() if watermarks else None
                ),
            }

    async def _state_hash_monitor(self):
        """Background task to monitor state hashing"""
        while self.running:
            try:
                # Implementation specific to projector type
                await asyncio.sleep(self.config.get("state_hash_interval_s", 300))
            except Exception as e:
                self.logger.error(f"State hash monitoring error: {e}")
                await asyncio.sleep(60)

    async def _metrics_updater(self):
        """Background task to update metrics"""
        while self.running:
            try:
                # Update Prometheus metrics here
                await asyncio.sleep(self.config.get("metrics_update_interval_s", 30))
            except Exception as e:
                self.logger.error(f"Metrics update error: {e}")
                await asyncio.sleep(60)

    async def get_watermark(self, world_id: str, branch: str) -> int:
        """Get current processing watermark for (world_id, branch)"""
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT last_processed_seq 
                FROM event_core.projector_watermarks 
                WHERE projector_name = $1 AND world_id = $2 AND branch = $3
            """,
                self.name,
                world_id,
                branch,
            )

            return result or 0

    async def set_watermark(self, world_id: str, branch: str, global_seq: int) -> None:
        """Update processing watermark for (world_id, branch)"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_core.projector_watermarks 
                (projector_name, world_id, branch, last_processed_seq, updated_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (projector_name, world_id, branch) 
                DO UPDATE SET 
                    last_processed_seq = EXCLUDED.last_processed_seq,
                    updated_at = EXCLUDED.updated_at
            """,
                self.name,
                world_id,
                branch,
                global_seq,
            )

    async def compute_state_hash(self, world_id: str, branch: str) -> str:
        """Compute deterministic state hash for replay validation"""
        # Base implementation - subclasses can override for lens-specific logic
        async with self.db_pool.acquire() as conn:
            # Get deterministic snapshot of projector state
            state_data = await self._get_state_snapshot(conn, world_id, branch)

            # Create canonical hash
            canonical = json.dumps(state_data, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @abstractmethod
    async def _get_state_snapshot(
        self, conn: asyncpg.Connection, world_id: str, branch: str
    ) -> Dict[str, Any]:
        """Get deterministic snapshot of projector state for hashing"""
        pass

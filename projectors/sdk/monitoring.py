import asyncio
import logging
from typing import Any, Dict

import asyncpg
from prometheus_client import Counter, Gauge, Histogram  # type: ignore[import-untyped]


class ProjectorMetrics:
    """Prometheus metrics for projector monitoring"""

    def __init__(self, projector_name: str):
        self.projector_name = projector_name

        self.events_processed = Counter(
            "projector_events_processed_total",
            "Total events processed by projector",
            ["projector", "world_id", "branch", "kind"],
        )

        self.processing_lag = Gauge(
            "projector_lag_seconds",
            "Time lag between event creation and processing",
            ["projector", "world_id", "branch"],
        )

        self.watermark_position = Gauge(
            "projector_watermark",
            "Current watermark position",
            ["projector", "world_id", "branch"],
        )

        self.state_hash = Gauge(
            "projector_state_hash",
            "Numeric representation of state hash for monitoring",
            ["projector", "world_id", "branch"],
        )

        self.processing_duration = Histogram(
            "projector_event_duration_seconds",
            "Time taken to process individual events",
            ["projector", "kind"],
        )

    def record_event_processed(
        self, world_id: str, branch: str, kind: str, duration: float
    ):
        """Record successful event processing"""
        self.events_processed.labels(
            projector=self.projector_name, world_id=world_id, branch=branch, kind=kind
        ).inc()

        self.processing_duration.labels(
            projector=self.projector_name, kind=kind
        ).observe(duration)

    async def update_lag_metrics(self, db_pool: asyncpg.Pool):
        """Periodically update lag and watermark metrics"""
        while True:
            try:
                async with db_pool.acquire() as conn:
                    # Get lag data per (world_id, branch)
                    lag_data = await conn.fetch(
                        """
                        SELECT 
                            w.world_id,
                            w.branch,
                            w.last_processed_seq as watermark,
                            COALESCE(
                                EXTRACT(EPOCH FROM (now() - MAX(el.received_at))), 
                                0
                            ) as lag_seconds
                        FROM event_core.projector_watermarks w
                        LEFT JOIN event_core.event_log el ON (
                            el.world_id = w.world_id 
                            AND el.branch = w.branch 
                            AND el.global_seq <= w.last_processed_seq
                        )
                        WHERE w.projector_name = $1
                        GROUP BY w.world_id, w.branch, w.last_processed_seq
                    """,
                        self.projector_name,
                    )

                    for row in lag_data:
                        self.processing_lag.labels(
                            projector=self.projector_name,
                            world_id=str(row["world_id"]),
                            branch=row["branch"],
                        ).set(row["lag_seconds"])

                        self.watermark_position.labels(
                            projector=self.projector_name,
                            world_id=str(row["world_id"]),
                            branch=row["branch"],
                        ).set(row["watermark"])

            except Exception as e:
                logging.error(f"Metrics update failed: {e}")

            await asyncio.sleep(30)


class MetricsIntegration:
    """Integration helper for Prometheus metrics with ProjectorSDK"""

    def __init__(self, projector_name: str):
        self.metrics = ProjectorMetrics(projector_name)
        self.logger = logging.getLogger(f"{projector_name}.metrics")

    async def start_background_updater(self, db_pool: asyncpg.Pool):
        """Start background metrics updater task"""
        try:
            await self.metrics.update_lag_metrics(db_pool)
        except Exception as e:
            self.logger.error(f"Background metrics updater failed: {e}")

    def record_processing(self, world_id: str, branch: str, kind: str, duration: float):
        """Record event processing metrics"""
        self.metrics.record_event_processed(world_id, branch, kind, duration)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics for health endpoint"""
        return {
            "metrics_enabled": True,
            "events_processed_counter": "projector_events_processed_total",
            "processing_lag_gauge": "projector_lag_seconds",
            "watermark_gauge": "projector_watermark",
            "processing_duration_histogram": "projector_event_duration_seconds",
        }

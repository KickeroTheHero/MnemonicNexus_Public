"""Publisher monitoring and metrics module."""

import asyncio
import logging
from typing import TYPE_CHECKING

import asyncpg
from prometheus_client import (  # type: ignore[import-untyped]
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

if TYPE_CHECKING:
    pass


class PublisherMetrics:
    """Prometheus metrics for publisher monitoring."""

    def __init__(self) -> None:
        self.events_published = Counter(
            "cdc_events_published_total",
            "Total events published successfully",
            ["world_id", "branch", "projector"],
        )
        self.events_failed = Counter(
            "cdc_events_failed_total",
            "Total events that failed delivery",
            ["world_id", "branch", "error_type"],
        )
        self.outbox_lag = Gauge(
            "cdc_outbox_lag_seconds",
            "Time lag between event creation and publishing",
            ["world_id", "branch"],
        )
        self.publish_duration = Histogram(
            "cdc_publish_duration_seconds",
            "Time taken to publish event batch",
            ["batch_size"],
        )
        self.dlq_count = Gauge("cdc_dlq_messages_total", "Number of messages in dead letter queue")


class MetricsUpdater:
    """Handles periodic metrics updates from database."""

    def __init__(self, metrics: PublisherMetrics, db_pool: asyncpg.Pool) -> None:
        self.metrics = metrics
        self.pool = db_pool
        self.running = False
        self.logger = logging.getLogger("publisher_v2.metrics")

    async def start_metrics_server(self, port: int = 9100) -> None:
        """Start Prometheus metrics HTTP server."""
        start_http_server(port)
        self.logger.info("Metrics server started on port %d", port)

    async def start_periodic_updates(self) -> None:
        """Start the periodic metrics update loop."""
        self.running = True
        while self.running:
            try:
                await self._update_lag_metrics()
                await self._update_dlq_metrics()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Metrics update failed: %s", exc)
            await asyncio.sleep(30)

    async def stop(self) -> None:
        """Stop the metrics updater."""
        self.running = False

    async def _update_lag_metrics(self) -> None:
        """Update lag metrics from database."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    el.world_id,
                    el.branch,
                    EXTRACT(EPOCH FROM (now() - MIN(el.received_at))) AS lag_seconds
                FROM event_core.event_log el
                WHERE NOT EXISTS (
                    SELECT 1 FROM event_core.outbox o 
                    WHERE o.global_seq = el.global_seq AND o.published_at IS NOT NULL
                )
                GROUP BY el.world_id, el.branch
                """
            )
            for r in rows:
                self.metrics.outbox_lag.labels(world_id=str(r["world_id"]), branch=r["branch"]).set(
                    float(r["lag_seconds"] or 0.0)
                )

    async def _update_dlq_metrics(self) -> None:
        """Update DLQ count from database."""
        async with self.pool.acquire() as conn:
            dlq_count_row = await conn.fetchval("SELECT COUNT(*) FROM event_core.dead_letter_queue")
            self.metrics.dlq_count.set(int(dlq_count_row))

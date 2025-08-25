import asyncio
import logging
import os
from typing import Any, Dict, List

import aiohttp
import asyncpg
from aiohttp import web

from config import PublisherConfig
from monitoring import MetricsUpdater, PublisherMetrics


class CDCPublisher:
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        config: PublisherConfig,
        metrics: PublisherMetrics,
        metrics_updater: MetricsUpdater,
    ) -> None:
        self.pool = db_pool
        self.config = config
        self.metrics = metrics
        self.metrics_updater = metrics_updater
        self.running = False
        self.logger = logging.getLogger("publisher_v2")

    async def start(self) -> None:
        self.running = True
        self.logger.info("CDC Publisher starting...")
        tasks: List[asyncio.Task[Any]] = [
            asyncio.create_task(self._poll_outbox()),
            asyncio.create_task(self.metrics_updater.start_periodic_updates()),
        ]
        await asyncio.gather(*tasks)

    async def _poll_outbox(self) -> None:
        while self.running:
            try:
                batch = await self._fetch_unpublished_batch()
                if batch:
                    await self._process_batch(batch)
                else:
                    await asyncio.sleep(self.config.poll_interval_ms / 1000)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Outbox polling error: %s", exc)
                await asyncio.sleep(5)

    async def _fetch_unpublished_batch(self) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM event_core.get_unpublished_batch($1)",
                self.config.batch_size,
            )
        return [dict(r) for r in rows]

    async def _process_batch(self, batch: List[Dict[str, Any]]) -> None:
        publish_tasks = [asyncio.create_task(self._publish_event(ev)) for ev in batch]
        results: List[object] = list(
            await asyncio.gather(*publish_tasks, return_exceptions=True)
        )
        await self._update_publish_status(batch, results)

    async def _publish_event(self, event: Dict[str, Any]) -> bool:
        success = True
        for endpoint in self._get_projector_endpoints(
            event["world_id"], event["branch"]
        ):
            try:
                await self._send_to_projector(event, endpoint)
                self.metrics.events_published.labels(
                    world_id=str(event["world_id"]),
                    branch=event["branch"],
                    projector=endpoint,
                ).inc()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed to send to %s: %s", endpoint, exc)
                self.metrics.events_failed.labels(
                    world_id=str(event["world_id"]),
                    branch=event["branch"],
                    error_type=exc.__class__.__name__,
                ).inc()
                success = False
        return success

    async def _send_to_projector(self, event: Dict[str, Any], endpoint: str) -> None:
        # Ensure envelope is a dict, not a JSON string
        envelope = event["envelope"]
        if isinstance(envelope, str):
            import json

            envelope = json.loads(envelope)

        payload = {
            "global_seq": event["global_seq"],
            "event_id": str(event["event_id"]),
            "envelope": envelope,
            "payload_hash": event.get("payload_hash"),
        }
        timeout = aiohttp.ClientTimeout(total=self.config.projector_timeout_ms / 1000)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{endpoint}/events",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Publisher-ID": self.config.publisher_id,
                },
            ) as resp:
                if resp.status not in (200, 202):
                    text = await resp.text()
                    raise RuntimeError(f"Projector returned {resp.status}: {text}")

    async def _update_publish_status(
        self, batch: List[Dict[str, Any]], results: List[object]
    ) -> None:
        async with self.pool.acquire() as conn:
            for event, result in zip(batch, results):
                if result is True:
                    await conn.execute(
                        "SELECT event_core.mark_published($1)", event["global_seq"]
                    )
                else:
                    err = str(result)
                    ok = await conn.fetchval(
                        "SELECT event_core.mark_retry($1, $2, $3)",
                        event["global_seq"],
                        err,
                        60,
                    )
                    if not ok:
                        await conn.execute(
                            "SELECT event_core.move_to_dlq($1, $2, $3)",
                            event["global_seq"],
                            err,
                            self.config.publisher_id,
                        )

    def _get_projector_endpoints(
        self, world_id: Any, branch: str
    ) -> List[str]:  # noqa: ARG002
        return self.config.projector_endpoints


async def create_db_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=5)


async def start_health_server(config: PublisherConfig) -> web.AppRunner:
    async def handle_health(_: web.Request) -> web.Response:
        body = {
            "service": "publisher-v2",
            "status": "ok",
        }
        return web.json_response(body)

    app = web.Application()
    app.add_routes([web.get("/health", handle_health)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.health_port)
    await site.start()
    return runner


async def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = PublisherConfig()

    # Database pool
    pool = await create_db_pool(config.database_url)

    # Metrics
    metrics = PublisherMetrics()
    metrics_updater = MetricsUpdater(metrics, pool)

    # Start metrics HTTP server
    await metrics_updater.start_metrics_server(config.metrics_port)

    # Health server
    health_runner = await start_health_server(config)
    del health_runner  # not used further, kept for lifecycle

    # Publisher
    publisher = CDCPublisher(pool, config, metrics, metrics_updater)
    try:
        await publisher.start()
    finally:
        await metrics_updater.stop()
        await pool.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

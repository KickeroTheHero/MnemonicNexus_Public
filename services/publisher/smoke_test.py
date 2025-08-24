#!/usr/bin/env python3
"""
Smoke test for Publisher V2 - Creates synthetic events and verifies processing.
Tests the publisher against the event_core.outbox without requiring projectors.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("publisher_smoke_test")


class SmokeTest:
    """Smoke test for publisher functionality."""

    def __init__(
        self, database_url: str = "postgresql://postgres:postgres@localhost:5433/nexus_v2"
    ):
        self.database_url = database_url
        self.test_world_id = str(uuid.uuid4())
        self.test_branch = "smoke-test"

    async def run(self) -> None:
        """Run the complete smoke test."""
        logger.info("Starting Publisher V2 smoke test")
        logger.info("Test world_id: %s", self.test_world_id)
        logger.info("Test branch: %s", self.test_branch)

        pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        try:
            await self._cleanup_previous_tests(pool)
            await self._create_synthetic_events(pool)
            await self._verify_outbox_entries(pool)
            await self._verify_publisher_processing(pool)
            logger.info("✅ Smoke test completed successfully")
        except Exception as exc:
            logger.error("❌ Smoke test failed: %s", exc)
            raise
        finally:
            await pool.close()

    async def _cleanup_previous_tests(self, pool: asyncpg.Pool) -> None:
        """Clean up any previous test data."""
        logger.info("Cleaning up previous test data...")
        async with pool.acquire() as conn:
            # Clean up outbox
            await conn.execute(
                "DELETE FROM event_core.outbox WHERE envelope->>'world_id' = $1",
                self.test_world_id,
            )
            # Clean up event log
            await conn.execute(
                "DELETE FROM event_core.event_log WHERE world_id = $1",
                uuid.UUID(self.test_world_id),
            )
            # Clean up DLQ
            await conn.execute(
                "DELETE FROM event_core.dead_letter_queue WHERE envelope->>'world_id' = $1",
                self.test_world_id,
            )

    async def _create_synthetic_events(self, pool: asyncpg.Pool, count: int = 5) -> None:
        """Create synthetic events in the outbox."""
        logger.info("Creating %d synthetic events...", count)
        async with pool.acquire() as conn:
            for i in range(count):
                envelope = self._create_test_envelope(f"test-event-{i}")

                # Insert event using the same function the gateway uses
                global_seq = await conn.fetchval(
                    """
                    SELECT event_core.insert_event_with_outbox(
                        $1::UUID,  -- p_world_id
                        $2::TEXT,  -- p_branch
                        $3::UUID,  -- p_event_id
                        $4::TEXT,  -- p_kind
                        $5::JSONB, -- p_envelope
                        $6::timestamptz, -- p_occurred_at
                        $7::TEXT   -- p_idempotency_key
                    )
                    """,
                    uuid.UUID(self.test_world_id),
                    self.test_branch,
                    uuid.UUID(envelope["event_id"]),
                    envelope["kind"],
                    json.dumps(envelope),
                    datetime.fromisoformat(envelope["occurred_at"].replace("Z", "+00:00")),
                    f"smoke-test-{i}",  # idempotency key
                )
                logger.info("Created event %d with global_seq: %s", i, global_seq)

    async def _verify_outbox_entries(self, pool: asyncpg.Pool) -> None:
        """Verify that events were created in the outbox."""
        logger.info("Verifying outbox entries...")
        async with pool.acquire() as conn:
            outbox_count = await conn.fetchval(
                "SELECT COUNT(*) FROM event_core.outbox WHERE envelope->>'world_id' = $1",
                self.test_world_id,
            )
            logger.info("Found %d entries in outbox", outbox_count)

            if outbox_count == 0:
                raise ValueError("No events found in outbox")

            # Check that events are unpublished
            unpublished = await conn.fetch(
                "SELECT * FROM event_core.get_unpublished_batch(10, $1::UUID, $2)",
                uuid.UUID(self.test_world_id),
                self.test_branch,
            )
            logger.info("Found %d unpublished events", len(unpublished))

            for event in unpublished:
                logger.info(
                    "Unpublished event: global_seq=%s, event_id=%s",
                    event["global_seq"],
                    event["event_id"],
                )

    async def _verify_publisher_processing(self, pool: asyncpg.Pool) -> None:
        """Simulate publisher processing and verify behavior."""
        logger.info("Simulating publisher processing...")
        async with pool.acquire() as conn:
            # Get a batch of unpublished events
            batch = await conn.fetch(
                "SELECT * FROM event_core.get_unpublished_batch(3, $1::UUID, $2)",
                uuid.UUID(self.test_world_id),
                self.test_branch,
            )

            if not batch:
                logger.warning("No unpublished events found for processing simulation")
                return

            logger.info("Processing batch of %d events", len(batch))

            # Simulate successful processing of first event
            if len(batch) >= 1:
                await conn.execute(
                    "SELECT event_core.mark_published($1)",
                    batch[0]["global_seq"],
                )
                logger.info("Marked event %s as published", batch[0]["global_seq"])

            # Simulate retry of second event
            if len(batch) >= 2:
                await conn.execute(
                    "SELECT event_core.mark_retry($1, $2, $3)",
                    batch[1]["global_seq"],
                    "Simulated projector timeout",
                    60,
                )
                logger.info("Marked event %s for retry", batch[1]["global_seq"])

            # Simulate DLQ of third event (if we had exhausted retries)
            if len(batch) >= 3:
                await conn.execute(
                    "SELECT event_core.move_to_dlq($1, $2, $3)",
                    batch[2]["global_seq"],
                    "Simulated poison message",
                    "smoke-test-publisher",
                )
                logger.info("Moved event %s to DLQ", batch[2]["global_seq"])

            # Verify final state
            await self._verify_final_state(conn)

    async def _verify_final_state(self, conn: asyncpg.Connection) -> None:
        """Verify the final state after processing simulation."""
        logger.info("Verifying final state...")

        # Check published count
        published_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM event_core.outbox 
            WHERE envelope->>'world_id' = $1 AND published_at IS NOT NULL
            """,
            self.test_world_id,
        )
        logger.info("Published events: %d", published_count)

        # Check retry count
        retry_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM event_core.outbox 
            WHERE envelope->>'world_id' = $1 AND next_retry_at IS NOT NULL AND published_at IS NULL
            """,
            self.test_world_id,
        )
        logger.info("Events pending retry: %d", retry_count)

        # Check DLQ count
        dlq_count = await conn.fetchval(
            "SELECT COUNT(*) FROM event_core.dead_letter_queue WHERE envelope->>'world_id' = $1",
            self.test_world_id,
        )
        logger.info("Events in DLQ: %d", dlq_count)

        # Check remaining unpublished
        unpublished_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM event_core.outbox 
            WHERE envelope->>'world_id' = $1 AND published_at IS NULL AND next_retry_at IS NULL
            """,
            self.test_world_id,
        )
        logger.info("Unpublished events (not in retry): %d", unpublished_count)

    def _create_test_envelope(self, event_name: str) -> Dict[str, Any]:
        """Create a test event envelope that matches V2 specification."""
        event_id = str(uuid.uuid4())
        return {
            "event_id": event_id,
            "world_id": self.test_world_id,
            "branch": self.test_branch,
            "kind": "smoke_test.event_created",
            "payload": {
                "name": event_name,
                "test_data": {"counter": 42, "flag": True},
                "smoke_test": True,
            },
            "by": {"agent": "smoke-test-publisher"},
            "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload_hash": f"test-hash-{event_name}",
        }


async def main() -> None:
    """Run the smoke test."""
    smoke_test = SmokeTest()
    await smoke_test.run()


if __name__ == "__main__":
    asyncio.run(main())

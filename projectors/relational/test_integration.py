#!/usr/bin/env python3
"""
Integration test for Phase A5 Relational Projector
Tests the complete event flow: Gateway → Outbox → Publisher → Projector
"""
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone

import asyncpg
import requests

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProjectorIntegrationTest:
    def __init__(self):
        self.db_url = "postgresql://postgres:postgres@localhost:5433/nexus_v2"
        self.projector_url = "http://localhost:8083"
        self.publisher_url = "http://localhost:8082"
        self.test_world_id = "550e8400-e29b-41d4-a716-446655440001"
        self.test_branch = "main"

    async def run_tests(self):
        """Run complete integration test suite"""
        logger.info("🚀 Starting Phase A5 Projector Integration Tests")

        try:
            # Test 1: Health check
            await self.test_projector_health()

            # Test 2: Database connection
            await self.test_database_connection()

            # Test 3: Direct HTTP event posting
            await self.test_direct_event_posting()

            # Test 4: Watermark management
            await self.test_watermark_management()

            # Test 5: Event idempotency
            await self.test_event_idempotency()

            # Test 6: State hash computation
            await self.test_state_hash_computation()

            logger.info("✅ All Phase A5 integration tests passed!")

        except Exception as e:
            logger.error(f"❌ Integration tests failed: {e}")
            raise

    async def test_projector_health(self):
        """Test projector health endpoint"""
        logger.info("Testing projector health endpoint...")

        response = requests.get(f"{self.projector_url}/health", timeout=10)
        response.raise_for_status()

        health_data = response.json()
        assert health_data["service"] == "projector-rel"
        assert health_data["status"] == "healthy"
        assert health_data["projector_name"] == "projector_rel"
        assert health_data["lens"] == "rel"

        logger.info(f"✅ Projector health: {health_data}")

    async def test_database_connection(self):
        """Test database connection and schema"""
        logger.info("Testing database connection and schema...")

        pool = await asyncpg.create_pool(self.db_url)
        try:
            async with pool.acquire() as conn:
                # Test lens_rel tables exist
                tables = await conn.fetch(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'lens_rel'
                    ORDER BY table_name
                """
                )

                table_names = [row["table_name"] for row in tables]
                expected_tables = ["note", "note_tag", "link"]

                for table in expected_tables:
                    assert table in table_names, f"Missing table: lens_rel.{table}"

                # Test projector_watermarks table exists
                watermarks_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = 'event_core' AND table_name = 'projector_watermarks'
                    )
                """
                )
                assert (
                    watermarks_exists
                ), "Missing event_core.projector_watermarks table"

                logger.info(f"✅ Database schema validated. Tables: {table_names}")
        finally:
            await pool.close()

    async def test_direct_event_posting(self):
        """Test direct HTTP event posting to projector"""
        logger.info("Testing direct event posting...")

        # Create test event
        test_event = {
            "global_seq": 1001,
            "event_id": "test-event-001",
            "envelope": {
                "world_id": self.test_world_id,
                "branch": self.test_branch,
                "kind": "note.created",
                "payload": {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "title": "Test Note for Phase A5",
                    "body": "This note tests the projector integration.",
                },
                "by": {"agent": "integration-test"},
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "version": 1,
            },
        }

        # Post event to projector
        response = requests.post(
            f"{self.projector_url}/events",
            json=test_event,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        result = response.json()
        assert result["status"] == "processed"
        assert result["global_seq"] == 1001

        # Verify event was applied to database
        pool = await asyncpg.create_pool(self.db_url)
        try:
            async with pool.acquire() as conn:
                note = await conn.fetchrow(
                    """
                    SELECT * FROM lens_rel.note 
                    WHERE world_id = $1 AND branch = $2 AND note_id = $3
                """,
                    self.test_world_id,
                    self.test_branch,
                    "550e8400-e29b-41d4-a716-446655440002",
                )

                assert note is not None, "Note was not created in database"
                assert note["title"] == "Test Note for Phase A5"
                assert note["body"] == "This note tests the projector integration."

                logger.info(f"✅ Event processed and stored: {note['title']}")
        finally:
            await pool.close()

    async def test_watermark_management(self):
        """Test watermark tracking"""
        logger.info("Testing watermark management...")

        pool = await asyncpg.create_pool(self.db_url)
        try:
            async with pool.acquire() as conn:
                # Check watermark was set
                watermark = await conn.fetchval(
                    """
                    SELECT last_processed_seq 
                    FROM event_core.projector_watermarks 
                    WHERE projector_name = $1 AND world_id = $2 AND branch = $3
                """,
                    "projector_rel",
                    self.test_world_id,
                    self.test_branch,
                )

                assert watermark == 1001, f"Expected watermark 1001, got {watermark}"

                logger.info(f"✅ Watermark correctly set: {watermark}")
        finally:
            await pool.close()

    async def test_event_idempotency(self):
        """Test event processing idempotency"""
        logger.info("Testing event idempotency...")

        # Post the same event again
        test_event = {
            "global_seq": 1002,
            "event_id": "test-event-002",
            "envelope": {
                "world_id": self.test_world_id,
                "branch": self.test_branch,
                "kind": "note.created",
                "payload": {
                    "id": "550e8400-e29b-41d4-a716-446655440002",  # Same note ID
                    "title": "Updated Title",  # Different content
                    "body": "Updated body content.",
                },
                "by": {"agent": "integration-test"},
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "version": 1,
            },
        }

        # Post duplicate note.created event
        response = requests.post(
            f"{self.projector_url}/events",
            json=test_event,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        # Verify note content was NOT updated (idempotent)
        pool = await asyncpg.create_pool(self.db_url)
        try:
            async with pool.acquire() as conn:
                note = await conn.fetchrow(
                    """
                    SELECT * FROM lens_rel.note 
                    WHERE world_id = $1 AND branch = $2 AND note_id = $3
                """,
                    self.test_world_id,
                    self.test_branch,
                    "550e8400-e29b-41d4-a716-446655440002",
                )

                # Should still have original title, not "Updated Title"
                assert (
                    note["title"] == "Test Note for Phase A5"
                ), "Note was unexpectedly updated"

                logger.info(f"✅ Idempotency preserved: {note['title']}")
        finally:
            await pool.close()

    async def test_state_hash_computation(self):
        """Test deterministic state hash computation"""
        logger.info("Testing state hash computation...")

        # Create a projector instance to test hash computation
        from projectors.relational.projector import RelationalProjector
        from projectors.sdk.config import ProjectorConfig

        config = ProjectorConfig(database_url=self.db_url)
        projector = RelationalProjector(config.dict())

        # Initialize database pool
        projector.db_pool = await asyncpg.create_pool(self.db_url)

        try:
            # Compute state hash
            hash1 = await projector.compute_state_hash(
                self.test_world_id, self.test_branch
            )

            # Compute again - should be identical
            hash2 = await projector.compute_state_hash(
                self.test_world_id, self.test_branch
            )

            assert hash1 == hash2, "State hash is not deterministic"
            assert len(hash1) == 64, "State hash should be SHA-256 (64 hex chars)"

            logger.info(f"✅ Deterministic state hash: {hash1[:16]}...")

        finally:
            await projector.db_pool.close()

    async def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        logger.info("Testing metrics endpoint...")

        response = requests.get(f"{self.projector_url}/metrics", timeout=10)
        response.raise_for_status()

        metrics = response.json()
        assert metrics["projector_name"] == "projector_rel"
        assert metrics["lens"] == "rel"
        assert metrics["watermark_count"] >= 1
        assert len(metrics["watermarks"]) >= 1

        logger.info(
            f"✅ Metrics endpoint working: {metrics['watermark_count']} watermarks"
        )


async def main():
    """Main test runner"""
    test = ProjectorIntegrationTest()

    # Wait a bit for services to be ready
    logger.info("Waiting for services to be ready...")
    time.sleep(5)

    await test.run_tests()


if __name__ == "__main__":
    asyncio.run(main())

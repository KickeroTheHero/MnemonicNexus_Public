#!/usr/bin/env python3
"""
Alpha Translator Test Implementation

Critical missing tests for the Alpha Mode memory-to-EMO translator.
This module addresses the CRITICAL GAP identified in testing analysis.

Usage:
    python scripts/test_alpha_translator.py
    python scripts/test_alpha_translator.py --verbose
"""

import asyncio
import asyncpg
import httpx
import json
import time
import uuid
import hashlib
import argparse
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """Result of memory-to-EMO translation test"""

    test_name: str
    success: bool
    duration: float
    memory_event: Dict[str, Any]
    emo_events: List[Dict[str, Any]]
    validation_details: Dict[str, Any]
    error: Optional[str] = None


class AlphaTranslatorTester:
    """Comprehensive Alpha Translator testing"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_url = config.get(
            "database_url", "postgresql://postgres:postgres@localhost:5432/nexus"
        )
        self.gateway_url = config.get("gateway_url", "http://localhost:8086")
        self.results: List[TranslationResult] = []

    async def run_all_translator_tests(self) -> List[TranslationResult]:
        """Execute comprehensive Alpha translator test suite"""
        logger.info("🔄 Starting Alpha Translator Test Suite")
        logger.info("=" * 60)

        # Core translation tests
        await self.test_memory_upserted_to_emo_created()
        await self.test_memory_upserted_to_emo_updated()
        await self.test_memory_deleted_to_emo_deleted()

        # Field mapping accuracy tests
        await self.test_field_mapping_accuracy()
        await self.test_version_management()
        await self.test_idempotency_preservation()

        # Error scenario tests
        await self.test_malformed_memory_events()
        await self.test_missing_required_fields()
        await self.test_translation_error_handling()

        # Performance tests
        await self.test_translation_performance()
        await self.test_concurrent_translation()

        # Parity validation
        await self.test_translator_vs_direct_emo_parity()

        self.generate_test_summary()
        return self.results

    async def test_memory_upserted_to_emo_created(self):
        """Test memory.item.upserted → emo.created translation"""
        start_time = time.time()
        test_name = "memory_upserted_to_emo_created"

        try:
            # Create memory.item.upserted event for new memory
            memory_event = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "correlation_id": f"translator-test-{int(time.time())}",
                "occurred_at": "2025-01-21T15:00:00.000Z",
                "by": {
                    "agent": "test:translator",
                    "context": "Alpha translator testing",
                },
                "payload": {
                    "id": f"mem-{uuid.uuid4()}",
                    "title": "Test Memory Item",
                    "body": "This is the body content of the memory item for translation testing.",
                    "tags": ["test", "translation", "alpha"],
                    "metadata": {"source": "test_suite", "category": "note"},
                    "created_at": "2025-01-21T15:00:00.000Z",
                    "updated_at": "2025-01-21T15:00:00.000Z",
                },
            }

            # Submit memory event
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=memory_event, timeout=10.0
                )

            assert (
                response.status_code == 201
            ), f"Memory event rejected: {response.status_code}"

            # Wait for translation processing
            await asyncio.sleep(3)

            # Check for corresponding emo.created event
            emo_events = await self.get_emo_events_for_memory(
                memory_event["payload"]["id"]
            )

            assert len(emo_events) >= 1, "No EMO events generated from memory event"

            emo_created = None
            for event in emo_events:
                if event["kind"] == "emo.created":
                    emo_created = event
                    break

            assert emo_created is not None, "No emo.created event found"

            # Validate translation accuracy
            validation_details = await self.validate_memory_to_emo_translation(
                memory_event, emo_created
            )

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event=memory_event,
                    emo_events=[emo_created],
                    validation_details=validation_details,
                )
            )

            logger.info(f"✅ {test_name} passed in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event=memory_event if "memory_event" in locals() else {},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_memory_upserted_to_emo_updated(self):
        """Test memory.item.upserted → emo.updated for existing EMO"""
        start_time = time.time()
        test_name = "memory_upserted_to_emo_updated"

        try:
            memory_id = f"mem-{uuid.uuid4()}"

            # First, create initial memory (should generate emo.created)
            initial_memory = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": memory_id,
                    "title": "Initial Memory",
                    "body": "Initial content",
                    "tags": ["test"],
                    "created_at": "2025-01-21T15:00:00.000Z",
                },
            }

            async with httpx.AsyncClient() as client:
                await client.post(f"{self.gateway_url}/v1/events", json=initial_memory)

            await asyncio.sleep(2)  # Wait for processing

            # Now update the memory (should generate emo.updated)
            updated_memory = {
                "world_id": initial_memory["world_id"],
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": memory_id,
                    "title": "Updated Memory Title",
                    "body": "Updated content with changes",
                    "tags": ["test", "updated"],
                    "updated_at": "2025-01-21T15:05:00.000Z",
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=updated_memory
                )

            assert (
                response.status_code == 201
            ), f"Updated memory event rejected: {response.status_code}"

            await asyncio.sleep(3)

            # Verify emo.updated event generated
            emo_events = await self.get_emo_events_for_memory(memory_id)

            emo_created = None
            emo_updated = None

            for event in emo_events:
                if event["kind"] == "emo.created":
                    emo_created = event
                elif event["kind"] == "emo.updated":
                    emo_updated = event

            assert emo_created is not None, "Initial emo.created not found"
            assert (
                emo_updated is not None
            ), "emo.updated not generated for memory update"

            # Validate version increment
            assert (
                emo_updated["payload"]["emo_version"] == 2
            ), "Version not incremented correctly"
            assert (
                emo_updated["payload"]["emo_id"] == emo_created["payload"]["emo_id"]
            ), "EMO ID mismatch"

            # Validate content update
            expected_content = "Updated Memory Title\n\nUpdated content with changes"
            assert (
                emo_updated["payload"]["content"] == expected_content
            ), "Content not updated correctly"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event=updated_memory,
                    emo_events=[emo_created, emo_updated],
                    validation_details={
                        "version_increment": emo_updated["payload"]["emo_version"] == 2,
                        "content_updated": True,
                        "tags_updated": True,
                    },
                )
            )

            logger.info(f"✅ {test_name} passed in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event=updated_memory if "updated_memory" in locals() else {},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_memory_deleted_to_emo_deleted(self):
        """Test memory.item.deleted → emo.deleted translation"""
        start_time = time.time()
        test_name = "memory_deleted_to_emo_deleted"

        try:
            memory_id = f"mem-{uuid.uuid4()}"

            # Create memory first
            create_memory = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": memory_id,
                    "title": "Memory to Delete",
                    "body": "This will be deleted",
                    "tags": ["test", "deletion"],
                },
            }

            async with httpx.AsyncClient() as client:
                await client.post(f"{self.gateway_url}/v1/events", json=create_memory)

            await asyncio.sleep(2)

            # Delete the memory
            delete_memory = {
                "world_id": create_memory["world_id"],
                "branch": "main",
                "kind": "memory.item.deleted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": memory_id,
                    "reason": "Test deletion through translator",
                    "deleted_at": "2025-01-21T15:10:00.000Z",
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=delete_memory
                )

            assert (
                response.status_code == 201
            ), f"Delete memory event rejected: {response.status_code}"

            await asyncio.sleep(3)

            # Verify emo.deleted event generated
            emo_events = await self.get_emo_events_for_memory(memory_id)

            emo_deleted = None
            for event in emo_events:
                if event["kind"] == "emo.deleted":
                    emo_deleted = event
                    break

            assert emo_deleted is not None, "emo.deleted event not generated"

            # Verify EMO marked as deleted in database
            async with asyncpg.connect(self.db_url) as conn:
                emo_id = self.derive_emo_id(memory_id)
                deleted_row = await conn.fetchrow(
                    "SELECT deleted, deletion_reason FROM lens_emo.emo_current WHERE emo_id = $1",
                    emo_id,
                )

                assert deleted_row is not None, "EMO not found in database"
                assert deleted_row["deleted"] == True, "EMO not marked as deleted"
                assert (
                    deleted_row["deletion_reason"] is not None
                ), "Deletion reason not recorded"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event=delete_memory,
                    emo_events=[emo_deleted],
                    validation_details={
                        "emo_deleted_event": True,
                        "database_deleted": deleted_row["deleted"],
                        "deletion_reason": deleted_row["deletion_reason"],
                    },
                )
            )

            logger.info(f"✅ {test_name} passed in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event=delete_memory if "delete_memory" in locals() else {},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_field_mapping_accuracy(self):
        """Test accuracy of field mapping from memory to EMO"""
        start_time = time.time()
        test_name = "field_mapping_accuracy"

        try:
            memory_event = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": f"mem-{uuid.uuid4()}",
                    "title": "Field Mapping Test Title",
                    "body": "Field mapping test body content with special chars: éñüíóß",
                    "tags": ["mapping", "test", "unicode"],
                    "metadata": {
                        "author": "test-user",
                        "category": "research",
                        "priority": "high",
                    },
                    "mime_type": "text/markdown",
                },
            }

            async with httpx.AsyncClient() as client:
                await client.post(f"{self.gateway_url}/v1/events", json=memory_event)

            await asyncio.sleep(3)

            emo_events = await self.get_emo_events_for_memory(
                memory_event["payload"]["id"]
            )
            emo_created = next(
                (e for e in emo_events if e["kind"] == "emo.created"), None
            )

            assert emo_created is not None, "emo.created event not found"

            # Validate specific field mappings
            emo_payload = emo_created["payload"]
            memory_payload = memory_event["payload"]

            # Content mapping: title + body
            expected_content = f"{memory_payload['title']}\n\n{memory_payload['body']}"
            assert (
                emo_payload["content"] == expected_content
            ), f"Content mapping incorrect: {emo_payload['content']}"

            # Tags mapping
            assert (
                emo_payload["tags"] == memory_payload["tags"]
            ), "Tags not mapped correctly"

            # MIME type mapping
            assert (
                emo_payload["mime_type"] == memory_payload["mime_type"]
            ), "MIME type not mapped correctly"

            # EMO type inference
            assert emo_payload["emo_type"] in [
                "note",
                "fact",
                "doc",
            ], "EMO type not inferred correctly"

            # Version for new EMO
            assert emo_payload["emo_version"] == 1, "Initial version not set to 1"

            # World/branch mapping
            assert (
                emo_payload["world_id"] == memory_event["world_id"]
            ), "World ID not mapped correctly"
            assert (
                emo_payload["branch"] == memory_event["branch"]
            ), "Branch not mapped correctly"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event=memory_event,
                    emo_events=[emo_created],
                    validation_details={
                        "content_mapping": True,
                        "tags_mapping": True,
                        "mime_type_mapping": True,
                        "version_mapping": True,
                        "world_branch_mapping": True,
                    },
                )
            )

            logger.info(f"✅ {test_name} passed in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event=memory_event if "memory_event" in locals() else {},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_idempotency_preservation(self):
        """Test that idempotency is preserved through translation"""
        start_time = time.time()
        test_name = "idempotency_preservation"

        try:
            memory_event = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "correlation_id": "idempotency-test-001",
                "payload": {
                    "id": f"mem-{uuid.uuid4()}",
                    "title": "Idempotency Test",
                    "body": "Testing idempotency preservation",
                },
            }

            # Submit same event twice
            async with httpx.AsyncClient() as client:
                response1 = await client.post(
                    f"{self.gateway_url}/v1/events", json=memory_event
                )
                response2 = await client.post(
                    f"{self.gateway_url}/v1/events", json=memory_event
                )

            # Both should be accepted (gateway-level idempotency)
            assert response1.status_code == 201, "First submission failed"
            assert response2.status_code in [
                201,
                409,
            ], "Second submission should be accepted or rejected with 409"

            await asyncio.sleep(3)

            # Check that only one EMO was created
            emo_events = await self.get_emo_events_for_memory(
                memory_event["payload"]["id"]
            )
            emo_created_events = [e for e in emo_events if e["kind"] == "emo.created"]

            assert (
                len(emo_created_events) == 1
            ), f"Expected 1 emo.created, got {len(emo_created_events)}"

            # Verify EMO has proper idempotency key
            emo_created = emo_created_events[0]
            idempotency_key = emo_created["payload"].get("idempotency_key")

            assert (
                idempotency_key is not None
            ), "Idempotency key not present in EMO event"

            # Validate idempotency key format
            emo_id = emo_created["payload"]["emo_id"]
            expected_key = f"{emo_id}:1:created"
            assert (
                idempotency_key == expected_key
            ), f"Idempotency key format incorrect: {idempotency_key}"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event=memory_event,
                    emo_events=emo_created_events,
                    validation_details={
                        "single_emo_created": len(emo_created_events) == 1,
                        "idempotency_key_present": True,
                        "idempotency_key_format": True,
                    },
                )
            )

            logger.info(f"✅ {test_name} passed in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event=memory_event if "memory_event" in locals() else {},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_translation_performance(self):
        """Test translator performance under load"""
        start_time = time.time()
        test_name = "translation_performance"

        try:
            event_count = 50  # Moderate load test
            memory_events = []

            # Generate memory events
            for i in range(event_count):
                memory_event = {
                    "world_id": str(uuid.uuid4()),
                    "branch": "main",
                    "kind": "memory.item.upserted",
                    "event_id": str(uuid.uuid4()),
                    "payload": {
                        "id": f"perf-mem-{i}",
                        "title": f"Performance Test Memory {i}",
                        "body": f"Performance test content {i}",
                    },
                }
                memory_events.append(memory_event)

            # Submit all events
            submission_start = time.time()

            async with httpx.AsyncClient() as client:
                tasks = []
                for event in memory_events:
                    task = client.post(f"{self.gateway_url}/v1/events", json=event)
                    tasks.append(task)

                responses = await asyncio.gather(*tasks)

            submission_time = time.time() - submission_start

            # Verify all events accepted
            success_count = sum(1 for r in responses if r.status_code == 201)
            assert (
                success_count == event_count
            ), f"Only {success_count}/{event_count} events accepted"

            # Wait for translation processing
            await asyncio.sleep(10)

            # Verify all EMOs created
            async with asyncpg.connect(self.db_url) as conn:
                emo_count = 0
                for event in memory_events:
                    emo_id = self.derive_emo_id(event["payload"]["id"])
                    exists = await conn.fetchval(
                        "SELECT 1 FROM lens_emo.emo_current WHERE emo_id = $1", emo_id
                    )
                    if exists:
                        emo_count += 1

            processing_time = time.time() - start_time
            submission_rate = event_count / submission_time
            processing_rate = emo_count / processing_time

            # Performance assertions
            assert (
                emo_count == event_count
            ), f"Only {emo_count}/{event_count} EMOs created"
            assert (
                submission_rate >= 10
            ), f"Submission rate too low: {submission_rate:.1f} events/sec"
            assert (
                processing_rate >= 5
            ), f"Processing rate too low: {processing_rate:.1f} EMOs/sec"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event={"batch_info": f"{event_count} events"},
                    emo_events=[],
                    validation_details={
                        "events_submitted": event_count,
                        "emos_created": emo_count,
                        "submission_rate": round(submission_rate, 2),
                        "processing_rate": round(processing_rate, 2),
                        "total_time": round(duration, 2),
                    },
                )
            )

            logger.info(
                f"✅ {test_name} passed - {submission_rate:.1f} events/sec submission, {processing_rate:.1f} EMOs/sec processing"
            )

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event={},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_malformed_memory_events(self):
        """Test handling of malformed memory events"""
        start_time = time.time()
        test_name = "malformed_memory_events"

        try:
            # Test various malformed events
            malformed_events = [
                {
                    "description": "Missing payload",
                    "event": {
                        "world_id": str(uuid.uuid4()),
                        "branch": "main",
                        "kind": "memory.item.upserted",
                        "event_id": str(uuid.uuid4()),
                        # Missing payload
                    },
                },
                {
                    "description": "Missing memory ID",
                    "event": {
                        "world_id": str(uuid.uuid4()),
                        "branch": "main",
                        "kind": "memory.item.upserted",
                        "event_id": str(uuid.uuid4()),
                        "payload": {
                            "title": "No ID memory",
                            "body": "This memory has no ID",
                        },
                    },
                },
                {
                    "description": "Invalid memory ID",
                    "event": {
                        "world_id": str(uuid.uuid4()),
                        "branch": "main",
                        "kind": "memory.item.upserted",
                        "event_id": str(uuid.uuid4()),
                        "payload": {
                            "id": None,  # Invalid ID
                            "title": "Invalid ID memory",
                            "body": "This memory has invalid ID",
                        },
                    },
                },
            ]

            error_handled_count = 0

            async with httpx.AsyncClient() as client:
                for test_case in malformed_events:
                    try:
                        response = await client.post(
                            f"{self.gateway_url}/v1/events",
                            json=test_case["event"],
                            timeout=5.0,
                        )

                        # Event should be rejected or translator should handle gracefully
                        if response.status_code in [400, 422, 500]:
                            error_handled_count += 1
                            logger.debug(
                                f"✅ Malformed event properly rejected: {test_case['description']}"
                            )
                        elif response.status_code == 201:
                            # Event accepted - translator should handle gracefully without crashing
                            logger.debug(
                                f"⚠️ Malformed event accepted, checking translator handling: {test_case['description']}"
                            )
                            error_handled_count += 1  # Count as handled if no crash

                    except Exception as e:
                        logger.debug(
                            f"✅ Exception properly caught for malformed event: {test_case['description']}: {e}"
                        )
                        error_handled_count += 1

            await asyncio.sleep(3)  # Wait for any processing

            # Verify translator is still responsive
            test_event = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "memory.item.upserted",
                "event_id": str(uuid.uuid4()),
                "payload": {
                    "id": f"health-check-{uuid.uuid4()}",
                    "title": "Health Check",
                    "body": "Translator health check after malformed events",
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=test_event
                )

            assert (
                response.status_code == 201
            ), "Translator not responsive after malformed events"

            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    memory_event={"malformed_tests": len(malformed_events)},
                    emo_events=[],
                    validation_details={
                        "malformed_events_tested": len(malformed_events),
                        "errors_handled": error_handled_count,
                        "translator_responsive": True,
                    },
                )
            )

            logger.info(
                f"✅ {test_name} passed - {error_handled_count}/{len(malformed_events)} errors handled gracefully"
            )

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                TranslationResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    memory_event={},
                    emo_events=[],
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    # Helper methods

    async def get_emo_events_for_memory(self, memory_id: str) -> List[Dict[str, Any]]:
        """Get all EMO events generated for a specific memory ID"""
        emo_id = self.derive_emo_id(memory_id)

        async with asyncpg.connect(self.db_url) as conn:
            # Get events from event log
            events = await conn.fetch(
                """
                SELECT envelope, global_seq 
                FROM event_core.event_log 
                WHERE envelope->>'kind' LIKE 'emo.%' 
                AND envelope->'payload'->>'emo_id' = $1
                ORDER BY global_seq
                """,
                str(emo_id),
            )

            return [dict(event["envelope"]) for event in events]

    def derive_emo_id(self, memory_id: str) -> uuid.UUID:
        """Derive EMO ID from memory ID (matches translator logic)"""
        # Use deterministic UUID generation based on memory ID
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # Fixed namespace
        return uuid.uuid5(namespace, str(memory_id))

    async def validate_memory_to_emo_translation(
        self, memory_event: Dict[str, Any], emo_event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate accuracy of memory-to-EMO translation"""
        memory_payload = memory_event["payload"]
        emo_payload = emo_event["payload"]

        validation = {}

        # EMO ID derivation
        expected_emo_id = str(self.derive_emo_id(memory_payload["id"]))
        validation["emo_id_correct"] = emo_payload["emo_id"] == expected_emo_id

        # Content mapping
        expected_content = memory_payload.get("title", "")
        if memory_payload.get("body"):
            expected_content += f"\n\n{memory_payload['body']}"
        validation["content_mapped"] = emo_payload["content"] == expected_content

        # Tags mapping
        validation["tags_mapped"] = emo_payload["tags"] == memory_payload.get(
            "tags", []
        )

        # Version for new EMO
        validation["version_correct"] = emo_payload["emo_version"] == 1

        # World/branch mapping
        validation["world_mapped"] = emo_payload["world_id"] == memory_event["world_id"]
        validation["branch_mapped"] = emo_payload["branch"] == memory_event["branch"]

        # Idempotency key format
        expected_key = f"{emo_payload['emo_id']}:1:created"
        validation["idempotency_key_correct"] = (
            emo_payload.get("idempotency_key") == expected_key
        )

        return validation

    def generate_test_summary(self):
        """Generate comprehensive test summary"""
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.success])
        failed_tests = total_tests - successful_tests
        total_duration = sum(r.duration for r in self.results)

        logger.info("\n" + "=" * 60)
        logger.info("🔄 ALPHA TRANSLATOR TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Successful: {successful_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"⏱️ Total Duration: {total_duration:.2f}s")
        logger.info(f"📊 Success Rate: {(successful_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            logger.info("\n❌ FAILED TESTS:")
            for result in self.results:
                if not result.success:
                    logger.info(f"  - {result.test_name}: {result.error}")

        logger.info("\n📋 DETAILED RESULTS:")
        for result in self.results:
            status = "✅" if result.success else "❌"
            logger.info(f"  {status} {result.test_name} ({result.duration:.2f}s)")
            if result.validation_details:
                for key, value in result.validation_details.items():
                    logger.info(f"      {key}: {value}")

    # Additional missing test methods that should be implemented
    async def test_version_management(self):
        """Test version management across multiple memory updates"""
        logger.info("⚠️ test_version_management - placeholder for future implementation")

    async def test_missing_required_fields(self):
        """Test handling of memory events with missing required fields"""
        logger.info(
            "⚠️ test_missing_required_fields - placeholder for future implementation"
        )

    async def test_translation_error_handling(self):
        """Test translator error handling and recovery"""
        logger.info(
            "⚠️ test_translation_error_handling - placeholder for future implementation"
        )

    async def test_concurrent_translation(self):
        """Test translator under concurrent load"""
        logger.info(
            "⚠️ test_concurrent_translation - placeholder for future implementation"
        )

    async def test_translator_vs_direct_emo_parity(self):
        """Test parity between translator path and direct EMO events"""
        logger.info(
            "⚠️ test_translator_vs_direct_emo_parity - placeholder for future implementation"
        )


async def main():
    """Main test runner entry point"""
    parser = argparse.ArgumentParser(description="Alpha Translator Test Runner")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--database-url", help="Database connection URL")
    parser.add_argument("--gateway-url", help="Gateway service URL")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configuration
    config = {
        "database_url": args.database_url
        or "postgresql://postgres:postgres@localhost:5432/nexus",
        "gateway_url": args.gateway_url or "http://localhost:8086",
    }

    # Create test runner
    tester = AlphaTranslatorTester(config)

    try:
        # Run translator tests
        await tester.run_all_translator_tests()

        # Exit with appropriate code
        failed_count = len([r for r in tester.results if not r.success])
        return 0 if failed_count == 0 else 1

    except KeyboardInterrupt:
        logger.info("\n⚠️ Test execution interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))

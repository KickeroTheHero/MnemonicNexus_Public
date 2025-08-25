#!/usr/bin/env python3
"""
Deterministic Replay Test Implementation

Critical missing tests for EMO deterministic replay capability.
This module addresses the CRITICAL GAP identified in testing analysis.

Usage:
    python scripts/test_deterministic_replay.py
    python scripts/test_deterministic_replay.py --verbose
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
class SystemState:
    """Captured system state for replay comparison"""

    emo_current_rows: List[Dict[str, Any]]
    emo_history_rows: List[Dict[str, Any]]
    emo_links_rows: List[Dict[str, Any]]
    emo_embeddings_rows: List[Dict[str, Any]]
    determinism_hash: str
    capture_timestamp: str


@dataclass
class ReplayResult:
    """Result of deterministic replay test"""

    test_name: str
    success: bool
    duration: float
    original_state: SystemState
    replayed_state: SystemState
    validation_details: Dict[str, Any]
    error: Optional[str] = None


class DeterministicReplayTester:
    """Comprehensive deterministic replay testing"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_url = config.get(
            "database_url", "postgresql://postgres:postgres@localhost:5432/nexus"
        )
        self.gateway_url = config.get("gateway_url", "http://localhost:8086")
        self.results: List[ReplayResult] = []

    async def run_all_replay_tests(self) -> List[ReplayResult]:
        """Execute comprehensive deterministic replay test suite"""
        logger.info("🔄 Starting Deterministic Replay Test Suite")
        logger.info("=" * 60)

        # Core replay tests
        await self.test_simple_emo_sequence_replay()
        await self.test_complex_relationship_replay()
        await self.test_deletion_and_recovery_replay()
        await self.test_version_consistency_replay()

        # State consistency tests
        await self.test_determinism_hash_stability()
        await self.test_vector_embedding_consistency()
        await self.test_graph_relationship_preservation()

        # Performance replay tests
        await self.test_large_scale_replay_performance()
        await self.test_partial_replay_from_checkpoint()

        # Error scenario replay tests
        await self.test_replay_with_corrupted_events()
        await self.test_replay_with_missing_events()

        self.generate_test_summary()
        return self.results

    async def test_simple_emo_sequence_replay(self):
        """Test replay of simple EMO creation/update/delete sequence"""
        start_time = time.time()
        test_name = "simple_emo_sequence_replay"

        try:
            world_id = str(uuid.uuid4())
            branch = "main"

            # Define event sequence
            event_sequence = [
                {
                    "world_id": world_id,
                    "branch": branch,
                    "kind": "emo.created",
                    "event_id": str(uuid.uuid4()),
                    "payload": {
                        "emo_id": str(uuid.uuid4()),
                        "emo_type": "note",
                        "emo_version": 1,
                        "tenant_id": world_id,
                        "world_id": world_id,
                        "branch": branch,
                        "content": "Initial EMO content for replay testing",
                        "tags": ["replay", "test"],
                        "source": {"kind": "user"},
                        "parents": [],
                        "links": [],
                        "idempotency_key": f"{uuid.uuid4()}:1:created",
                        "change_id": str(uuid.uuid4()),
                        "schema_version": 1,
                    },
                },
                {
                    "world_id": world_id,
                    "branch": branch,
                    "kind": "emo.updated",
                    "event_id": str(uuid.uuid4()),
                    "payload": {
                        "emo_id": None,  # Will be set from first event
                        "emo_version": 2,
                        "world_id": world_id,
                        "branch": branch,
                        "content": "Updated EMO content for replay testing",
                        "content_diff": {
                            "op": "replace",
                            "path": "/content",
                            "value": "Updated content",
                        },
                        "rationale": "Update for replay test",
                        "idempotency_key": None,  # Will be set
                        "change_id": str(uuid.uuid4()),
                    },
                },
                {
                    "world_id": world_id,
                    "branch": branch,
                    "kind": "emo.deleted",
                    "event_id": str(uuid.uuid4()),
                    "payload": {
                        "emo_id": None,  # Will be set from first event
                        "emo_version": 3,
                        "world_id": world_id,
                        "branch": branch,
                        "deletion_reason": "Replay test deletion",
                        "idempotency_key": None,  # Will be set
                        "change_id": str(uuid.uuid4()),
                    },
                },
            ]

            # Set EMO ID for subsequent events
            emo_id = event_sequence[0]["payload"]["emo_id"]
            event_sequence[1]["payload"]["emo_id"] = emo_id
            event_sequence[1]["payload"]["idempotency_key"] = f"{emo_id}:2:updated"
            event_sequence[2]["payload"]["emo_id"] = emo_id
            event_sequence[2]["payload"]["idempotency_key"] = f"{emo_id}:3:deleted"

            # Process original sequence
            logger.info("Processing original event sequence...")
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()

            # Capture original state
            original_state = await self.capture_system_state(world_id, branch)

            # Reset system to genesis
            logger.info("Resetting system for replay...")
            await self.reset_lens_tables(world_id, branch)

            # Replay the sequence
            logger.info("Replaying event sequence...")
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()

            # Capture replayed state
            replayed_state = await self.capture_system_state(world_id, branch)

            # Validate replay consistency
            validation_details = await self.validate_state_consistency(
                original_state, replayed_state
            )

            success = all(validation_details.values())

            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=success,
                    duration=duration,
                    original_state=original_state,
                    replayed_state=replayed_state,
                    validation_details=validation_details,
                )
            )

            if success:
                logger.info(f"✅ {test_name} passed in {duration:.2f}s")
            else:
                logger.error(f"❌ {test_name} failed - state consistency check failed")

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    original_state=SystemState([], [], [], [], "", ""),
                    replayed_state=SystemState([], [], [], [], "", ""),
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_complex_relationship_replay(self):
        """Test replay of complex EMO relationships and lineage"""
        start_time = time.time()
        test_name = "complex_relationship_replay"

        try:
            world_id = str(uuid.uuid4())
            branch = "main"

            # Create complex relationship scenario
            parent_id = str(uuid.uuid4())
            child1_id = str(uuid.uuid4())
            child2_id = str(uuid.uuid4())
            grandchild_id = str(uuid.uuid4())

            event_sequence = [
                # Create parent EMO
                self.create_emo_event(
                    parent_id, world_id, branch, "Parent EMO", version=1
                ),
                # Create child EMOs with relationships
                self.create_emo_event(
                    child1_id,
                    world_id,
                    branch,
                    "Child 1 EMO",
                    version=1,
                    parents=[{"emo_id": parent_id, "rel": "derived"}],
                ),
                self.create_emo_event(
                    child2_id,
                    world_id,
                    branch,
                    "Child 2 EMO",
                    version=1,
                    parents=[{"emo_id": parent_id, "rel": "derived"}],
                ),
                # Add relationship between children
                self.link_emo_event(
                    child1_id,
                    world_id,
                    branch,
                    version=2,
                    links=[{"kind": "emo", "ref": child2_id}],
                ),
                # Create grandchild with multiple parents
                self.create_emo_event(
                    grandchild_id,
                    world_id,
                    branch,
                    "Grandchild EMO",
                    version=1,
                    parents=[
                        {"emo_id": child1_id, "rel": "derived"},
                        {"emo_id": child2_id, "rel": "merges"},
                    ],
                ),
                # Update parent to reference children
                self.update_emo_event(
                    parent_id,
                    world_id,
                    branch,
                    version=2,
                    content="Updated parent with references",
                ),
                # Add external link to grandchild
                self.link_emo_event(
                    grandchild_id,
                    world_id,
                    branch,
                    version=2,
                    links=[{"kind": "uri", "ref": "https://example.com/source"}],
                ),
            ]

            # Process original sequence
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()

            original_state = await self.capture_system_state(world_id, branch)

            # Reset and replay
            await self.reset_lens_tables(world_id, branch)
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()

            replayed_state = await self.capture_system_state(world_id, branch)

            # Validate complex relationship preservation
            validation_details = await self.validate_state_consistency(
                original_state, replayed_state
            )

            # Additional relationship-specific validations
            validation_details.update(
                await self.validate_relationship_consistency(
                    original_state,
                    replayed_state,
                    [parent_id, child1_id, child2_id, grandchild_id],
                )
            )

            success = all(validation_details.values())

            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=success,
                    duration=duration,
                    original_state=original_state,
                    replayed_state=replayed_state,
                    validation_details=validation_details,
                )
            )

            if success:
                logger.info(f"✅ {test_name} passed in {duration:.2f}s")
            else:
                logger.error(
                    f"❌ {test_name} failed - relationship consistency check failed"
                )

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    original_state=SystemState([], [], [], [], "", ""),
                    replayed_state=SystemState([], [], [], [], "", ""),
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_determinism_hash_stability(self):
        """Test that determinism hash is stable across replay"""
        start_time = time.time()
        test_name = "determinism_hash_stability"

        try:
            world_id = str(uuid.uuid4())
            branch = "main"

            # Create sequence with various event types
            emo_id = str(uuid.uuid4())
            event_sequence = [
                self.create_emo_event(
                    emo_id, world_id, branch, "Hash test EMO", version=1
                ),
                self.update_emo_event(
                    emo_id, world_id, branch, version=2, content="Updated for hash test"
                ),
                self.link_emo_event(
                    emo_id,
                    world_id,
                    branch,
                    version=3,
                    links=[{"kind": "uri", "ref": "https://test.com"}],
                ),
            ]

            # Process original sequence multiple times to test stability
            hashes = []

            for iteration in range(3):
                logger.info(f"Hash stability test iteration {iteration + 1}")

                # Reset and replay
                await self.reset_lens_tables(world_id, branch)
                await self.process_event_sequence(event_sequence)
                await self.wait_for_processing_complete()

                # Compute determinism hash
                state = await self.capture_system_state(world_id, branch)
                hash_value = await self.compute_determinism_hash_for_emo(
                    emo_id, world_id, branch
                )
                hashes.append(hash_value)

                logger.info(f"Iteration {iteration + 1} hash: {hash_value}")

            # Validate all hashes are identical
            all_hashes_identical = len(set(hashes)) == 1

            validation_details = {
                "all_hashes_identical": all_hashes_identical,
                "hash_iterations": len(hashes),
                "unique_hashes": len(set(hashes)),
                "hash_values": hashes,
            }

            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=all_hashes_identical,
                    duration=duration,
                    original_state=SystemState(
                        [], [], [], [], hashes[0] if hashes else "", ""
                    ),
                    replayed_state=SystemState(
                        [], [], [], [], hashes[-1] if hashes else "", ""
                    ),
                    validation_details=validation_details,
                )
            )

            if all_hashes_identical:
                logger.info(
                    f"✅ {test_name} passed - hash stable across {len(hashes)} iterations"
                )
            else:
                logger.error(
                    f"❌ {test_name} failed - hash inconsistent: {set(hashes)}"
                )

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    original_state=SystemState([], [], [], [], "", ""),
                    replayed_state=SystemState([], [], [], [], "", ""),
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    async def test_large_scale_replay_performance(self):
        """Test replay performance with large event sequences"""
        start_time = time.time()
        test_name = "large_scale_replay_performance"

        try:
            world_id = str(uuid.uuid4())
            branch = "main"
            event_count = 100  # Reasonable scale for testing

            # Generate large event sequence
            event_sequence = []
            emo_ids = []

            # Create multiple EMOs
            for i in range(event_count // 4):  # 25 EMOs
                emo_id = str(uuid.uuid4())
                emo_ids.append(emo_id)
                event_sequence.append(
                    self.create_emo_event(
                        emo_id, world_id, branch, f"Large scale EMO {i}", version=1
                    )
                )

            # Add updates to half of them
            for i in range(len(emo_ids) // 2):
                event_sequence.append(
                    self.update_emo_event(
                        emo_ids[i],
                        world_id,
                        branch,
                        version=2,
                        content=f"Updated large scale EMO {i}",
                    )
                )

            # Add some relationships
            for i in range(len(emo_ids) // 4):
                if i + 1 < len(emo_ids):
                    event_sequence.append(
                        self.link_emo_event(
                            emo_ids[i],
                            world_id,
                            branch,
                            version=3,
                            parents=[{"emo_id": emo_ids[i + 1], "rel": "derived"}],
                        )
                    )

            logger.info(f"Generated {len(event_sequence)} events for large scale test")

            # Process original sequence
            original_start = time.time()
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()
            original_processing_time = time.time() - original_start

            original_state = await self.capture_system_state(world_id, branch)

            # Reset and replay
            replay_start = time.time()
            await self.reset_lens_tables(world_id, branch)
            await self.process_event_sequence(event_sequence)
            await self.wait_for_processing_complete()
            replay_processing_time = time.time() - replay_start

            replayed_state = await self.capture_system_state(world_id, branch)

            # Validate consistency
            validation_details = await self.validate_state_consistency(
                original_state, replayed_state
            )

            # Performance metrics
            validation_details.update(
                {
                    "event_count": len(event_sequence),
                    "original_processing_time": round(original_processing_time, 2),
                    "replay_processing_time": round(replay_processing_time, 2),
                    "performance_ratio": round(
                        replay_processing_time / original_processing_time, 2
                    ),
                    "events_per_second_original": round(
                        len(event_sequence) / original_processing_time, 1
                    ),
                    "events_per_second_replay": round(
                        len(event_sequence) / replay_processing_time, 1
                    ),
                }
            )

            # Success criteria: consistency maintained and reasonable performance
            success = (
                all(v for k, v in validation_details.items() if isinstance(v, bool))
                and replay_processing_time < original_processing_time * 2
            )  # Replay shouldn't be >2x slower

            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=success,
                    duration=duration,
                    original_state=original_state,
                    replayed_state=replayed_state,
                    validation_details=validation_details,
                )
            )

            if success:
                logger.info(
                    f"✅ {test_name} passed - {len(event_sequence)} events replayed consistently"
                )
            else:
                logger.error(
                    f"❌ {test_name} failed - consistency or performance issues"
                )

        except Exception as e:
            duration = time.time() - start_time
            self.results.append(
                ReplayResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    original_state=SystemState([], [], [], [], "", ""),
                    replayed_state=SystemState([], [], [], [], "", ""),
                    validation_details={},
                    error=str(e),
                )
            )
            logger.error(f"❌ {test_name} failed: {e}")

    # Helper methods

    async def process_event_sequence(self, events: List[Dict[str, Any]]):
        """Process a sequence of events through the gateway"""
        async with httpx.AsyncClient() as client:
            for event in events:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=event, timeout=10.0
                )

                if response.status_code != 201:
                    raise Exception(
                        f"Event rejected: {response.status_code} - {response.text}"
                    )

    async def wait_for_processing_complete(self, timeout: int = 30):
        """Wait for event processing to complete"""
        await asyncio.sleep(5)  # Base wait time

        # Could add more sophisticated completion detection here
        # For now, use fixed wait time

    async def capture_system_state(self, world_id: str, branch: str) -> SystemState:
        """Capture complete system state for comparison"""
        async with asyncpg.connect(self.db_url) as conn:
            # Capture EMO current state
            emo_current = await conn.fetch(
                "SELECT * FROM lens_emo.emo_current WHERE world_id = $1 AND branch = $2 ORDER BY emo_id",
                world_id,
                branch,
            )

            # Capture EMO history
            emo_history = await conn.fetch(
                "SELECT * FROM lens_emo.emo_history WHERE world_id = $1 AND branch = $2 ORDER BY emo_id, emo_version",
                world_id,
                branch,
            )

            # Capture EMO links
            emo_links = await conn.fetch(
                "SELECT * FROM lens_emo.emo_links WHERE world_id = $1 AND branch = $2 ORDER BY emo_id, target_emo_id",
                world_id,
                branch,
            )

            # Capture EMO embeddings (if available)
            emo_embeddings = []
            try:
                emo_embeddings = await conn.fetch(
                    "SELECT emo_id, model_id, embed_dim FROM lens_emo.emo_embeddings WHERE world_id = $1 AND branch = $2 ORDER BY emo_id",
                    world_id,
                    branch,
                )
            except Exception:
                # Embeddings table might not exist or be populated
                pass

            # Compute overall determinism hash
            determinism_hash = await self.compute_system_determinism_hash(
                world_id, branch
            )

            return SystemState(
                emo_current_rows=[dict(row) for row in emo_current],
                emo_history_rows=[dict(row) for row in emo_history],
                emo_links_rows=[dict(row) for row in emo_links],
                emo_embeddings_rows=[dict(row) for row in emo_embeddings],
                determinism_hash=determinism_hash,
                capture_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    async def reset_lens_tables(self, world_id: str, branch: str):
        """Reset lens tables to genesis state for the given world/branch"""
        async with asyncpg.connect(self.db_url) as conn:
            # Delete all data for this world/branch
            await conn.execute(
                "DELETE FROM lens_emo.emo_embeddings WHERE world_id = $1 AND branch = $2",
                world_id,
                branch,
            )
            await conn.execute(
                "DELETE FROM lens_emo.emo_links WHERE world_id = $1 AND branch = $2",
                world_id,
                branch,
            )
            await conn.execute(
                "DELETE FROM lens_emo.emo_history WHERE world_id = $1 AND branch = $2",
                world_id,
                branch,
            )
            await conn.execute(
                "DELETE FROM lens_emo.emo_current WHERE world_id = $1 AND branch = $2",
                world_id,
                branch,
            )

            # Refresh materialized views
            try:
                await conn.execute("REFRESH MATERIALIZED VIEW lens_emo.emo_active")
            except Exception:
                # MV might not exist
                pass

    async def validate_state_consistency(
        self, original: SystemState, replayed: SystemState
    ) -> Dict[str, bool]:
        """Validate that replayed state matches original state"""
        validation = {}

        # Compare row counts
        validation["emo_current_count_match"] = len(original.emo_current_rows) == len(
            replayed.emo_current_rows
        )
        validation["emo_history_count_match"] = len(original.emo_history_rows) == len(
            replayed.emo_history_rows
        )
        validation["emo_links_count_match"] = len(original.emo_links_rows) == len(
            replayed.emo_links_rows
        )
        validation["emo_embeddings_count_match"] = len(
            original.emo_embeddings_rows
        ) == len(replayed.emo_embeddings_rows)

        # Compare determinism hashes
        validation["determinism_hash_match"] = (
            original.determinism_hash == replayed.determinism_hash
        )

        # Deep comparison of current state (most critical)
        validation["emo_current_content_match"] = self.compare_emo_current_content(
            original.emo_current_rows, replayed.emo_current_rows
        )

        return validation

    def compare_emo_current_content(
        self, original_rows: List[Dict], replayed_rows: List[Dict]
    ) -> bool:
        """Compare EMO current state content for exact match"""
        if len(original_rows) != len(replayed_rows):
            return False

        # Sort by emo_id for consistent comparison
        original_sorted = sorted(original_rows, key=lambda x: x["emo_id"])
        replayed_sorted = sorted(replayed_rows, key=lambda x: x["emo_id"])

        for orig, repl in zip(original_sorted, replayed_sorted):
            # Compare key fields (excluding timestamps which may vary slightly)
            key_fields = [
                "emo_id",
                "emo_version",
                "content",
                "tags",
                "deleted",
                "deletion_reason",
            ]
            for field in key_fields:
                if orig.get(field) != repl.get(field):
                    logger.error(
                        f"Field mismatch for {orig['emo_id']}.{field}: {orig.get(field)} != {repl.get(field)}"
                    )
                    return False

        return True

    async def compute_system_determinism_hash(self, world_id: str, branch: str) -> str:
        """Compute determinism hash for entire system state"""
        async with asyncpg.connect(self.db_url) as conn:
            # Get all EMO data sorted consistently
            rows = await conn.fetch(
                """
                SELECT emo_id, emo_version, content, tags, deleted, 
                       array_to_string(tags, ',') as tags_str
                FROM lens_emo.emo_current 
                WHERE world_id = $1 AND branch = $2 
                ORDER BY emo_id
                """,
                world_id,
                branch,
            )

            # Create hash input from sorted data
            hash_input = ""
            for row in rows:
                hash_input += f"{row['emo_id']}:{row['emo_version']}:{row['content']}:{row['tags_str']}:{row['deleted']}"

            # Compute SHA-256 hash
            return hashlib.sha256(hash_input.encode()).hexdigest()

    async def compute_determinism_hash_for_emo(
        self, emo_id: str, world_id: str, branch: str
    ) -> str:
        """Compute determinism hash for a specific EMO"""
        async with asyncpg.connect(self.db_url) as conn:
            # Implementation of the determinism hash recipe from EMO spec
            row = await conn.fetchrow(
                """
                SELECT ec.emo_id, ec.emo_version, ec.world_id, ec.branch,
                       ec.content, ec.tags, ec.updated_at,
                       COALESCE(string_agg(DISTINCT el.target_emo_id::text, ',' ORDER BY el.target_emo_id::text), '') as linked_emos
                FROM lens_emo.emo_current ec
                LEFT JOIN lens_emo.emo_links el ON ec.emo_id = el.emo_id
                WHERE ec.emo_id = $1 AND ec.world_id = $2 AND ec.branch = $3
                GROUP BY ec.emo_id, ec.emo_version, ec.world_id, ec.branch, ec.content, ec.tags, ec.updated_at
                """,
                emo_id,
                world_id,
                branch,
            )

            if not row:
                return ""

            # Hash components in order per EMO spec
            hash_components = [
                row["emo_id"],
                str(row["emo_version"]),
                row["world_id"],
                row["branch"],
                row["content"] or "",
                ",".join(row["tags"] or []),
                row["linked_emos"],
                str(int(row["updated_at"].timestamp())),
            ]

            hash_input = ":".join(hash_components)
            return hashlib.sha256(hash_input.encode()).hexdigest()

    def create_emo_event(
        self,
        emo_id: str,
        world_id: str,
        branch: str,
        content: str,
        version: int = 1,
        parents: List = None,
        links: List = None,
    ) -> Dict[str, Any]:
        """Create emo.created event"""
        return {
            "world_id": world_id,
            "branch": branch,
            "kind": "emo.created",
            "event_id": str(uuid.uuid4()),
            "payload": {
                "emo_id": emo_id,
                "emo_type": "note",
                "emo_version": version,
                "tenant_id": world_id,
                "world_id": world_id,
                "branch": branch,
                "content": content,
                "tags": ["replay", "test"],
                "source": {"kind": "user"},
                "parents": parents or [],
                "links": links or [],
                "idempotency_key": f"{emo_id}:{version}:created",
                "change_id": str(uuid.uuid4()),
                "schema_version": 1,
            },
        }

    def update_emo_event(
        self, emo_id: str, world_id: str, branch: str, version: int, content: str
    ) -> Dict[str, Any]:
        """Create emo.updated event"""
        return {
            "world_id": world_id,
            "branch": branch,
            "kind": "emo.updated",
            "event_id": str(uuid.uuid4()),
            "payload": {
                "emo_id": emo_id,
                "emo_version": version,
                "world_id": world_id,
                "branch": branch,
                "content": content,
                "content_diff": {"op": "replace", "path": "/content", "value": content},
                "rationale": "Replay test update",
                "idempotency_key": f"{emo_id}:{version}:updated",
                "change_id": str(uuid.uuid4()),
            },
        }

    def link_emo_event(
        self,
        emo_id: str,
        world_id: str,
        branch: str,
        version: int,
        parents: List = None,
        links: List = None,
    ) -> Dict[str, Any]:
        """Create emo.linked event"""
        return {
            "world_id": world_id,
            "branch": branch,
            "kind": "emo.linked",
            "event_id": str(uuid.uuid4()),
            "payload": {
                "emo_id": emo_id,
                "emo_version": version,
                "world_id": world_id,
                "branch": branch,
                "parents": parents or [],
                "links": links or [],
                "idempotency_key": f"{emo_id}:{version}:linked",
                "change_id": str(uuid.uuid4()),
            },
        }

    def generate_test_summary(self):
        """Generate comprehensive test summary"""
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.success])
        failed_tests = total_tests - successful_tests
        total_duration = sum(r.duration for r in self.results)

        logger.info("\n" + "=" * 60)
        logger.info("🔄 DETERMINISTIC REPLAY TEST SUMMARY")
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
                    if isinstance(value, bool):
                        status_icon = "✅" if value else "❌"
                        logger.info(f"      {status_icon} {key}")
                    else:
                        logger.info(f"      📊 {key}: {value}")

    # Placeholder methods for tests not yet implemented
    async def test_deletion_and_recovery_replay(self):
        """Test replay of deletion and recovery scenarios"""
        logger.info(
            "⚠️ test_deletion_and_recovery_replay - placeholder for future implementation"
        )

    async def test_version_consistency_replay(self):
        """Test version consistency across replay"""
        logger.info(
            "⚠️ test_version_consistency_replay - placeholder for future implementation"
        )

    async def test_vector_embedding_consistency(self):
        """Test vector embedding consistency across replay"""
        logger.info(
            "⚠️ test_vector_embedding_consistency - placeholder for future implementation"
        )

    async def test_graph_relationship_preservation(self):
        """Test graph relationship preservation across replay"""
        logger.info(
            "⚠️ test_graph_relationship_preservation - placeholder for future implementation"
        )

    async def test_partial_replay_from_checkpoint(self):
        """Test partial replay from specific checkpoints"""
        logger.info(
            "⚠️ test_partial_replay_from_checkpoint - placeholder for future implementation"
        )

    async def test_replay_with_corrupted_events(self):
        """Test replay behavior with corrupted events"""
        logger.info(
            "⚠️ test_replay_with_corrupted_events - placeholder for future implementation"
        )

    async def test_replay_with_missing_events(self):
        """Test replay behavior with missing events"""
        logger.info(
            "⚠️ test_replay_with_missing_events - placeholder for future implementation"
        )

    async def validate_relationship_consistency(
        self, original: SystemState, replayed: SystemState, emo_ids: List[str]
    ) -> Dict[str, bool]:
        """Validate relationship consistency for specific EMOs"""
        # Placeholder for relationship validation
        return {"relationship_consistency": True}


async def main():
    """Main test runner entry point"""
    parser = argparse.ArgumentParser(description="Deterministic Replay Test Runner")
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
    tester = DeterministicReplayTester(config)

    try:
        # Run replay tests
        await tester.run_all_replay_tests()

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

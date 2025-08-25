"""
Graph Adapter for MnemonicNexus
AGE-based graph operations with world/branch isolation
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import asyncpg


class GraphAdapter(ABC):
    """Abstract interface for graph operations"""

    @abstractmethod
    async def apply_event(
        self, world_id: str, branch: str, envelope: Dict[str, Any]
    ) -> None:
        """Apply event to graph store"""
        pass

    @abstractmethod
    async def ensure_graph_exists(self, world_id: str, branch: str) -> None:
        """Ensure graph exists for world/branch"""
        pass

    @abstractmethod
    async def get_lineage(
        self, world_id: str, branch: str, entity_id: str
    ) -> Dict[str, Any]:
        """Get entity lineage"""
        pass


class AGEAdapter(GraphAdapter):
    """Apache AGE implementation of graph adapter"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def apply_event(
        self, world_id: str, branch: str, envelope: Dict[str, Any]
    ) -> None:
        """Apply event to AGE graph"""
        try:
            async with self.db_pool.acquire() as conn:
                # Ensure graph exists
                await self.ensure_graph_exists(world_id, branch)

                # Extract event data
                event_data = envelope.get("event", {})
                entity_id = event_data.get("entity_id")
                kind = envelope.get("kind", "")

                if kind.startswith("note."):
                    await self._handle_note_event(conn, world_id, branch, envelope)
                elif kind.startswith("link."):
                    await self._handle_link_event(conn, world_id, branch, envelope)

        except Exception as e:
            # Log error but don't fail - AGE is optional
            print(f"AGE operation failed: {e}")

    async def ensure_graph_exists(self, world_id: str, branch: str) -> None:
        """Ensure AGE graph exists for world/branch"""
        try:
            async with self.db_pool.acquire() as conn:
                # Use the graph creation function from migrations
                await conn.execute(
                    "SELECT lens_emo.create_emo_graph($1, $2)",
                    world_id,
                    branch,
                )
        except Exception as e:
            print(f"Graph creation failed: {e}")

    async def get_lineage(
        self, world_id: str, branch: str, entity_id: str
    ) -> Dict[str, Any]:
        """Get entity lineage from AGE graph"""
        try:
            async with self.db_pool.acquire() as conn:
                # Use AGE functions from migrations
                result = await conn.fetchrow(
                    "SELECT lens_emo.get_emo_lineage($1, $2, $3)",
                    world_id,
                    branch,
                    entity_id,
                )
                return json.loads(result[0]) if result and result[0] else {}
        except Exception as e:
            print(f"Lineage query failed: {e}")
            return {}

    async def _handle_note_event(
        self, conn: asyncpg.Connection, world_id: str, branch: str, envelope: Dict[str, Any]
    ) -> None:
        """Handle note-related events"""
        event_data = envelope.get("event", {})
        entity_id = event_data.get("entity_id")
        kind = envelope.get("kind", "")

        if kind == "note.created":
            # Add node to graph
            await conn.execute(
                """
                SELECT lens_emo.add_emo_node($1, $2, $3, $4)
                """,
                world_id,
                branch,
                entity_id,
                json.dumps({"type": "note", "title": event_data.get("title", "")}),
            )

        elif kind == "note.updated":
            # Update node properties (remove and re-add)
            await conn.execute(
                """
                SELECT lens_emo.add_emo_node($1, $2, $3, $4)
                """,
                world_id,
                branch,
                entity_id,
                json.dumps({"type": "note", "title": event_data.get("title", "")}),
            )

        elif kind == "note.deleted":
            # Remove node from graph (implementation depends on AGE functions)
            pass

    async def _handle_link_event(
        self, conn: asyncpg.Connection, world_id: str, branch: str, envelope: Dict[str, Any]
    ) -> None:
        """Handle link-related events"""
        event_data = envelope.get("event", {})
        kind = envelope.get("kind", "")

        if kind == "link.created":
            source_id = event_data.get("source_id")
            target_id = event_data.get("target_id")
            relationship = event_data.get("relationship", "related_to")

            if source_id and target_id:
                await conn.execute(
                    """
                    SELECT lens_emo.add_emo_relationship($1, $2, $3, $4, $5)
                    """,
                    world_id,
                    branch,
                    source_id,
                    target_id,
                    relationship,
                )

        elif kind == "link.deleted":
            # Remove relationship (implementation depends on AGE functions)
            pass

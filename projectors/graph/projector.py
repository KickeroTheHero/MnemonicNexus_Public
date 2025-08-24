"""
Graph Projector for MnemonicNexus V2
AGE-based graph projection with world/branch isolation
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Any, Dict, Optional

import asyncpg
from sdk.projector import ProjectorSDK

from services.common.graph_adapter import AGEAdapter, GraphAdapter


class GraphProjector(ProjectorSDK):
    """AGE-based graph projector for V2 events"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.graph_adapter: Optional[GraphAdapter] = None

    @property
    def name(self) -> str:
        return "graph-projector-v2"

    @property
    def lens(self) -> str:
        return "graph"

    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to AGE graph with world/branch isolation"""
        try:
            world_id = envelope.get("world_id")
            branch = envelope.get("branch", "main")
            kind = envelope.get("kind")
            payload = envelope.get("payload", {})

            if not world_id or not kind:
                self.logger.warning("Invalid event envelope: missing world_id or kind")
                return

            # Ensure graph adapter is initialized
            if not self.graph_adapter:
                await self._initialize_graph_adapter()

            # Route event to appropriate handler
            if kind.startswith("note."):
                await self._handle_note_event(world_id, branch, kind, payload)
            elif kind.startswith("tag."):
                await self._handle_tag_event(world_id, branch, kind, payload)
            elif kind.startswith("link."):
                await self._handle_link_event(world_id, branch, kind, payload)
            elif kind.startswith("mention."):
                await self._handle_mention_event(world_id, branch, kind, payload)
            elif kind.startswith("emo."):
                await self._handle_emo_event(world_id, branch, kind, payload)
            else:
                self.logger.debug(f"Unhandled event kind: {kind}")

        except Exception as e:
            self.logger.error(
                f"Error processing event {envelope.get('kind')} for world {envelope.get('world_id')}: {e}"
            )
            raise

    async def _initialize_graph_adapter(self):
        """Initialize the graph adapter with database connection"""
        if not self.db_pool:
            raise RuntimeError("Database pool not initialized")

        self.graph_adapter = AGEAdapter(self.db_pool)
        self.logger.info("Graph adapter initialized with AGE backend")

    async def _handle_note_event(
        self, world_id: str, branch: str, kind: str, payload: Dict[str, Any]
    ):
        """Handle note lifecycle events"""
        # Use the fixed AGEAdapter instead of direct calls
        if kind == "note.created":
            note_id = payload.get("id")
            title = payload.get("title", "")
            
            # Create envelope for graph adapter
            envelope = {
                "kind": kind,
                "world_id": world_id,
                "branch": branch,
                "payload": {
                    "id": note_id,
                    "title": title
                }
            }
            
            await self.graph_adapter.apply_event(world_id, branch, envelope)

        elif kind == "note.updated":
            note_id = payload.get("id")
            title = payload.get("title", "")
            
            # Create envelope for graph adapter
            envelope = {
                "kind": kind,
                "world_id": world_id,
                "branch": branch,
                "payload": {
                    "id": note_id,
                    "title": title
                }
            }
            
            await self.graph_adapter.apply_event(world_id, branch, envelope)

        elif kind == "note.deleted":
            note_id = payload.get("id")
            
            # Create envelope for graph adapter
            envelope = {
                "kind": kind,
                "world_id": world_id,
                "branch": branch,
                "payload": {
                    "id": note_id
                }
            }
            
            await self.graph_adapter.apply_event(world_id, branch, envelope)

    async def _handle_tag_event(
        self, world_id: str, branch: str, kind: str, payload: Dict[str, Any]
    ):
        """Handle tag events"""
        async with self.db_pool.acquire() as conn:
            graph_name = await conn.fetchval(
                "SELECT lens_graph.ensure_graph_exists($1, $2)", world_id, branch
            )
            
            if kind == "tag.added":
                tag = payload.get("tag")
                note_id = payload.get("id")
                applied_at = payload.get("applied_at", "now()")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MERGE (t:Tag {{tag: '{tag}', world_id: '{world_id}', branch: '{branch}'}})
                        ON CREATE SET t.entity_type = 'tag'
                        WITH t
                        MATCH (n:Note {{id: '{note_id}', world_id: '{world_id}', branch: '{branch}'}})
                        CREATE (n)-[r:TAGGED {{
                            applied_at: '{applied_at}',
                            world_id: '{world_id}',
                            branch: '{branch}'
                        }}]->(t)
                        RETURN r
                    $$) AS (result agtype)
                    """
                )

            elif kind == "tag.removed":
                tag = payload.get("tag")
                note_id = payload.get("id")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (
                            n:Note {{id: '{note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        )-[r:TAGGED {{world_id: '{world_id}', branch: '{branch}'}}]->(
                            t:Tag {{tag: '{tag}', world_id: '{world_id}', branch: '{branch}'}}
                        )
                        DELETE r
                    $$) AS (result agtype)
                    """
                )

    async def _handle_link_event(
        self, world_id: str, branch: str, kind: str, payload: Dict[str, Any]
    ):
        """Handle note linking events"""
        async with self.db_pool.acquire() as conn:
            graph_name = await conn.fetchval(
                "SELECT lens_graph.ensure_graph_exists($1, $2)", world_id, branch
            )
            
            if kind == "link.added":
                src_note_id = payload.get("src")
                dst_note_id = payload.get("dst")
                link_type = payload.get("link_type", "reference")
                created_at = payload.get("created_at", "now()")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (
                            src:Note {{id: '{src_note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        ), (
                            dst:Note {{id: '{dst_note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        )
                        CREATE (src)-[r:LINKS_TO {{
                            link_type: '{link_type}',
                            created_at: '{created_at}',
                            world_id: '{world_id}',
                            branch: '{branch}'
                        }}]->(dst)
                        RETURN r
                    $$) AS (result agtype)
                    """
                )

            elif kind == "link.removed":
                src_note_id = payload.get("src")
                dst_note_id = payload.get("dst")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (
                            src:Note {{id: '{src_note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        )-[r:LINKS_TO {{world_id: '{world_id}', branch: '{branch}'}}]->(
                            dst:Note {{id: '{dst_note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        )
                        DELETE r
                    $$) AS (result agtype)
                    """
                )

    async def _handle_mention_event(
        self, world_id: str, branch: str, kind: str, payload: Dict[str, Any]
    ) -> None:
        """Handle mention.* events by creating MENTIONS relationships to generic entities."""
        async with self.db_pool.acquire() as conn:
            graph_name = await conn.fetchval(
                "SELECT lens_graph.ensure_graph_exists($1, $2)", world_id, branch
            )
            
            if kind == "mention.added":
                note_id = payload.get("id")
                entity = payload.get("entity")
                created_at = payload.get("created_at", "now()")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (n:Note {{id: '{note_id}', world_id: '{world_id}', branch: '{branch}'}})
                        MERGE (e:Entity {{name: '{entity}', world_id: '{world_id}', branch: '{branch}'}})
                        ON CREATE SET e.entity_type = 'entity'
                        CREATE (n)-[r:MENTIONS {{
                            created_at: '{created_at}',
                            world_id: '{world_id}',
                            branch: '{branch}'
                        }}]->(e)
                        RETURN r
                    $$) AS (result agtype)
                    """
                )
                
            elif kind == "mention.removed":
                note_id = payload.get("id")
                entity = payload.get("entity")
                
                await conn.fetch(
                    f"""
                    SELECT * FROM cypher('{graph_name}', $$
                        MATCH (
                            n:Note {{id: '{note_id}', world_id: '{world_id}', branch: '{branch}'}}
                        )-[r:MENTIONS {{world_id: '{world_id}', branch: '{branch}'}}]->(
                            e:Entity {{name: '{entity}', world_id: '{world_id}', branch: '{branch}'}}
                        )
                        DELETE r
                    $$) AS (result agtype)
                    """
                )

    async def _handle_emo_event(
        self, world_id: str, branch: str, kind: str, payload: Dict[str, Any]
    ):
        """Handle EMO events by creating/updating graph nodes and relationships"""
        try:
            async with self.db_pool.acquire() as conn:
                if kind == "emo.created":
                    await self._handle_emo_created(conn, world_id, branch, payload)
                elif kind == "emo.updated":
                    await self._handle_emo_updated(conn, world_id, branch, payload)
                elif kind == "emo.linked":
                    await self._handle_emo_linked(conn, world_id, branch, payload)
                elif kind == "emo.deleted":
                    await self._handle_emo_deleted(conn, world_id, branch, payload)
                else:
                    self.logger.warning(f"Unknown EMO event kind: {kind}")
        except Exception as e:
            self.logger.error(f"Failed to handle EMO event {kind}: {e}")
            raise

    async def _handle_emo_created(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle emo.created by adding EMO node and relationships"""
        emo_id = payload["emo_id"]
        emo_type = payload["emo_type"]
        emo_version = payload["emo_version"]

        # Create node properties
        properties = {
            "emo_version": emo_version,
            "emo_type": emo_type,
            "tenant_id": payload["tenant_id"],
            "mime_type": payload.get("mime_type", "text/markdown"),
            "tags": payload.get("tags", []),
            "source_kind": payload["source"]["kind"],
            "created_at": "now()",
        }

        # Add EMO node using graph functions
        await conn.fetchval(
            "SELECT lens_emo.add_emo_node($1::uuid, $2, $3::uuid, $4, $5::jsonb)",
            world_id,
            branch,
            emo_id,
            emo_type,
            properties,
        )

        # Handle parent relationships
        for parent in payload.get("parents", []):
            await conn.fetchval(
                "SELECT lens_emo.add_emo_relationship($1::uuid, $2, $3::uuid, $4::uuid, $5)",
                world_id,
                branch,
                emo_id,
                parent["emo_id"],
                parent["rel"],
            )

        self.logger.debug(f"Created EMO graph node {emo_id} in {world_id}/{branch}")

    async def _handle_emo_updated(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle emo.updated by updating EMO node properties"""
        emo_id = payload["emo_id"]
        emo_type = payload["emo_type"]
        emo_version = payload["emo_version"]

        # Update node properties
        properties = {
            "emo_version": emo_version,
            "emo_type": emo_type,
            "tenant_id": payload["tenant_id"],
            "mime_type": payload.get("mime_type", "text/markdown"),
            "tags": payload.get("tags", []),
            "updated_at": "now()",
        }

        # Update EMO node (this will merge/update existing node)
        await conn.fetchval(
            "SELECT lens_emo.add_emo_node($1::uuid, $2, $3::uuid, $4, $5::jsonb)",
            world_id,
            branch,
            emo_id,
            emo_type,
            properties,
        )

        self.logger.debug(f"Updated EMO graph node {emo_id} to v{emo_version} in {world_id}/{branch}")

    async def _handle_emo_linked(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle emo.linked by adding/updating relationships"""
        emo_id = payload["emo_id"]

        # Handle parent relationships
        for parent in payload.get("parents", []):
            await conn.fetchval(
                "SELECT lens_emo.add_emo_relationship($1::uuid, $2, $3::uuid, $4::uuid, $5)",
                world_id,
                branch,
                emo_id,
                parent["emo_id"],
                parent["rel"],
            )

        # Handle EMO-to-EMO links
        for link in payload.get("links", []):
            if link["kind"] == "emo":
                await conn.fetchval(
                    "SELECT lens_emo.add_emo_relationship($1::uuid, $2, $3::uuid, $4::uuid, 'linked')",
                    world_id,
                    branch,
                    emo_id,
                    link["ref"],
                )

        self.logger.debug(f"Updated EMO links for {emo_id} in {world_id}/{branch}")

    async def _handle_emo_deleted(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle emo.deleted by soft-deleting EMO node"""
        emo_id = payload["emo_id"]

        # Soft delete EMO node
        await conn.fetchval(
            "SELECT lens_emo.remove_emo_node($1::uuid, $2, $3::uuid)",
            world_id,
            branch,
            emo_id,
        )

        self.logger.debug(f"Soft deleted EMO graph node {emo_id} from {world_id}/{branch}")

    async def _get_state_snapshot(
        self, conn: asyncpg.Connection, world_id: str, branch: str
    ) -> Dict[str, Any]:
        """Deterministic snapshot for state hashing: counts and sample IDs."""
        # Use direct AGE calls instead of broken wrapper
        # First ensure graph exists and get graph name
        graph_name = await conn.fetchval(
            "SELECT lens_graph.ensure_graph_exists($1, $2)", world_id, branch
        )
        
        try:
            # Basic node count
            node_count_result = await conn.fetch(
                f"""
                SELECT * FROM cypher('{graph_name}', $$
                    MATCH (n) RETURN COUNT(n) as count
                $$) AS (result agtype)
                """
            )
            node_count = node_count_result[0]['result']['count'] if node_count_result else 0
            
            # Basic edge count
            edge_count_result = await conn.fetch(
                f"""
                SELECT * FROM cypher('{graph_name}', $$
                    MATCH ()-[r]->() RETURN COUNT(r) as count
                $$) AS (result agtype)
                """
            )
            edge_count = edge_count_result[0]['result']['count'] if edge_count_result else 0
            
            # Sample note IDs for deterministic comparison
            note_ids_result = await conn.fetch(
                f"""
                SELECT * FROM cypher('{graph_name}', $$
                    MATCH (n:Note) RETURN n.id as id ORDER BY id LIMIT 100
                $$) AS (result agtype)
                """
            )
            note_ids = [row['result']['id'] for row in note_ids_result] if note_ids_result else []
            
        except Exception as e:
            self.logger.warning(f"Failed to get graph state snapshot: {e}")
            # Return empty state if graph operations fail
            node_count = edge_count = 0
            note_ids = []
        
        # Get EMO graph statistics
        try:
            emo_stats_result = await conn.fetchrow(
                "SELECT * FROM lens_emo.get_emo_graph_stats($1::uuid, $2)",
                world_id,
                branch,
            )
            emo_stats = {
                "total_nodes": emo_stats_result["total_nodes"] if emo_stats_result else 0,
                "active_nodes": emo_stats_result["active_nodes"] if emo_stats_result else 0,
                "total_relationships": emo_stats_result["total_relationships"] if emo_stats_result else 0,
            }
        except Exception as e:
            self.logger.warning(f"Failed to get EMO graph stats: {e}")
            emo_stats = {"total_nodes": 0, "active_nodes": 0, "total_relationships": 0}

        return {
            "lens": "graph",
            "world_id": world_id,
            "branch": branch,
            "graph_name": graph_name,
            "node_count": node_count,
            "edge_count": edge_count,
            "note_ids": sorted(note_ids),  # Ensure deterministic ordering
            "emo_graph_stats": emo_stats,
        }

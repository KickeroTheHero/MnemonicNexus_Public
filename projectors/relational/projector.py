import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from typing import Any, Dict

import asyncpg
from sdk.projector import ProjectorSDK


class RelationalProjector(ProjectorSDK):
    """Relational lens projector implementation"""

    @property
    def name(self) -> str:
        return "projector_rel"

    @property
    def lens(self) -> str:
        return "rel"

    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to relational lens with idempotency"""
        kind = envelope["kind"]
        payload = envelope["payload"]
        world_id = envelope["world_id"]
        branch = envelope["branch"]

        self.logger.info(f"Processing {kind} event for {world_id}/{branch} (seq: {global_seq})")

        async with self.db_pool.acquire() as conn:
            if kind == "note.created":
                await self._handle_note_created(conn, world_id, branch, payload)
            elif kind == "note.updated":
                await self._handle_note_updated(conn, world_id, branch, payload)
            elif kind == "note.deleted":
                await self._handle_note_deleted(conn, world_id, branch, payload)
            elif kind == "tag.added":
                await self._handle_tag_added(conn, world_id, branch, payload)
            elif kind == "tag.removed":
                await self._handle_tag_removed(conn, world_id, branch, payload)
            elif kind == "link.added":
                await self._handle_link_added(conn, world_id, branch, payload)
            elif kind == "link.removed":
                await self._handle_link_removed(conn, world_id, branch, payload)
            else:
                self.logger.warning(f"Unknown event kind: {kind}")

    async def _handle_note_created(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.created event idempotently"""
        await conn.execute(
            """
            INSERT INTO lens_rel.note (
                world_id, branch, note_id, title, body, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, COALESCE($6::timestamptz, now()), COALESCE($6::timestamptz, now()))
            ON CONFLICT (world_id, branch, note_id) DO NOTHING
        """,
            world_id,
            branch,
            payload["id"],
            payload["title"],
            payload.get("body", ""),
            payload.get("created_at"),
        )

        self.logger.debug(f"Created note {payload['id']} in {world_id}/{branch}")

    async def _handle_note_updated(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.updated event idempotently"""
        updated_rows = await conn.execute(
            """
            UPDATE lens_rel.note 
            SET title = $4, body = $5, updated_at = COALESCE($6::timestamptz, now())
            WHERE world_id = $1 AND branch = $2 AND note_id = $3
        """,
            world_id,
            branch,
            payload["id"],
            payload["title"],
            payload.get("body", ""),
            payload.get("updated_at"),
        )

        self.logger.debug(
            f"Updated note {payload['id']} in {world_id}/{branch} (rows: {updated_rows})"
        )

    async def _handle_note_deleted(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle note.deleted event idempotently"""
        # Soft delete - could also be hard delete depending on requirements
        await conn.execute(
            """
            UPDATE lens_rel.note 
            SET updated_at = now()
            WHERE world_id = $1 AND branch = $2 AND note_id = $3
        """,
            world_id,
            branch,
            payload["id"],
        )

        # Also remove associated tags and links
        await conn.execute(
            """
            DELETE FROM lens_rel.note_tag 
            WHERE world_id = $1 AND branch = $2 AND note_id = $3
        """,
            world_id,
            branch,
            payload["id"],
        )

        await conn.execute(
            """
            DELETE FROM lens_rel.link 
            WHERE world_id = $1 AND branch = $2 AND (src_id = $3 OR dst_id = $3)
        """,
            world_id,
            branch,
            payload["id"],
        )

        self.logger.debug(
            f"Deleted note {payload['id']} and associated data from {world_id}/{branch}"
        )

    async def _handle_tag_added(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle tag.added event idempotently"""
        await conn.execute(
            """
            INSERT INTO lens_rel.note_tag (
                world_id, branch, note_id, tag, applied_at
            ) VALUES ($1, $2, $3, $4, COALESCE($5::timestamptz, now()))
            ON CONFLICT (world_id, branch, note_id, tag) DO NOTHING
        """,
            world_id,
            branch,
            payload["id"],
            payload["tag"],
            payload.get("applied_at"),
        )

        self.logger.debug(
            f"Added tag '{payload['tag']}' to note {payload['id']} in {world_id}/{branch}"
        )

    async def _handle_tag_removed(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle tag.removed event idempotently"""
        deleted_rows = await conn.execute(
            """
            DELETE FROM lens_rel.note_tag 
            WHERE world_id = $1 AND branch = $2 AND note_id = $3 AND tag = $4
        """,
            world_id,
            branch,
            payload["id"],
            payload["tag"],
        )

        self.logger.debug(
            f"Removed tag '{payload['tag']}' from note {payload['id']} in {world_id}/{branch} (rows: {deleted_rows})"
        )

    async def _handle_link_added(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle link.added event idempotently"""
        await conn.execute(
            """
            INSERT INTO lens_rel.link (
                world_id, branch, src_id, dst_id, link_type, created_at
            ) VALUES ($1, $2, $3, $4, $5, COALESCE($6::timestamptz, now()))
            ON CONFLICT (world_id, branch, src_id, dst_id, link_type) DO NOTHING
        """,
            world_id,
            branch,
            payload["src"],
            payload["dst"],
            payload.get("link_type", "default"),
            payload.get("created_at"),
        )

        self.logger.debug(f"Added link {payload['src']} -> {payload['dst']} in {world_id}/{branch}")

    async def _handle_link_removed(
        self, conn: asyncpg.Connection, world_id: str, branch: str, payload: Dict[str, Any]
    ):
        """Handle link.removed event idempotently"""
        deleted_rows = await conn.execute(
            """
            DELETE FROM lens_rel.link 
            WHERE world_id = $1 AND branch = $2 AND src_id = $3 AND dst_id = $4 AND link_type = $5
        """,
            world_id,
            branch,
            payload["src"],
            payload["dst"],
            payload.get("link_type", "default"),
        )

        self.logger.debug(
            f"Removed link {payload['src']} -> {payload['dst']} from {world_id}/{branch} (rows: {deleted_rows})"
        )

    async def _get_state_snapshot(
        self, conn: asyncpg.Connection, world_id: str, branch: str
    ) -> Dict[str, Any]:
        """Get deterministic relational lens state snapshot"""

        # Get sorted note data for deterministic hash
        notes = await conn.fetch(
            """
            SELECT note_id, title, body, created_at, updated_at
            FROM lens_rel.note
            WHERE world_id = $1 AND branch = $2
            ORDER BY note_id
        """,
            world_id,
            branch,
        )

        # Get sorted tag data
        tags = await conn.fetch(
            """
            SELECT note_id, tag, applied_at
            FROM lens_rel.note_tag
            WHERE world_id = $1 AND branch = $2  
            ORDER BY note_id, tag
        """,
            world_id,
            branch,
        )

        # Get sorted link data
        links = await conn.fetch(
            """
            SELECT src_id, dst_id, link_type, created_at
            FROM lens_rel.link
            WHERE world_id = $1 AND branch = $2
            ORDER BY src_id, dst_id, link_type
        """,
            world_id,
            branch,
        )

        # Convert to serializable format
        def serialize_record(record):
            """Convert asyncpg record to JSON-serializable dict"""
            import uuid

            result = dict(record)
            for key, value in result.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    result[key] = str(value)
            return result

        return {
            "lens": "relational",
            "world_id": world_id,
            "branch": branch,
            "notes": [serialize_record(note) for note in notes],
            "tags": [serialize_record(tag) for tag in tags],
            "links": [serialize_record(link) for link in links],
        }

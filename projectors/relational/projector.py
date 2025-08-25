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

        self.logger.info(
            f"Processing {kind} event for {world_id}/{branch} (seq: {global_seq})"
        )

        async with self.db_pool.acquire() as conn:
            # Legacy note events
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
            # EMO events
            elif kind == "emo.created":
                await self._handle_emo_created(conn, world_id, branch, payload)
            elif kind == "emo.updated":
                await self._handle_emo_updated(conn, world_id, branch, payload)
            elif kind == "emo.linked":
                await self._handle_emo_linked(conn, world_id, branch, payload)
            elif kind == "emo.deleted":
                await self._handle_emo_deleted(conn, world_id, branch, payload)
            else:
                self.logger.warning(f"Unknown event kind: {kind}")

    async def _handle_note_created(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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

        self.logger.debug(
            f"Added link {payload['src']} -> {payload['dst']} in {world_id}/{branch}"
        )

    async def _handle_link_removed(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
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

    async def _handle_emo_created(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
    ):
        """Handle emo.created event idempotently"""
        await conn.execute(
            """
            INSERT INTO lens_emo.emo_current (
                emo_id, emo_type, emo_version, tenant_id, world_id, branch,
                mime_type, content, tags, source_kind, source_uri, updated_at
            ) VALUES (
                $1::uuid, $2, $3, $4::uuid, $5::uuid, $6, 
                $7, $8, $9, $10, $11, now()
            )
            ON CONFLICT (emo_id, world_id, branch) DO NOTHING
        """,
            payload["emo_id"],
            payload["emo_type"],
            payload["emo_version"],
            payload["tenant_id"],
            world_id,
            branch,
            payload.get("mime_type", "text/markdown"),
            payload.get("content"),
            payload.get("tags", []),
            payload["source"]["kind"],
            payload["source"].get("uri"),
        )

        # Handle version history
        await conn.execute(
            """
            INSERT INTO lens_emo.emo_history (
                emo_id, emo_version, world_id, branch, content_hash, updated_at
            ) VALUES ($1::uuid, $2, $3::uuid, $4, $5, now())
            ON CONFLICT (emo_id, emo_version, world_id, branch) DO NOTHING
        """,
            payload["emo_id"],
            payload["emo_version"],
            world_id,
            branch,
            self._compute_emo_content_hash(payload.get("content", "")),
        )

        # Handle links
        await self._handle_emo_links(conn, world_id, branch, payload)

        self.logger.debug(
            f"Created EMO {payload['emo_id']} v{payload['emo_version']} in {world_id}/{branch}"
        )

    async def _handle_emo_updated(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
    ):
        """Handle emo.updated event idempotently"""
        updated_rows = await conn.execute(
            """
            UPDATE lens_emo.emo_current 
            SET emo_version = $3, content = $4, tags = $5, mime_type = $6, updated_at = now()
            WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $7
        """,
            payload["emo_id"],
            world_id,
            payload["emo_version"],
            payload.get("content"),
            payload.get("tags", []),
            payload.get("mime_type", "text/markdown"),
            branch,
        )

        # Add to version history
        await conn.execute(
            """
            INSERT INTO lens_emo.emo_history (
                emo_id, emo_version, world_id, branch, content_hash, updated_at
            ) VALUES ($1::uuid, $2, $3::uuid, $4, $5, now())
            ON CONFLICT (emo_id, emo_version, world_id, branch) DO NOTHING
        """,
            payload["emo_id"],
            payload["emo_version"],
            world_id,
            branch,
            self._compute_emo_content_hash(payload.get("content", "")),
        )

        # Handle updated links
        await self._handle_emo_links(conn, world_id, branch, payload)

        self.logger.debug(
            f"Updated EMO {payload['emo_id']} to v{payload['emo_version']} in {world_id}/{branch} (rows: {updated_rows})"
        )

    async def _handle_emo_linked(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
    ):
        """Handle emo.linked event for lineage relationships"""
        await self._handle_emo_links(conn, world_id, branch, payload)

        self.logger.debug(
            f"Updated links for EMO {payload['emo_id']} in {world_id}/{branch}"
        )

    async def _handle_emo_deleted(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
    ):
        """Handle emo.deleted event (soft delete with full semantics)"""
        emo_id = payload["emo_id"]
        emo_version = payload.get("emo_version", 1)
        deletion_reason = payload.get("deletion_reason")
        idempotency_key = payload.get("idempotency_key")
        change_id = payload.get("change_id")

        # Update the current EMO record with deletion metadata
        await conn.execute(
            """
            UPDATE lens_emo.emo_current 
            SET deleted = TRUE, 
                deleted_at = now(),
                deletion_reason = $4,
                updated_at = now()
            WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $3
        """,
            emo_id,
            world_id,
            branch,
            deletion_reason,
        )

        # Record deletion in history for audit trail
        content_hash = self._compute_emo_content_hash("")  # Deleted content is empty

        try:
            await conn.execute(
                """
                INSERT INTO lens_emo.emo_history (
                    change_id, emo_id, emo_version, world_id, branch, 
                    operation_type, content_hash, idempotency_key
                ) VALUES ($1, $2, $3, $4, $5, 'deleted', $6, $7)
                ON CONFLICT (idempotency_key) DO NOTHING
            """,
                change_id,
                emo_id,
                emo_version,
                world_id,
                branch,
                content_hash,
                idempotency_key,
            )
        except Exception as e:
            self.logger.warning(f"Idempotency violation for EMO deletion {emo_id}: {e}")

        self.logger.debug(
            f"Soft deleted EMO {emo_id} from {world_id}/{branch} (reason: {deletion_reason})"
        )

    async def _handle_emo_links(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        payload: Dict[str, Any],
    ):
        """Handle EMO links (parents and external links)"""
        emo_id = payload["emo_id"]

        # Clear existing links for this EMO
        await conn.execute(
            """
            DELETE FROM lens_emo.emo_links 
            WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $3
        """,
            emo_id,
            world_id,
            branch,
        )

        # Add parent relationships
        for parent in payload.get("parents", []):
            await conn.execute(
                """
                INSERT INTO lens_emo.emo_links (
                    emo_id, world_id, branch, rel, target_emo_id, created_at
                ) VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, now())
            """,
                emo_id,
                world_id,
                branch,
                parent["rel"],
                parent["emo_id"],
            )

        # Add external links
        for link in payload.get("links", []):
            if link["kind"] == "emo":
                await conn.execute(
                    """
                    INSERT INTO lens_emo.emo_links (
                        emo_id, world_id, branch, rel, target_emo_id, created_at
                    ) VALUES ($1::uuid, $2::uuid, $3, 'linked', $4::uuid, now())
                """,
                    emo_id,
                    world_id,
                    branch,
                    link["ref"],
                )
            elif link["kind"] == "uri":
                await conn.execute(
                    """
                    INSERT INTO lens_emo.emo_links (
                        emo_id, world_id, branch, rel, target_uri, created_at
                    ) VALUES ($1::uuid, $2::uuid, $3, 'linked', $4, now())
                """,
                    emo_id,
                    world_id,
                    branch,
                    link["ref"],
                )

    def _compute_emo_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of EMO content"""
        import hashlib

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

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

        # Get EMO data for state snapshot
        emos = await conn.fetch(
            """
            SELECT emo_id, emo_type, emo_version, updated_at, deleted
            FROM lens_emo.emo_current
            WHERE world_id = $1::uuid AND branch = $2
            ORDER BY emo_id
        """,
            world_id,
            branch,
        )

        return {
            "lens": "relational",
            "world_id": world_id,
            "branch": branch,
            "notes": [serialize_record(note) for note in notes],
            "tags": [serialize_record(tag) for tag in tags],
            "links": [serialize_record(link) for link in links],
            "emos": [serialize_record(emo) for emo in emos],
        }

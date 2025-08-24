"""
Database persistence layer for MnemonicNexus V2 Gateway

Handles event storage, retrieval, and idempotency checking with comprehensive validation.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import asyncpg
from validation import ConflictError

if TYPE_CHECKING:
    from models import EventEnvelope


class EventPersistence:
    """Database operations for event storage and retrieval"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def store_event(
        self, envelope: "EventEnvelope", headers: Dict[str, Optional[str]]
    ) -> Dict[str, Any]:
        """Store event with comprehensive validation and integrity"""

        # Enrich envelope with server fields
        enriched_envelope = envelope.dict()
        enriched_envelope["received_at"] = datetime.utcnow().isoformat() + "Z"
        enriched_envelope["payload_hash"] = self._compute_payload_hash(enriched_envelope)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Check idempotency if key provided
                if headers["idempotency_key"]:
                    existing = await self._check_idempotency(
                        conn, envelope.world_id, envelope.branch, headers["idempotency_key"]
                    )
                    if existing:
                        raise ConflictError(
                            f"Duplicate idempotency key: {headers['idempotency_key']}"
                        )

                # Generate event ID
                event_id = str(uuid.uuid4())

                # Insert into event log using the database function
                result = await conn.fetchrow(
                    """
                    SELECT * FROM event_core.insert_event_with_outbox(
                        $1::uuid, $2, $3::uuid, $4, $5::jsonb, $6::timestamptz, $7
                    )
                """,
                    uuid.UUID(envelope.world_id),
                    envelope.branch,
                    uuid.UUID(event_id),
                    envelope.kind,
                    json.dumps(enriched_envelope),
                    (
                        datetime.fromisoformat(envelope.occurred_at.replace("Z", "+00:00"))
                        if envelope.occurred_at
                        else None
                    ),
                    headers["idempotency_key"],
                )

                global_seq = result["insert_event_with_outbox"]

                return {
                    "event_id": event_id,
                    "global_seq": global_seq,
                    "received_at": enriched_envelope["received_at"],
                }

    async def _check_idempotency(
        self, conn: asyncpg.Connection, world_id: str, branch: str, idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Check for existing event with same idempotency key"""
        return await conn.fetchrow(
            """
            SELECT event_id, global_seq, received_at
            FROM event_core.event_log
            WHERE world_id = $1 AND branch = $2 AND idempotency_key = $3
        """,
            uuid.UUID(world_id),
            branch,
            idempotency_key,
        )

    async def list_events(
        self,
        world_id: str,
        branch: str,
        kind: Optional[str],
        after_global_seq: Optional[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """List events with filtering and pagination"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT event_id, world_id, branch, kind, envelope, 
                       global_seq, received_at
                FROM event_core.event_log
                WHERE world_id = $1 AND branch = $2
            """
            params = [uuid.UUID(world_id), branch]

            if kind:
                query += " AND kind = $3"
                params.append(kind)

            if after_global_seq:
                query += f" AND global_seq > ${len(params) + 1}"
                params.append(after_global_seq)

            query += f" ORDER BY global_seq LIMIT ${len(params) + 1}"
            params.append(limit)

            rows = await conn.fetch(query, *params)

            return [
                {
                    "event_id": str(row["event_id"]),
                    "world_id": str(row["world_id"]),
                    "branch": row["branch"],
                    "kind": row["kind"],
                    "global_seq": row["global_seq"],
                    "received_at": row["received_at"].isoformat() + "Z",
                    **json.loads(row["envelope"]),
                }
                for row in rows
            ]

    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get specific event by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT event_id, world_id, branch, kind, envelope,
                       global_seq, received_at
                FROM event_core.event_log
                WHERE event_id = $1
            """,
                uuid.UUID(event_id),
            )

            if not row:
                return None

            return {
                "event_id": str(row["event_id"]),
                "world_id": str(row["world_id"]),
                "branch": row["branch"],
                "kind": row["kind"],
                "global_seq": row["global_seq"],
                "received_at": row["received_at"].isoformat() + "Z",
                **json.loads(row["envelope"]),
            }

    async def get_projector_lag(self) -> Dict[str, Any]:
        """Get projector lag information for health checks"""
        async with self.pool.acquire() as conn:
            # Get latest event sequence
            latest_seq = await conn.fetchval(
                """
                SELECT COALESCE(MAX(global_seq), 0) FROM event_core.event_log
            """
            )

            # Get watermark information - handle case where table doesn't exist yet
            try:
                watermarks = await conn.fetch(
                    """
                    SELECT world_id, branch, projector_name, watermark
                    FROM projector_core.watermark
                    ORDER BY world_id, branch, projector_name
                """
                )
            except Exception:
                # Watermark table doesn't exist yet - projectors not initialized
                return {
                    "latest_global_seq": latest_seq,
                    "projectors": {},
                    "note": "Projector watermarks not yet initialized",
                }

            # Calculate lag
            projector_status = {}
            for wm in watermarks:
                projector = wm["projector_name"]
                if projector not in projector_status:
                    projector_status[projector] = {
                        "latest_watermark": wm["watermark"],
                        "lag": latest_seq - wm["watermark"] if latest_seq > wm["watermark"] else 0,
                    }
                else:
                    # Update if this watermark is newer
                    if wm["watermark"] > projector_status[projector]["latest_watermark"]:
                        projector_status[projector]["latest_watermark"] = wm["watermark"]
                        projector_status[projector]["lag"] = (
                            latest_seq - wm["watermark"] if latest_seq > wm["watermark"] else 0
                        )

            return {"latest_global_seq": latest_seq, "projectors": projector_status}

    def _compute_payload_hash(self, envelope: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of canonical envelope"""
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

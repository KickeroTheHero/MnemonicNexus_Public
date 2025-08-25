"""
Memory-to-EMO Dual-Write Translator Shim

This module translates legacy memory.* events to new emo.* events
to enable EMO identity, versioning, and lineage while maintaining
backward compatibility with existing memory event contracts.

Alpha-safe: No compaction, preserves all existing memory.* behavior.
"""

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

# Add parent directories to path for SDK imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.projector import ProjectorSDK


class MemoryToEMOTranslator(ProjectorSDK):
    """
    Translator shim that converts memory.* events to emo.* events

    Responsibilities:
    - On memory.item.upserted: emit emo.created (new) or emo.updated (existing)
    - On memory.item.deleted: emit emo.deleted
    - Infer lineage relationships from source.uri when possible
    - Maintain version tracking and identity consistency
    """

    @property
    def name(self) -> str:
        return "translator_memory_to_emo"

    @property
    def lens(self) -> str:
        return "translator"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._emo_versions: Dict[str, int] = {}  # Cache for EMO versions

    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply memory event translation to EMO events"""
        kind = envelope["kind"]
        payload = envelope["payload"]
        world_id = envelope["world_id"]
        branch = envelope["branch"]

        self.logger.info(
            f"Translating {kind} event for {world_id}/{branch} (seq: {global_seq})"
        )

        # Only translate memory.* events
        if not kind.startswith("memory."):
            self.logger.debug(f"Skipping non-memory event: {kind}")
            return

        async with self.db_pool.acquire() as conn:
            try:
                if kind == "memory.item.upserted":
                    await self._translate_memory_upserted(conn, envelope, payload)
                elif kind == "memory.item.deleted":
                    await self._translate_memory_deleted(conn, envelope, payload)
                elif kind == "memory.embed.generated":
                    await self._translate_memory_embed(conn, envelope, payload)
                else:
                    self.logger.warning(f"Unknown memory event kind: {kind}")

            except Exception as e:
                self.logger.error(f"Translation failed for {kind}: {e}")
                # Don't re-raise to avoid blocking other projectors
                # Log error but continue processing

    async def _translate_memory_upserted(
        self,
        conn: asyncpg.Connection,
        envelope: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> None:
        """Translate memory.item.upserted to emo.created or emo.updated"""

        memory_id = payload["id"]
        world_id = envelope["world_id"]
        branch = envelope["branch"]

        # Derive EMO ID from memory ID (deterministic mapping)
        emo_id = self._derive_emo_id(memory_id)

        # Check if this EMO already exists
        current_version = await self._get_emo_current_version(
            conn, emo_id, world_id, branch
        )
        is_new_emo = current_version == 0

        # Increment version for updates
        new_version = 1 if is_new_emo else current_version + 1

        # Build EMO envelope
        emo_envelope = {
            "world_id": world_id,
            "branch": branch,
            "kind": "emo.created" if is_new_emo else "emo.updated",
            "by": envelope["by"],
            "payload": {
                "emo_id": str(emo_id),
                "emo_type": self._infer_emo_type(payload),
                "emo_version": new_version,
                "tenant_id": envelope.get(
                    "tenant_id", world_id
                ),  # fallback to world_id
                "world_id": world_id,
                "branch": branch,
                "source": self._extract_source_info(envelope, payload),
                "mime_type": payload.get("mime_type", "text/markdown"),
                "content": payload.get("content", payload.get("body", "")),
                "tags": payload.get("tags", []),
                "parents": self._infer_parents(payload),
                "links": self._extract_links(payload),
                "vector_meta": self._extract_vector_meta(payload),
                "schema_version": 1,
            },
            "occurred_at": envelope.get("occurred_at"),
            "trace_id": envelope.get("trace_id"),
        }

        # Emit the translated EMO event to the event log
        await self._emit_emo_event(conn, emo_envelope)

        # Cache the new version
        cache_key = f"{emo_id}:{world_id}:{branch}"
        self._emo_versions[cache_key] = new_version

        self.logger.info(
            f"Translated memory.item.upserted -> {emo_envelope['kind']} "
            f"for EMO {emo_id} v{new_version}"
        )

    async def _translate_memory_deleted(
        self,
        conn: asyncpg.Connection,
        envelope: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> None:
        """Translate memory.item.deleted to emo.deleted"""

        memory_id = payload["id"]
        world_id = envelope["world_id"]
        branch = envelope["branch"]

        # Derive EMO ID from memory ID
        emo_id = self._derive_emo_id(memory_id)

        # Get current version (if exists)
        current_version = await self._get_emo_current_version(
            conn, emo_id, world_id, branch
        )
        if current_version == 0:
            self.logger.warning(f"Attempting to delete non-existent EMO {emo_id}")
            return

        # Build EMO deletion envelope
        emo_envelope = {
            "world_id": world_id,
            "branch": branch,
            "kind": "emo.deleted",
            "by": envelope["by"],
            "payload": {
                "emo_id": str(emo_id),
                "emo_version": current_version,
                "tenant_id": envelope.get("tenant_id", world_id),
                "world_id": world_id,
                "branch": branch,
                "schema_version": 1,
            },
            "occurred_at": envelope.get("occurred_at"),
            "trace_id": envelope.get("trace_id"),
        }

        # Emit the deletion event
        await self._emit_emo_event(conn, emo_envelope)

        self.logger.info(
            f"Translated memory.item.deleted -> emo.deleted for EMO {emo_id}"
        )

    async def _translate_memory_embed(
        self,
        conn: asyncpg.Connection,
        envelope: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> None:
        """Handle memory.embed.generated events (optional audit)"""
        # For now, just log these events
        # In the future, could emit emo.embed.generated or similar
        memory_id = payload.get("memory_id")
        model_id = payload.get("model_id")

        self.logger.info(
            f"Memory embedding generated for {memory_id} using model {model_id}"
        )

    def _derive_emo_id(self, memory_id: str) -> uuid.UUID:
        """Derive deterministic EMO ID from memory ID"""
        # Use namespace UUID to ensure deterministic mapping
        # This ensures same memory ID always maps to same EMO ID
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return uuid.uuid5(namespace, f"memory:{memory_id}")

    def _infer_emo_type(self, payload: Dict[str, Any]) -> str:
        """Infer EMO type from memory payload"""
        # Simple heuristic - can be enhanced
        content = payload.get("content", payload.get("body", ""))
        title = payload.get("title", "")

        # Check for document-like characteristics
        if len(content) > 1000 or "# " in content or "## " in content:
            return "doc"

        # Check for factual statements
        if any(word in title.lower() for word in ["fact", "definition", "rule"]):
            return "fact"

        # Check for profile information
        if any(word in title.lower() for word in ["profile", "person", "contact"]):
            return "profile"

        # Default to note
        return "note"

    def _extract_source_info(
        self, envelope: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract source information from memory envelope/payload"""
        by_info = envelope.get("by", {})
        agent_info = by_info.get("agent", "unknown")

        # Determine source kind
        if agent_info == "user" or "user" in agent_info.lower():
            source_kind = "user"
        elif "ingest" in agent_info.lower() or "import" in agent_info.lower():
            source_kind = "ingest"
        else:
            source_kind = "agent"

        source = {"kind": source_kind}

        # Add URI if available
        source_uri = payload.get("source_uri") or payload.get("uri")
        if source_uri:
            source["uri"] = source_uri

        return source

    def _infer_parents(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Infer parent relationships from payload"""
        parents = []

        # Look for explicit parent references
        parent_id = payload.get("parent_id")
        if parent_id:
            parent_emo_id = self._derive_emo_id(parent_id)
            parents.append({"emo_id": str(parent_emo_id), "rel": "derived"})

        # Look for supersession relationships
        supersedes_id = payload.get("supersedes")
        if supersedes_id:
            supersedes_emo_id = self._derive_emo_id(supersedes_id)
            parents.append({"emo_id": str(supersedes_emo_id), "rel": "supersedes"})

        # Look for merge sources
        merged_from = payload.get("merged_from", [])
        for merge_id in merged_from:
            merge_emo_id = self._derive_emo_id(merge_id)
            parents.append({"emo_id": str(merge_emo_id), "rel": "merges"})

        return parents

    def _extract_links(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract external links from payload"""
        links = []

        # Extract URI links
        external_links = payload.get("links", [])
        for link in external_links:
            if isinstance(link, str):
                links.append({"kind": "uri", "ref": link})
            elif isinstance(link, dict) and "uri" in link:
                links.append({"kind": "uri", "ref": link["uri"]})

        # Extract EMO references
        emo_refs = payload.get("references", [])
        for ref_id in emo_refs:
            ref_emo_id = self._derive_emo_id(ref_id)
            links.append({"kind": "emo", "ref": str(ref_emo_id)})

        return links

    def _extract_vector_meta(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract vector metadata if available"""
        embedding_info = payload.get("embedding")
        if not embedding_info:
            return None

        vector_meta = {}
        if "model_id" in embedding_info:
            vector_meta["model_id"] = embedding_info["model_id"]
        if "embed_dim" in embedding_info:
            vector_meta["embed_dim"] = embedding_info["embed_dim"]
        if "model_version" in embedding_info:
            vector_meta["model_version"] = embedding_info["model_version"]
        if "template_id" in embedding_info:
            vector_meta["template_id"] = embedding_info["template_id"]

        return vector_meta if vector_meta else None

    async def _get_emo_current_version(
        self, conn: asyncpg.Connection, emo_id: uuid.UUID, world_id: str, branch: str
    ) -> int:
        """Get current version of EMO, 0 if doesn't exist"""

        # Check cache first
        cache_key = f"{emo_id}:{world_id}:{branch}"
        if cache_key in self._emo_versions:
            return self._emo_versions[cache_key]

        # Query database
        try:
            result = await conn.fetchval(
                """
                SELECT emo_version 
                FROM lens_emo.emo_current 
                WHERE emo_id = $1 AND world_id = $2::uuid AND branch = $3 AND NOT deleted
            """,
                emo_id,
                world_id,
                branch,
            )
            version = result or 0
            self._emo_versions[cache_key] = version
            return version
        except Exception as e:
            self.logger.warning(f"Failed to get EMO version for {emo_id}: {e}")
            return 0

    async def _emit_emo_event(
        self, conn: asyncpg.Connection, emo_envelope: Dict[str, Any]
    ) -> None:
        """Emit translated EMO event to the event log"""

        # Generate event ID
        event_id = str(uuid.uuid4())

        # Compute payload hash
        payload_json = json.dumps(emo_envelope["payload"], sort_keys=True)
        payload_hash = self._compute_payload_hash(payload_json)

        # Insert into event log
        try:
            await conn.execute(
                """
                INSERT INTO event_core.event_log (
                    event_id, world_id, branch, kind, envelope, 
                    occurred_at, payload_hash
                ) VALUES ($1, $2::uuid, $3, $4, $5, $6, $7)
            """,
                uuid.UUID(event_id),
                emo_envelope["world_id"],
                emo_envelope["branch"],
                emo_envelope["kind"],
                json.dumps(emo_envelope),
                emo_envelope.get("occurred_at"),
                payload_hash,
            )

            self.logger.debug(f"Emitted EMO event {event_id}: {emo_envelope['kind']}")

        except Exception as e:
            self.logger.error(f"Failed to emit EMO event: {e}")
            raise

    def _compute_payload_hash(self, payload_json: str) -> str:
        """Compute SHA-256 hash of payload"""
        import hashlib

        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    async def _get_state_snapshot(
        self, conn: asyncpg.Connection, world_id: str, branch: str
    ) -> Dict[str, Any]:
        """Get translator state snapshot (minimal for now)"""
        return {
            "lens": "translator",
            "world_id": world_id,
            "branch": branch,
            "translated_events": len(self._emo_versions),
            "cached_versions": dict(self._emo_versions),
        }


# Main execution
if __name__ == "__main__":
    import asyncio

    config = {
        "database_url": os.getenv(
            "PROJECTOR_DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/nexus",
        ),
        "projector_name": os.getenv("PROJECTOR_NAME", "translator_memory_to_emo"),
        "projector_lens": os.getenv("PROJECTOR_LENS", "translator"),
        "projector_port": int(os.getenv("PROJECTOR_PORT", "8000")),
        "projector_host": os.getenv("PROJECTOR_HOST", "0.0.0.0"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }

    translator = MemoryToEMOTranslator(config)

    async def run_translator():
        try:
            await translator.start_polling()
        except KeyboardInterrupt:
            print("Shutting down translator...")
            await translator.shutdown()
        except Exception as e:
            print(f"Translator error: {e}")
            await translator.shutdown()
            raise

    asyncio.run(run_translator())

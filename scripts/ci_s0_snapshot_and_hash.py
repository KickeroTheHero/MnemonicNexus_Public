#!/usr/bin/env python3
"""
CI Script: S0 Snapshot and Hash
Job: ci:s0:snapshot-and-hash

Per MNX checklist: lens snapshots + state hashes per branch/tenant.
Validates deterministic state across all projectors for given world/branch.
"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any

import asyncpg


async def get_projector_state_snapshots(
    world_id: str, branch: str = "main"
) -> Dict[str, Any]:
    """Get state snapshots from all projectors for deterministic hashing"""

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    )

    snapshots = {}

    async with asyncpg.create_pool(database_url, min_size=1, max_size=5) as pool:
        async with pool.acquire() as conn:

            # Relational lens snapshot
            try:
                # Notes
                notes = await conn.fetch(
                    """
                    SELECT note_id, title, body, created_at, updated_at
                    FROM lens_rel.note
                    WHERE world_id = $1::uuid AND branch = $2
                    ORDER BY note_id
                """,
                    world_id,
                    branch,
                )

                # EMOs
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

                # Tags
                tags = await conn.fetch(
                    """
                    SELECT note_id, tag, applied_at
                    FROM lens_rel.note_tag
                    WHERE world_id = $1::uuid AND branch = $2  
                    ORDER BY note_id, tag
                """,
                    world_id,
                    branch,
                )

                # Links
                links = await conn.fetch(
                    """
                    SELECT src_id, dst_id, link_type, created_at
                    FROM lens_rel.link
                    WHERE world_id = $1::uuid AND branch = $2
                    ORDER BY src_id, dst_id, link_type
                """,
                    world_id,
                    branch,
                )

                # EMO Links
                emo_links = await conn.fetch(
                    """
                    SELECT emo_id, rel, target_emo_id, target_uri, created_at
                    FROM lens_emo.emo_links
                    WHERE world_id = $1::uuid AND branch = $2
                    ORDER BY emo_id, rel
                """,
                    world_id,
                    branch,
                )

                snapshots["relational"] = {
                    "lens": "relational",
                    "world_id": world_id,
                    "branch": branch,
                    "notes": [dict(note) for note in notes],
                    "emos": [dict(emo) for emo in emos],
                    "tags": [dict(tag) for tag in tags],
                    "links": [dict(link) for link in links],
                    "emo_links": [dict(link) for link in emo_links],
                }

            except Exception as e:
                print(f"Failed to get relational snapshot: {e}")
                snapshots["relational"] = {"error": str(e)}

            # Semantic lens snapshot
            try:
                # Legacy embeddings
                embeddings = await conn.fetch(
                    """
                    SELECT entity_id, entity_type, model_name, model_version, dimensions, created_at
                    FROM lens_sem.embedding
                    WHERE world_id = $1::uuid AND branch = $2
                    ORDER BY entity_id, model_name
                """,
                    world_id,
                    branch,
                )

                # EMO embeddings
                emo_embeddings = await conn.fetch(
                    """
                    SELECT emo_id, emo_version, model_id, embed_dim, model_version, created_at
                    FROM lens_emo.emo_embeddings
                    WHERE world_id = $1::uuid AND branch = $2
                    ORDER BY emo_id, emo_version
                """,
                    world_id,
                    branch,
                )

                snapshots["semantic"] = {
                    "lens": "semantic",
                    "world_id": world_id,
                    "branch": branch,
                    "embeddings": [dict(emb) for emb in embeddings],
                    "emo_embeddings": [dict(emb) for emb in emo_embeddings],
                    "embedding_count": len(embeddings),
                    "emo_embedding_count": len(emo_embeddings),
                }

            except Exception as e:
                print(f"Failed to get semantic snapshot: {e}")
                snapshots["semantic"] = {"error": str(e)}

            # Graph lens snapshot
            try:
                # Get graph name
                graph_name = await conn.fetchval(
                    "SELECT lens_graph.ensure_graph_exists($1::uuid, $2)",
                    world_id,
                    branch,
                )

                # Get basic graph stats (node/edge counts)
                try:
                    node_count_result = await conn.fetch(
                        f"""
                        SELECT * FROM cypher('{graph_name}', $$
                            MATCH (n) RETURN COUNT(n) as count
                        $$) AS (result agtype)
                        """
                    )
                    node_count = (
                        node_count_result[0]["result"]["count"]
                        if node_count_result
                        else 0
                    )

                    edge_count_result = await conn.fetch(
                        f"""
                        SELECT * FROM cypher('{graph_name}', $$
                            MATCH ()-[r]->() RETURN COUNT(r) as count
                        $$) AS (result agtype)
                        """
                    )
                    edge_count = (
                        edge_count_result[0]["result"]["count"]
                        if edge_count_result
                        else 0
                    )

                    # Sample note IDs for deterministic comparison
                    note_ids_result = await conn.fetch(
                        f"""
                        SELECT * FROM cypher('{graph_name}', $$
                            MATCH (n:Note) RETURN n.id as id ORDER BY id LIMIT 100
                        $$) AS (result agtype)
                        """
                    )
                    note_ids = (
                        [row["result"]["id"] for row in note_ids_result]
                        if note_ids_result
                        else []
                    )

                except Exception as graph_e:
                    print(f"Graph query failed: {graph_e}")
                    node_count = edge_count = 0
                    note_ids = []

                # EMO graph stats
                try:
                    emo_stats_result = await conn.fetchrow(
                        "SELECT * FROM lens_emo.get_emo_graph_stats($1::uuid, $2)",
                        world_id,
                        branch,
                    )
                    emo_stats = {
                        "total_nodes": (
                            emo_stats_result["total_nodes"] if emo_stats_result else 0
                        ),
                        "active_nodes": (
                            emo_stats_result["active_nodes"] if emo_stats_result else 0
                        ),
                        "total_relationships": (
                            emo_stats_result["total_relationships"]
                            if emo_stats_result
                            else 0
                        ),
                    }
                except Exception as e:
                    emo_stats = {
                        "total_nodes": 0,
                        "active_nodes": 0,
                        "total_relationships": 0,
                    }

                snapshots["graph"] = {
                    "lens": "graph",
                    "world_id": world_id,
                    "branch": branch,
                    "graph_name": graph_name,
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "note_ids": sorted(note_ids),
                    "emo_graph_stats": emo_stats,
                }

            except Exception as e:
                print(f"Failed to get graph snapshot: {e}")
                snapshots["graph"] = {"error": str(e)}

    return snapshots


def compute_determinism_state_hash(snapshots: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of all lens states"""

    # Serialize snapshots with deterministic ordering
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return str(obj)

    # Sort keys recursively for deterministic serialization
    def sort_dict_recursive(d):
        if isinstance(d, dict):
            return {k: sort_dict_recursive(v) for k, v in sorted(d.items())}
        elif isinstance(d, list):
            return [sort_dict_recursive(item) for item in d]
        else:
            return d

    sorted_snapshots = sort_dict_recursive(snapshots)
    canonical_json = json.dumps(
        sorted_snapshots, default=serialize_datetime, sort_keys=True
    )

    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


async def main():
    """Main CI validation function"""
    if len(sys.argv) < 2:
        print("Usage: python ci_s0_snapshot_and_hash.py <world_id> [branch]")
        sys.exit(1)

    world_id = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"

    print(f"🔍 Taking S0 snapshot for world {world_id}, branch '{branch}'")

    try:
        # Get snapshots from all lenses
        snapshots = await get_projector_state_snapshots(world_id, branch)

        # Compute deterministic state hash
        state_hash = compute_determinism_state_hash(snapshots)

        # Output results
        result = {
            "world_id": world_id,
            "branch": branch,
            "timestamp": datetime.utcnow().isoformat(),
            "state_hash": state_hash,
            "snapshots": snapshots,
            "lens_summary": {
                "relational": {
                    "notes": len(snapshots["relational"].get("notes", [])),
                    "emos": len(snapshots["relational"].get("emos", [])),
                    "tags": len(snapshots["relational"].get("tags", [])),
                    "links": len(snapshots["relational"].get("links", [])),
                    "emo_links": len(snapshots["relational"].get("emo_links", [])),
                },
                "semantic": {
                    "embeddings": len(snapshots["semantic"].get("embeddings", [])),
                    "emo_embeddings": len(
                        snapshots["semantic"].get("emo_embeddings", [])
                    ),
                },
                "graph": {
                    "node_count": snapshots["graph"].get("node_count", 0),
                    "edge_count": snapshots["graph"].get("edge_count", 0),
                    "emo_nodes": snapshots["graph"]
                    .get("emo_graph_stats", {})
                    .get("total_nodes", 0),
                },
            },
        }

        # Save to file
        filename = f"snapshot_{world_id}_{branch}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"✅ Snapshot complete:")
        print(f"   State hash: {state_hash}")
        print(f"   Saved to: {filename}")
        print(f"   Lens summary: {result['lens_summary']}")

        # Exit with success
        return 0

    except Exception as e:
        print(f"❌ Snapshot failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
CI Script: EMO Lineage Integrity Test
Job: ci:emo:lineage-integrity

Per MNX checklist: parents/links produce correct graph edges; determinism hash stable.
Tests EMO parent relationships, lineage integrity, and graph structure consistency.
"""

import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, List

import asyncpg
import httpx


# Base EMO for lineage testing
BASE_EMO = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "lineage-test",
    "kind": "emo.created",
    "by": {
        "agent": "ci-lineage-test",
        "trace_id": "ci-lineage-base"
    },
    "payload": {
        "emo_id": "emo-base-001",
        "emo_type": "doc",
        "emo_version": 1,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "lineage-test",
        "source": {
            "kind": "user",
            "uri": "user://lineage-tester"
        },
        "mime_type": "text/markdown",
        "content": "Base document for lineage testing. This will be the root of a lineage tree.",
        "tags": ["lineage", "base", "doc"],
        "parents": [],
        "links": [],
        "schema_version": 1
    },
    "occurred_at": "2025-01-01T16:00:00Z"
}

# Derived EMO (child of base)
DERIVED_EMO = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "lineage-test",
    "kind": "emo.created",
    "by": {
        "agent": "ci-lineage-test",
        "trace_id": "ci-lineage-derived"
    },
    "payload": {
        "emo_id": "emo-derived-001",
        "emo_type": "note",
        "emo_version": 1,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "lineage-test",
        "source": {
            "kind": "agent",
            "uri": "agent://summarizer-v1"
        },
        "mime_type": "text/markdown",
        "content": "Summary derived from base document. This demonstrates DERIVED lineage relationship.",
        "tags": ["lineage", "derived", "summary"],
        "parents": [
            {
                "emo_id": "emo-base-001",
                "rel": "derived"
            }
        ],
        "links": [],
        "schema_version": 1
    },
    "occurred_at": "2025-01-01T16:05:00Z"
}

# Updated EMO (supersedes base)
SUPERSEDING_EMO = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "lineage-test",
    "kind": "emo.created",
    "by": {
        "agent": "ci-lineage-test",
        "trace_id": "ci-lineage-superseded"
    },
    "payload": {
        "emo_id": "emo-supersede-001",
        "emo_type": "doc",
        "emo_version": 1,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "lineage-test",
        "source": {
            "kind": "user",
            "uri": "user://lineage-tester"
        },
        "mime_type": "text/markdown",
        "content": "Updated version of the base document. This supersedes the original.",
        "tags": ["lineage", "supersede", "doc", "v2"],
        "parents": [
            {
                "emo_id": "emo-base-001",
                "rel": "supersedes"
            }
        ],
        "links": [
            {
                "kind": "emo",
                "ref": "emo-derived-001"
            }
        ],
        "schema_version": 1
    },
    "occurred_at": "2025-01-01T16:10:00Z"
}

# Merge EMO (merges multiple sources)
MERGE_EMO = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "lineage-test",
    "kind": "emo.created",
    "by": {
        "agent": "ci-lineage-test",
        "trace_id": "ci-lineage-merged"
    },
    "payload": {
        "emo_id": "emo-merge-001",
        "emo_type": "fact",
        "emo_version": 1,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "lineage-test",
        "source": {
            "kind": "agent",
            "uri": "agent://knowledge-merger-v1"
        },
        "mime_type": "text/markdown",
        "content": "Consolidated knowledge merged from multiple sources. Demonstrates fan-in lineage.",
        "tags": ["lineage", "merge", "consolidated"],
        "parents": [
            {
                "emo_id": "emo-derived-001",
                "rel": "merges"
            },
            {
                "emo_id": "emo-supersede-001",
                "rel": "merges"
            }
        ],
        "links": [],
        "schema_version": 1
    },
    "occurred_at": "2025-01-01T16:15:00Z"
}


async def submit_event(event: Dict[str, Any], description: str) -> Dict[str, Any]:
    """Submit event to gateway"""
    
    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8086")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"📤 Submitting {description}")
        
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-Id": f"ci-lineage-{uuid.uuid4()}"
        }
        
        response = await client.post(
            f"{gateway_url}/v1/events",
            json=event,
            headers=headers
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"{description} failed: {response.text}")
        
        result = response.json()
        print(f"   ✅ {result['event_id']}")
        return result


async def get_lineage_state(world_id: str, branch: str) -> Dict[str, Any]:
    """Get complete lineage state from database"""
    
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    )
    
    async with asyncpg.create_pool(database_url, min_size=1, max_size=2) as pool:
        async with pool.acquire() as conn:
            
            # Get all EMOs
            emos = await conn.fetch(
                """
                SELECT emo_id, emo_type, emo_version, content, tags, deleted
                FROM lens_emo.emo_current
                WHERE world_id = $1::uuid AND branch = $2
                ORDER BY emo_id
            """,
                world_id,
                branch,
            )
            
            # Get all EMO relationships
            relationships = await conn.fetch(
                """
                SELECT emo_id, rel, target_emo_id, target_uri, created_at
                FROM lens_emo.emo_links
                WHERE world_id = $1::uuid AND branch = $2
                ORDER BY emo_id, rel
            """,
                world_id,
                branch,
            )
            
            # Get graph lineage data
            lineage_data = {}
            for emo in emos:
                emo_id = str(emo["emo_id"])
                try:
                    # Get ancestors
                    ancestors = await conn.fetch(
                        "SELECT ancestor_id, relationship, depth FROM lens_emo.get_emo_lineage($1::uuid, $2, $3::uuid, 10)",
                        world_id,
                        branch,
                        emo["emo_id"]
                    )
                    
                    # Get descendants  
                    descendants = await conn.fetch(
                        "SELECT descendant_id, relationship, depth FROM lens_emo.get_emo_descendants($1::uuid, $2, $3::uuid, 10)",
                        world_id,
                        branch,
                        emo["emo_id"]
                    )
                    
                    lineage_data[emo_id] = {
                        "ancestors": [dict(a) for a in ancestors],
                        "descendants": [dict(d) for d in descendants]
                    }
                    
                except Exception as e:
                    print(f"Warning: Could not get lineage for {emo_id}: {e}")
                    lineage_data[emo_id] = {"ancestors": [], "descendants": []}
            
            return {
                "emos": [dict(emo) for emo in emos],
                "relationships": [dict(rel) for rel in relationships],
                "lineage": lineage_data
            }


def validate_lineage_integrity(state: Dict[str, Any]) -> List[str]:
    """Validate lineage integrity and return list of issues"""
    
    issues = []
    
    # Build relationship maps
    parent_map = {}  # child -> [parents]
    child_map = {}   # parent -> [children]
    
    for rel in state["relationships"]:
        if rel["target_emo_id"]:  # EMO-to-EMO relationships
            child_id = str(rel["emo_id"])
            parent_id = str(rel["target_emo_id"])
            rel_type = rel["rel"]
            
            if child_id not in parent_map:
                parent_map[child_id] = []
            parent_map[child_id].append((parent_id, rel_type))
            
            if parent_id not in child_map:
                child_map[parent_id] = []
            child_map[parent_id].append((child_id, rel_type))
    
    # Test 1: No orphan relationships (both EMOs exist)
    emo_ids = {str(emo["emo_id"]) for emo in state["emos"]}
    
    for rel in state["relationships"]:
        if rel["target_emo_id"]:
            child_id = str(rel["emo_id"])
            parent_id = str(rel["target_emo_id"])
            
            if child_id not in emo_ids:
                issues.append(f"Orphan relationship: child {child_id} not found in emos")
            if parent_id not in emo_ids:
                issues.append(f"Orphan relationship: parent {parent_id} not found in emos")
    
    # Test 2: Expected relationships exist
    expected_relationships = [
        ("emo-derived-001", "emo-base-001", "derived"),
        ("emo-supersede-001", "emo-base-001", "supersedes"),  
        ("emo-merge-001", "emo-derived-001", "merges"),
        ("emo-merge-001", "emo-supersede-001", "merges"),
    ]
    
    for child_id, parent_id, expected_rel in expected_relationships:
        found = False
        if child_id in parent_map:
            for parent, rel_type in parent_map[child_id]:
                if parent == parent_id and rel_type == expected_rel:
                    found = True
                    break
        
        if not found:
            issues.append(f"Missing expected relationship: {child_id} -{expected_rel}-> {parent_id}")
    
    # Test 3: Fan-in relationships (merge EMO has multiple parents)
    merge_parents = parent_map.get("emo-merge-001", [])
    if len(merge_parents) < 2:
        issues.append(f"Merge EMO should have multiple parents, found: {len(merge_parents)}")
    
    # Test 4: Graph traversal consistency
    for emo_id, lineage in state["lineage"].items():
        # Check that direct parents are reachable via graph traversal
        direct_parents = [p[0] for p in parent_map.get(emo_id, [])]
        graph_ancestors = [str(a["ancestor_id"]) for a in lineage["ancestors"] if a["depth"] == 1]
        
        for parent in direct_parents:
            if parent not in graph_ancestors:
                issues.append(f"Graph traversal inconsistency: {parent} is direct parent of {emo_id} but not in graph ancestors")
    
    return issues


def compute_lineage_hash(state: Dict[str, Any]) -> str:
    """Compute deterministic hash of lineage state"""
    
    # Create canonical representation
    canonical = {
        "emo_count": len(state["emos"]),
        "relationship_count": len(state["relationships"]),
        "emo_ids": sorted([str(emo["emo_id"]) for emo in state["emos"]]),
        "relationships": sorted([
            {
                "child": str(rel["emo_id"]),
                "parent": str(rel["target_emo_id"]) if rel["target_emo_id"] else rel["target_uri"],
                "relation": rel["rel"]
            }
            for rel in state["relationships"]
        ], key=lambda x: (x["child"], x["parent"], x["relation"]))
    }
    
    canonical_json = json.dumps(canonical, sort_keys=True)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


async def test_lineage_integrity():
    """Test EMO lineage integrity and graph consistency"""
    
    print("🧪 Testing EMO Lineage Integrity")
    
    world_id = BASE_EMO["world_id"]
    branch = BASE_EMO["branch"]
    
    # Submit all lineage events in order
    events = [
        (BASE_EMO, "base EMO"),
        (DERIVED_EMO, "derived EMO"),
        (SUPERSEDING_EMO, "superseding EMO"),
        (MERGE_EMO, "merge EMO")
    ]
    
    print("\n1️⃣ Submitting lineage events:")
    for event, description in events:
        await submit_event(event, description)
    
    # Wait for projector processing
    print("\n⏳ Waiting for projector processing...")
    await asyncio.sleep(4.0)
    
    # Get lineage state
    print("\n2️⃣ Analyzing lineage state:")
    state = await get_lineage_state(world_id, branch)
    
    print(f"   EMOs: {len(state['emos'])}")
    print(f"   Relationships: {len(state['relationships'])}")
    print(f"   Lineage entries: {len(state['lineage'])}")
    
    # Validate integrity
    print("\n3️⃣ Validating lineage integrity:")
    issues = validate_lineage_integrity(state)
    
    if issues:
        print("❌ Lineage integrity issues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    
    print("✅ Lineage integrity validated successfully")
    
    # Test deterministic hash
    print("\n4️⃣ Testing deterministic lineage hash:")
    lineage_hash_1 = compute_lineage_hash(state)
    
    # Get state again and compute hash  
    await asyncio.sleep(0.5)
    state_2 = await get_lineage_state(world_id, branch)
    lineage_hash_2 = compute_lineage_hash(state_2)
    
    print(f"   Hash 1: {lineage_hash_1}")
    print(f"   Hash 2: {lineage_hash_2}")
    
    if lineage_hash_1 != lineage_hash_2:
        print("❌ Lineage hash is not deterministic")
        return False
    
    print("✅ Lineage hash is deterministic and stable")
    
    # Test specific lineage relationships
    print("\n5️⃣ Testing specific lineage patterns:")
    
    # Check merge fan-in
    merge_lineage = state["lineage"].get("emo-merge-001", {})
    merge_ancestors = merge_lineage.get("ancestors", [])
    
    print(f"   Merge EMO ancestors: {len(merge_ancestors)}")
    for ancestor in merge_ancestors:
        print(f"     - {ancestor['ancestor_id']} (depth: {ancestor['depth']})")
    
    # Verify merge has multiple depth-1 ancestors (direct parents)
    direct_parents = [a for a in merge_ancestors if a["depth"] == 1]
    if len(direct_parents) < 2:
        print(f"❌ Merge EMO should have multiple direct parents, found {len(direct_parents)}")
        return False
    
    print(f"✅ Merge EMO has correct fan-in: {len(direct_parents)} direct parents")
    
    return True


async def main():
    """Main CI validation function"""
    
    print("🔍 Starting CI: EMO Lineage Integrity Test")
    
    try:
        success = await test_lineage_integrity()
        
        if success:
            print("\n✅ CI: EMO Lineage Integrity Test - PASSED")
            print("   All parent/child relationships are correctly established")
            print("   Graph traversal produces consistent results")
            print("   Fan-in relationships work correctly")
            print("   Lineage hash is deterministic and stable")
            return 0
        else:
            print("\n❌ CI: EMO Lineage Integrity Test - FAILED")
            return 1
            
    except Exception as e:
        print(f"\n❌ CI test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

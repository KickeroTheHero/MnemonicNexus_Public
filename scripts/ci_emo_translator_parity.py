#!/usr/bin/env python3
"""
CI Script: EMO Translator Parity Test
Job: ci:emo:translator-parity

Per MNX checklist: shim emits emo.*; direct vs translated EMO fixtures match.
Tests that the memory-to-EMO translator produces identical results to direct EMO events.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any

import asyncpg
import httpx


# Memory event that should translate to EMO
MEMORY_EVENT = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "translator-test",
    "kind": "memory.item.upserted",
    "by": {
        "agent": "ci-translator-test",
        "trace_id": "ci-translator-parity"
    },
    "payload": {
        "id": "memory-item-001",  # Memory ID that will be deterministically mapped to EMO ID
        "title": "Test Memory Item for Translation",
        "body": "This memory item should be translated to an EMO create event with deterministic ID mapping.",
        "tags": ["test", "translator", "parity"],
        "created_at": "2025-01-01T15:00:00Z"
    },
    "occurred_at": "2025-01-01T15:00:00Z"
}

# Corresponding direct EMO event (what the translator should produce)
def get_expected_emo_event() -> Dict[str, Any]:
    """Get the EMO event that the translator should produce"""
    
    # Derive EMO ID using same logic as translator
    import uuid
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
    expected_emo_id = uuid.uuid5(namespace, f"memory:memory-item-001")
    
    return {
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "translator-test",
        "kind": "emo.created",
        "by": {
            "agent": "ci-direct-emo-test",
            "trace_id": "ci-translator-parity-direct"
        },
        "payload": {
            "emo_id": str(expected_emo_id),
            "emo_type": "note",  # Inferred type
            "emo_version": 1,
            "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
            "world_id": "550e8400-e29b-41d4-a716-446655440001",
            "branch": "translator-test",
            "source": {
                "kind": "user"  # Inferred from agent
            },
            "mime_type": "text/markdown",
            "content": "Test Memory Item for Translation This memory item should be translated to an EMO create event with deterministic ID mapping.",  # title + body
            "tags": ["test", "translator", "parity"],
            "parents": [],
            "links": [],
            "schema_version": 1
        },
        "occurred_at": "2025-01-01T15:00:00Z"
    }


async def submit_event(event: Dict[str, Any], description: str) -> Dict[str, Any]:
    """Submit event to gateway and return response"""
    
    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8086")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"📤 Submitting {description}")
        print(f"   Event: {event['kind']}")
        
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-Id": f"ci-translator-{uuid.uuid4()}"
        }
        
        response = await client.post(
            f"{gateway_url}/v1/events",
            json=event,
            headers=headers
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code not in (200, 201):
            print(f"   ❌ Failed: {response.text}")
            raise Exception(f"{description} failed with {response.status_code}: {response.text}")
        
        result = response.json()
        print(f"   ✅ Success: {result['event_id']}")
        return result


async def wait_for_projectors(delay: float = 2.0):
    """Wait for projectors to process events"""
    print(f"⏳ Waiting {delay}s for projector processing...")
    await asyncio.sleep(delay)


async def get_emo_state(world_id: str, branch: str, emo_id: str) -> Dict[str, Any]:
    """Get EMO state from all lenses"""
    
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    )
    
    async with asyncpg.create_pool(database_url, min_size=1, max_size=2) as pool:
        async with pool.acquire() as conn:
            
            # Get EMO from relational lens
            emo_current = await conn.fetchrow(
                """
                SELECT emo_id, emo_type, emo_version, content, tags, source_kind, mime_type, deleted
                FROM lens_emo.emo_current
                WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $3
            """,
                emo_id,
                world_id,
                branch,
            )
            
            # Get EMO embedding
            emo_embedding = await conn.fetchrow(
                """
                SELECT emo_id, emo_version, model_id, embed_dim
                FROM lens_emo.emo_embeddings
                WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $3
                LIMIT 1
            """,
                emo_id,
                world_id,
                branch,
            )
            
            # Get EMO links
            emo_links = await conn.fetch(
                """
                SELECT rel, target_emo_id, target_uri
                FROM lens_emo.emo_links
                WHERE emo_id = $1::uuid AND world_id = $2::uuid AND branch = $3
                ORDER BY rel
            """,
                emo_id,
                world_id,
                branch,
            )
            
            return {
                "current": dict(emo_current) if emo_current else None,
                "embedding": dict(emo_embedding) if emo_embedding else None,
                "links": [dict(link) for link in emo_links],
            }


def normalize_emo_state_for_comparison(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize EMO state for comparison, ignoring timestamps and agent-specific fields"""
    
    if not state or not state["current"]:
        return {}
    
    normalized = {
        "emo_id": str(state["current"]["emo_id"]),
        "emo_type": state["current"]["emo_type"],
        "emo_version": state["current"]["emo_version"],
        "content": state["current"]["content"],
        "tags": sorted(state["current"]["tags"] or []),  # Normalize tag order
        "source_kind": state["current"]["source_kind"],
        "mime_type": state["current"]["mime_type"],
        "deleted": state["current"]["deleted"],
        "has_embedding": state["embedding"] is not None,
        "link_count": len(state["links"]),
        "links": [
            {
                "rel": link["rel"],
                "target_emo_id": str(link["target_emo_id"]) if link["target_emo_id"] else None,
                "target_uri": link["target_uri"]
            }
            for link in sorted(state["links"], key=lambda x: x["rel"])
        ]
    }
    
    return normalized


async def test_translator_parity():
    """Test that memory-to-EMO translation produces equivalent results to direct EMO events"""
    
    print("🧪 Testing EMO Translator Parity")
    
    # Get expected EMO ID
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    expected_emo_id = str(uuid.uuid5(namespace, f"memory:memory-item-001"))
    print(f"   Expected EMO ID: {expected_emo_id}")
    
    world_id = MEMORY_EVENT["world_id"]
    branch = MEMORY_EVENT["branch"]
    
    # Test 1: Submit memory event (should be translated to EMO)
    print("\n1️⃣ Testing memory event translation:")
    
    try:
        memory_result = await submit_event(MEMORY_EVENT, "memory event for translation")
        await wait_for_projectors(3.0)  # Extra time for translator processing
        
        # Get translated EMO state
        translated_state = await get_emo_state(world_id, branch, expected_emo_id)
        print(f"   Translated EMO found: {translated_state['current'] is not None}")
        
        if not translated_state["current"]:
            print("❌ Memory event was not translated to EMO")
            return False
            
    except Exception as e:
        print(f"❌ Memory event translation failed: {e}")
        return False
    
    # Test 2: Submit equivalent direct EMO event (in separate branch for comparison)
    print("\n2️⃣ Testing direct EMO event:")
    
    direct_emo_event = get_expected_emo_event()
    direct_emo_event["branch"] = "translator-test-direct"  # Different branch
    direct_emo_event["payload"]["branch"] = "translator-test-direct"
    
    try:
        direct_result = await submit_event(direct_emo_event, "direct EMO event")
        await wait_for_projectors()
        
        # Get direct EMO state
        direct_state = await get_emo_state(world_id, "translator-test-direct", expected_emo_id)
        print(f"   Direct EMO found: {direct_state['current'] is not None}")
        
        if not direct_state["current"]:
            print("❌ Direct EMO event was not processed")
            return False
            
    except Exception as e:
        print(f"❌ Direct EMO event failed: {e}")
        return False
    
    # Test 3: Compare states for equivalence
    print("\n3️⃣ Comparing translated vs direct EMO states:")
    
    normalized_translated = normalize_emo_state_for_comparison(translated_state)
    normalized_direct = normalize_emo_state_for_comparison(direct_state)
    
    print("   Translated EMO:")
    for key, value in normalized_translated.items():
        print(f"     {key}: {value}")
    
    print("   Direct EMO:")  
    for key, value in normalized_direct.items():
        print(f"     {key}: {value}")
    
    # Compare key fields
    comparison_fields = [
        "emo_id", "emo_type", "emo_version", "content", 
        "tags", "source_kind", "mime_type", "deleted",
        "has_embedding", "link_count"
    ]
    
    differences = []
    for field in comparison_fields:
        if normalized_translated.get(field) != normalized_direct.get(field):
            differences.append(f"{field}: {normalized_translated.get(field)} != {normalized_direct.get(field)}")
    
    if differences:
        print("❌ Translated and direct EMOs differ:")
        for diff in differences:
            print(f"     {diff}")
        return False
    
    print("✅ Translated and direct EMOs are equivalent!")
    
    # Test 4: Verify deterministic EMO ID mapping  
    print("\n4️⃣ Verifying deterministic EMO ID mapping:")
    
    if normalized_translated["emo_id"] != expected_emo_id:
        print(f"❌ EMO ID mismatch. Expected {expected_emo_id}, got {normalized_translated['emo_id']}")
        return False
    
    print(f"✅ EMO ID mapping is deterministic: {expected_emo_id}")
    
    return True


async def main():
    """Main CI validation function"""
    
    print("🔍 Starting CI: EMO Translator Parity Test")
    
    try:
        success = await test_translator_parity()
        
        if success:
            print("\n✅ CI: EMO Translator Parity Test - PASSED")
            print("   Memory-to-EMO translation produces equivalent results to direct EMO events")
            print("   EMO ID mapping is deterministic and consistent")
            return 0
        else:
            print("\n❌ CI: EMO Translator Parity Test - FAILED")
            return 1
            
    except Exception as e:
        print(f"\n❌ CI test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

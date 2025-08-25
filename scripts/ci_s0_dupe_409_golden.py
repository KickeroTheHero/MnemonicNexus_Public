#!/usr/bin/env python3
"""
CI Script: Duplicate 409 Golden Test
Job: ci:s0:dupe-409-golden

Per MNX checklist: golden envelopes; assert 1 row + 409.
Tests idempotency by submitting the same envelope twice and expecting 409 Conflict.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

import httpx


# Golden envelope for idempotency testing
GOLDEN_ENVELOPE = {
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "branch": "test-branch",
    "kind": "emo.created",
    "by": {"agent": "ci-test-agent", "trace_id": "ci-trace-409-test"},
    "payload": {
        "emo_id": "123e4567-e89b-12d3-a456-426614174409",  # Specific ID for 409 test
        "emo_type": "fact",
        "emo_version": 1,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
        "world_id": "550e8400-e29b-41d4-a716-446655440001",
        "branch": "test-branch",
        "source": {"kind": "user", "uri": "ci://409-test"},
        "mime_type": "text/markdown",
        "content": "Golden envelope for 409 idempotency testing. This content should appear only once.",
        "tags": ["ci", "golden", "409-test"],
        "parents": [],
        "links": [],
        "vector_meta": {
            "model_id": "test-model",
            "embed_dim": 384,
            "model_version": "test-v1",
            "template_id": "golden",
        },
        "schema_version": 1,
    },
    "occurred_at": "2025-01-01T12:00:00Z",
}

# Fixed idempotency key for deterministic testing
IDEMPOTENCY_KEY = "golden-409-test-key-deterministic"


async def test_duplicate_409():
    """Test that duplicate envelope submission returns 409 Conflict"""

    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8086")

    async with httpx.AsyncClient(timeout=30.0) as client:

        print("🧪 Testing duplicate envelope 409 behavior")
        print(f"   Gateway URL: {gateway_url}")
        print(f"   EMO ID: {GOLDEN_ENVELOPE['payload']['emo_id']}")
        print(f"   Idempotency Key: {IDEMPOTENCY_KEY}")

        # First submission - should succeed (201 Created)
        print("\n📤 First submission (expecting 201 Created):")

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": IDEMPOTENCY_KEY,
            "X-Correlation-Id": f"ci-409-test-{uuid.uuid4()}",
        }

        response1 = await client.post(
            f"{gateway_url}/v1/events", json=GOLDEN_ENVELOPE, headers=headers
        )

        print(f"   Status: {response1.status_code}")
        print(f"   Response: {response1.text[:200]}...")

        if response1.status_code != 201:
            print(
                f"❌ First submission failed. Expected 201, got {response1.status_code}"
            )
            return False

        first_response = response1.json()
        event_id_1 = first_response["event_id"]
        global_seq_1 = first_response["global_seq"]

        print(f"✅ First submission succeeded:")
        print(f"   Event ID: {event_id_1}")
        print(f"   Global Seq: {global_seq_1}")

        # Second submission - should return 409 Conflict
        print("\n📤 Second submission (expecting 409 Conflict):")

        # Use same idempotency key and envelope
        response2 = await client.post(
            f"{gateway_url}/v1/events", json=GOLDEN_ENVELOPE, headers=headers
        )

        print(f"   Status: {response2.status_code}")
        print(f"   Response: {response2.text[:200]}...")

        if response2.status_code != 409:
            print(
                f"❌ Second submission should return 409, got {response2.status_code}"
            )
            return False

        second_response = response2.json()
        print(f"✅ Second submission correctly returned 409:")
        print(f"   Error code: {second_response.get('code', 'N/A')}")
        print(f"   Message: {second_response.get('message', 'N/A')}")

        # Verify only one row exists in database
        print("\n🔍 Verifying only one event exists in database:")

        database_url = os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
        )

        import asyncpg

        async with asyncpg.create_pool(database_url, min_size=1, max_size=2) as pool:
            async with pool.acquire() as conn:

                # Count events with this idempotency key
                event_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM event_core.event_log
                    WHERE idempotency_key = $1 
                    AND world_id = $2::uuid
                    AND branch = $3
                """,
                    IDEMPOTENCY_KEY,
                    GOLDEN_ENVELOPE["world_id"],
                    GOLDEN_ENVELOPE["branch"],
                )

                print(f"   Events with idempotency key: {event_count}")

                if event_count != 1:
                    print(f"❌ Expected exactly 1 event, found {event_count}")
                    return False

                # Verify the event details
                event = await conn.fetchrow(
                    """
                    SELECT event_id, kind, envelope->>'emo_id' as emo_id
                    FROM event_core.event_log
                    WHERE idempotency_key = $1 
                    AND world_id = $2::uuid
                    AND branch = $3
                """,
                    IDEMPOTENCY_KEY,
                    GOLDEN_ENVELOPE["world_id"],
                    GOLDEN_ENVELOPE["branch"],
                )

                print(f"✅ Verified single event in database:")
                print(f"   Event ID: {event['event_id']}")
                print(f"   Kind: {event['kind']}")
                print(f"   EMO ID: {event['emo_id']}")

                # Verify it's the same event from first submission
                if str(event["event_id"]) != event_id_1:
                    print(
                        f"❌ Event ID mismatch. Expected {event_id_1}, got {event['event_id']}"
                    )
                    return False

        print("\n✅ All 409 idempotency tests passed!")
        return True


async def main():
    """Main CI validation function"""

    print("🔍 Starting CI: S0 Duplicate 409 Golden Test")

    try:
        success = await test_duplicate_409()

        if success:
            print("\n✅ CI: S0 Duplicate 409 Golden Test - PASSED")
            return 0
        else:
            print("\n❌ CI: S0 Duplicate 409 Golden Test - FAILED")
            return 1

    except Exception as e:
        print(f"\n❌ CI test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

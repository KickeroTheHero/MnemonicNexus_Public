#!/usr/bin/env python3
"""
Optimized Performance Test - Push for 1000+ events/sec
"""

import asyncio
import aiohttp
import json
import time
import uuid
from typing import Tuple


async def create_test_event(event_number: int) -> dict:
    """Create minimal test event for performance"""
    return {
        "world_id": "550e8400-e29b-41d4-a716-446655440001", 
        "branch": "main",
        "kind": "note.created",
        "event_id": str(uuid.uuid4()),
        "correlation_id": f"perf-{event_number}-{int(time.time()*1000000)}",
        "occurred_at": "2024-01-15T14:30:00.000Z",
        "by": {"agent": "perf:test", "context": "High throughput test"},
        "payload": {
            "entity_id": str(uuid.uuid4()),
            "entity_type": "note",
            "title": f"Perf Test {event_number}",
            "content": f"Performance test event {event_number}",
            "tags": ["perf"],
            "idempotency_key": f"perf-{event_number}-{int(time.time()*1000000)}",
            "schema_version": 1
        }
    }


async def send_event_batch(session: aiohttp.ClientSession, events: list, semaphore: asyncio.Semaphore) -> Tuple[int, int]:
    """Send a batch of events"""
    successes = 0
    errors = 0
    
    tasks = []
    for event in events:
        async def send_single():
            async with semaphore:
                try:
                    async with session.post(
                        "http://localhost:8081/v1/events",
                        json=event,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        return 200 <= response.status < 300
                except:
                    return False
        
        tasks.append(asyncio.create_task(send_single()))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception) or not result:
            errors += 1
        else:
            successes += 1
    
    return successes, errors


async def high_throughput_test():
    """Optimized test for maximum throughput"""
    print("🚀 High Throughput Test - Target: 1000+ events/sec")
    
    # Aggressive settings
    total_events = 2000
    batch_size = 50
    max_concurrent = 300
    
    # Create events
    print(f"📝 Generating {total_events} test events...")
    events = [await create_test_event(i) for i in range(total_events)]
    
    # Create batches
    batches = [events[i:i+batch_size] for i in range(0, len(events), batch_size)]
    
    # Optimized connector settings
    connector = aiohttp.TCPConnector(
        limit=max_concurrent + 50,
        limit_per_host=max_concurrent + 50,
        keepalive_timeout=60,
        enable_cleanup_closed=True
    )
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=10, connect=2)
    ) as session:
        print(f"⚡ Starting high-throughput test...")
        print(f"   Events: {total_events}, Batches: {len(batches)}, Max concurrent: {max_concurrent}")
        
        start_time = time.time()
        
        # Send all batches concurrently
        batch_tasks = [send_event_batch(session, batch, semaphore) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks)
        
        end_time = time.time()
        duration = end_time - start_time
    
    # Calculate results
    total_successes = sum(r[0] for r in batch_results)
    total_errors = sum(r[1] for r in batch_results)
    throughput = total_events / duration
    
    print(f"\n🎯 High Throughput Results:")
    print("=" * 40)
    print(f"Total Events:   {total_events:,}")
    print(f"Duration:       {duration:.2f}s")
    print(f"Successes:      {total_successes:,}")
    print(f"Errors:         {total_errors:,}")
    print(f"Success Rate:   {total_successes/total_events*100:.1f}%")
    print(f"Throughput:     {throughput:.1f} events/sec")
    
    if throughput >= 1000:
        print("🎉 SUCCESS: 1000+ events/sec ACHIEVED!")
        return True
    else:
        print(f"⚠️  Need {1000-throughput:.1f} more events/sec")
        return False


if __name__ == "__main__":
    asyncio.run(high_throughput_test())

#!/usr/bin/env python3
"""
MNX Performance Testing Script
Tests sustained event throughput against the gateway
Target: 1000+ events/sec
"""

import asyncio
import aiohttp
import json
import time
import uuid
from dataclasses import dataclass
from typing import List, Tuple
import statistics


@dataclass
class PerformanceResult:
    total_events: int
    total_duration: float
    events_per_second: float
    success_count: int
    error_count: int
    avg_latency: float
    p95_latency: float
    p99_latency: float


async def create_test_event(event_number: int) -> dict:
    """Create a test event with unique IDs"""
    return {
        "world_id": "550e8400-e29b-41d4-a716-446655440001", 
        "branch": "main",
        "kind": "note.created",
        "event_id": str(uuid.uuid4()),
        "correlation_id": f"perf-test-{event_number}-{uuid.uuid4()}",
        "occurred_at": "2024-01-15T14:30:00.000Z",
        "by": {
            "agent": "test:performance.validator",
            "context": f"Performance test event {event_number}"
        },
        "payload": {
            "entity_id": str(uuid.uuid4()),
            "entity_type": "note",
            "title": f"Performance Test Note {event_number}",
            "content": f"This is test note {event_number} for performance validation",
            "tags": ["performance", "test"],
            "idempotency_key": f"perf-{event_number}-{uuid.uuid4()}",
            "schema_version": 1
        }
    }


async def send_event(session: aiohttp.ClientSession, event: dict, semaphore: asyncio.Semaphore) -> Tuple[bool, float]:
    """Send a single event and return (success, latency)"""
    async with semaphore:
        start_time = time.time()
        try:
            async with session.post(
                "http://localhost:8081/v1/events",
                json=event,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                latency = time.time() - start_time
                success = 200 <= response.status < 300
                if not success:
                    text = await response.text()
                    print(f"❌ Error {response.status}: {text[:100]}")
                return success, latency
        except Exception as e:
            latency = time.time() - start_time
            print(f"❌ Exception: {e}")
            return False, latency


async def run_performance_test(
    total_events: int = 5000,
    max_concurrent: int = 100,
    target_rps: int = 1000
) -> PerformanceResult:
    """Run performance test with specified parameters"""
    
    print(f"🚀 Starting performance test:")
    print(f"   Target: {total_events} events at {target_rps} RPS")
    print(f"   Max concurrent: {max_concurrent}")
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create events
    print("📝 Generating test events...")
    events = [await create_test_event(i) for i in range(total_events)]
    
    # Create HTTP session
    connector = aiohttp.TCPConnector(limit=max_concurrent + 10, limit_per_host=max_concurrent + 10)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        print("⏱️  Starting load test...")
        start_time = time.time()
        
        # Send events with rate limiting
        tasks = []
        for i, event in enumerate(events):
            # Rate limiting: delay between batches
            if i > 0 and i % max_concurrent == 0:
                await asyncio.sleep(max_concurrent / target_rps)
            
            task = asyncio.create_task(send_event(session, event, semaphore))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
    
    # Process results
    successes = []
    latencies = []
    error_count = 0
    
    for result in results:
        if isinstance(result, Exception):
            error_count += 1
        else:
            success, latency = result
            latencies.append(latency)
            if success:
                successes.append(True)
            else:
                error_count += 1
    
    success_count = len(successes)
    events_per_second = total_events / total_duration
    
    # Calculate latency percentiles
    if latencies:
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
    else:
        avg_latency = p95_latency = p99_latency = 0.0
    
    return PerformanceResult(
        total_events=total_events,
        total_duration=total_duration,
        events_per_second=events_per_second,
        success_count=success_count,
        error_count=error_count,
        avg_latency=avg_latency,
        p95_latency=p95_latency,
        p99_latency=p99_latency
    )


def print_results(result: PerformanceResult):
    """Print formatted performance results"""
    print("\n📊 Performance Test Results:")
    print("=" * 50)
    print(f"Total Events:     {result.total_events:,}")
    print(f"Duration:         {result.total_duration:.2f}s")
    print(f"Success Rate:     {result.success_count}/{result.total_events} ({result.success_count/result.total_events*100:.1f}%)")
    print(f"Errors:           {result.error_count}")
    print(f"Throughput:       {result.events_per_second:.1f} events/sec")
    print(f"Avg Latency:      {result.avg_latency*1000:.1f}ms")
    print(f"P95 Latency:      {result.p95_latency*1000:.1f}ms") 
    print(f"P99 Latency:      {result.p99_latency*1000:.1f}ms")
    
    if result.events_per_second >= 1000:
        print("✅ TARGET ACHIEVED: 1000+ events/sec!")
    else:
        print(f"⚠️  Target not met. Need {1000 - result.events_per_second:.1f} more events/sec")


async def main():
    """Main performance test runner"""
    try:
        # Check if gateway is responding
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8081/health") as response:
                if response.status != 200:
                    print("❌ Gateway not healthy. Start services first.")
                    return
        
        print("✅ Gateway is healthy. Starting performance test...")
        
        # Run graduated performance tests
        test_configs = [
            (100, 50, 200),    # Warm-up: 100 events, 50 concurrent, 200 RPS target
            (1000, 100, 500),  # Ramp-up: 1k events, 100 concurrent, 500 RPS target  
            (5000, 200, 1000), # Main test: 5k events, 200 concurrent, 1000 RPS target
        ]
        
        for i, (events, concurrent, target_rps) in enumerate(test_configs, 1):
            print(f"\n🔥 Test {i}/3: {events} events @ {target_rps} RPS target")
            result = await run_performance_test(events, concurrent, target_rps)
            print_results(result)
            
            if result.error_count > events * 0.1:  # More than 10% errors
                print(f"⚠️  High error rate ({result.error_count}/{events}). Check system health.")
                break
            
            if i < len(test_configs):
                print("⏸️  Cooling down for 5 seconds...")
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

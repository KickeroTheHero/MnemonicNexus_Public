"""
Performance smoke tests
Basic performance validation - not exhaustive load testing
"""

import json
import os
import pytest
import requests
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8081")

@pytest.mark.performance
class TestPerformanceSmoke:
    """Basic performance smoke tests"""
    
    def create_test_envelope(self, sequence: int = 0) -> Dict[str, Any]:
        """Create a test envelope for performance testing"""
        return {
            "world_id": str(uuid.uuid4()),
            "branch": "main",
            "kind": "test.performance",
            "payload": {
                "sequence": sequence,
                "content": f"Performance test event {sequence}",
                "timestamp": time.time()
            },
            "by": {"agent": "performance-test"}
        }
    
    @pytest.mark.integration
    def test_single_event_latency(self):
        """Test latency of single event submission"""
        try:
            envelope = self.create_test_envelope()
            headers = {"Content-Type": "application/json"}
            
            # Measure latency
            start_time = time.time()
            
            response = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope,
                headers=headers,
                timeout=30
            )
            
            end_time = time.time()
            latency = end_time - start_time
            
            if response.status_code == 401:
                pytest.skip("Authentication required")
            
            assert response.status_code == 201
            
            # Latency should be reasonable for smoke test
            assert latency < 5.0, f"Single event latency too high: {latency:.3f}s"
            
            print(f"Single event latency: {latency:.3f}s")
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    @pytest.mark.integration
    def test_health_check_latency(self):
        """Test health check endpoint latency"""
        try:
            # Measure health check latency
            start_time = time.time()
            
            response = requests.get(f"{GATEWAY_URL}/health", timeout=10)
            
            end_time = time.time()
            latency = end_time - start_time
            
            assert response.status_code in [200, 503]
            
            # Health check should be fast
            assert latency < 2.0, f"Health check latency too high: {latency:.3f}s"
            
            print(f"Health check latency: {latency:.3f}s")
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    @pytest.mark.integration
    def test_concurrent_events_smoke(self):
        """Test concurrent event submission (smoke test level)"""
        try:
            num_events = 10  # Small number for smoke test
            max_workers = 3   # Limited concurrency
            
            def submit_event(sequence: int) -> Dict[str, Any]:
                """Submit a single event"""
                envelope = self.create_test_envelope(sequence)
                headers = {"Content-Type": "application/json"}
                
                start_time = time.time()
                
                response = requests.post(
                    f"{GATEWAY_URL}/v1/events",
                    json=envelope,
                    headers=headers,
                    timeout=30
                )
                
                end_time = time.time()
                
                return {
                    "sequence": sequence,
                    "status_code": response.status_code,
                    "latency": end_time - start_time,
                    "response": response.json() if response.status_code in [200, 201] else None
                }
            
            # Submit events concurrently
            start_time = time.time()
            results = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_seq = {
                    executor.submit(submit_event, i): i 
                    for i in range(num_events)
                }
                
                for future in as_completed(future_to_seq):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"Event submission failed: {e}")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Check results
            successful_events = [r for r in results if r["status_code"] == 201]
            auth_required = [r for r in results if r["status_code"] == 401]
            
            if len(auth_required) == len(results):
                pytest.skip("Authentication required for all requests")
            
            # Should have some successful events
            assert len(successful_events) > 0, "No events were successful"
            
            # Calculate throughput
            throughput = len(successful_events) / total_time
            
            # Average latency
            latencies = [r["latency"] for r in successful_events]
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"Concurrent smoke test results:")
            print(f"  Events: {len(successful_events)}/{num_events}")
            print(f"  Total time: {total_time:.3f}s")
            print(f"  Throughput: {throughput:.2f} events/sec")
            print(f"  Avg latency: {avg_latency:.3f}s")
            print(f"  Max latency: {max_latency:.3f}s")
            
            # Smoke test assertions (not performance targets)
            assert throughput > 1.0, f"Throughput too low: {throughput:.2f} events/sec"
            assert avg_latency < 10.0, f"Average latency too high: {avg_latency:.3f}s"
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    @pytest.mark.integration  
    def test_metrics_endpoint_performance(self):
        """Test metrics endpoint performance"""
        try:
            # Measure metrics endpoint latency
            start_time = time.time()
            
            response = requests.get(f"{GATEWAY_URL}/metrics", timeout=10)
            
            end_time = time.time()
            latency = end_time - start_time
            
            assert response.status_code == 200
            
            # Metrics should be fast
            assert latency < 3.0, f"Metrics latency too high: {latency:.3f}s"
            
            # Should return some content
            content_length = len(response.text)
            assert content_length > 0, "Metrics endpoint returned no content"
            
            print(f"Metrics endpoint latency: {latency:.3f}s")
            print(f"Metrics content length: {content_length} bytes")
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Metrics endpoint not available: {e}")


@pytest.mark.performance
class TestResourceUsage:
    """Basic resource usage monitoring"""
    
    @pytest.mark.integration
    def test_memory_stability_smoke(self):
        """Basic memory stability test"""
        try:
            # Submit a few events and check we don't get obvious memory errors
            for i in range(5):
                envelope = {
                    "world_id": str(uuid.uuid4()),
                    "branch": "main",
                    "kind": "test.memory",
                    "payload": {"sequence": i, "data": "x" * 1000},  # 1KB payload
                    "by": {"agent": "memory-test"}
                }
                
                response = requests.post(
                    f"{GATEWAY_URL}/v1/events",
                    json=envelope,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 401:
                    pytest.skip("Authentication required")
                
                assert response.status_code == 201
                
                # Small delay between requests
                time.sleep(0.1)
            
            # Final health check
            health_response = requests.get(f"{GATEWAY_URL}/health", timeout=10)
            assert health_response.status_code in [200, 503]
            
            print("Memory stability smoke test passed")
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])

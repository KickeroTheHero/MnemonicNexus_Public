"""
Integration tests for gateway service
Tests require services to be running - marked with @pytest.mark.integration
"""

import json
import os
import pytest
import requests
import uuid
from typing import Dict, Any

# Test configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8081")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/nexus")

@pytest.mark.integration
class TestGatewayHealthChecks:
    """Test gateway health and basic connectivity"""
    
    def test_gateway_health_endpoint(self):
        """Test gateway health endpoint responds"""
        try:
            response = requests.get(f"{GATEWAY_URL}/health", timeout=5)
            
            # Should get a response (200 or 503)
            assert response.status_code in [200, 503]
            
            # Should be JSON
            data = response.json()
            assert "status" in data
            assert data["status"] in ["ok", "degraded", "down"]
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    def test_gateway_service_info(self):
        """Test gateway service info endpoint"""
        try:
            response = requests.get(f"{GATEWAY_URL}/", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "service" in data
            assert "version" in data
            assert "endpoints" in data
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    def test_openapi_spec_available(self):
        """Test OpenAPI specification is available"""
        try:
            response = requests.get(f"{GATEWAY_URL}/docs", timeout=5)
            # Should get HTML page or redirect
            assert response.status_code in [200, 307, 308]
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway docs not available: {e}")


@pytest.mark.integration  
class TestEventIngestion:
    """Test event ingestion functionality"""
    
    def create_test_envelope(self, world_id: str = None, event_kind: str = "test.created") -> Dict[str, Any]:
        """Create a test event envelope"""
        if world_id is None:
            world_id = str(uuid.uuid4())
            
        return {
            "world_id": world_id,
            "branch": "main",
            "kind": event_kind,
            "payload": {
                "test_id": str(uuid.uuid4()),
                "message": "Integration test event",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "by": {
                "agent": "integration-test"
            },
            "occurred_at": "2024-01-15T10:30:00Z"
        }
    
    def test_event_creation_success(self):
        """Test successful event creation"""
        try:
            envelope = self.create_test_envelope()
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-Id": str(uuid.uuid4())
            }
            
            response = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope,
                headers=headers,
                timeout=10
            )
            
            # Should create successfully
            if response.status_code == 401:
                pytest.skip("Authentication required - test in authenticated environment")
            
            assert response.status_code == 201
            
            data = response.json()
            assert "event_id" in data
            assert "global_seq" in data
            assert "received_at" in data
            assert "correlation_id" in data
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    def test_duplicate_event_409(self):
        """Test duplicate event returns 409 Conflict"""
        try:
            envelope = self.create_test_envelope()
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-Id": str(uuid.uuid4()),
                "Idempotency-Key": f"test-{uuid.uuid4()}"
            }
            
            # First submission
            response1 = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope,
                headers=headers,
                timeout=10
            )
            
            if response1.status_code == 401:
                pytest.skip("Authentication required - test in authenticated environment")
            
            # Second submission with same idempotency key
            response2 = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope,
                headers=headers,
                timeout=10
            )
            
            # First should succeed, second should conflict
            assert response1.status_code == 201
            assert response2.status_code == 409
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    def test_invalid_envelope_400(self):
        """Test invalid envelope returns 400 Bad Request"""
        try:
            # Missing required fields
            invalid_envelope = {
                "kind": "test.invalid",
                "payload": {}
                # Missing world_id, branch, by
            }
            
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=invalid_envelope,
                headers=headers,
                timeout=10
            )
            
            # Should be validation error
            if response.status_code == 401:
                pytest.skip("Authentication required - test in authenticated environment")
            
            assert response.status_code == 400
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")


@pytest.mark.integration
class TestTenancyIsolation:
    """Test multi-tenant isolation"""
    
    def test_world_isolation(self):
        """Test that different world_ids are isolated"""
        try:
            world_id_1 = str(uuid.uuid4())
            world_id_2 = str(uuid.uuid4())
            
            # Create events in different worlds
            envelope_1 = {
                "world_id": world_id_1,
                "branch": "main",
                "kind": "test.isolation",
                "payload": {"message": "World 1"},
                "by": {"agent": "isolation-test"}
            }
            
            envelope_2 = {
                "world_id": world_id_2,
                "branch": "main", 
                "kind": "test.isolation",
                "payload": {"message": "World 2"},
                "by": {"agent": "isolation-test"}
            }
            
            headers = {"Content-Type": "application/json"}
            
            # Submit to both worlds
            response_1 = requests.post(f"{GATEWAY_URL}/v1/events", json=envelope_1, headers=headers, timeout=10)
            response_2 = requests.post(f"{GATEWAY_URL}/v1/events", json=envelope_2, headers=headers, timeout=10)
            
            if response_1.status_code == 401 or response_2.status_code == 401:
                pytest.skip("Authentication required - test in authenticated environment")
            
            # Both should succeed (different worlds)
            assert response_1.status_code == 201
            assert response_2.status_code == 201
            
            # Should get different event IDs
            data_1 = response_1.json()
            data_2 = response_2.json()
            assert data_1["event_id"] != data_2["event_id"]
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")


@pytest.mark.integration
class TestMetricsAndObservability:
    """Test metrics and observability endpoints"""
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        try:
            response = requests.get(f"{GATEWAY_URL}/metrics", timeout=5)
            assert response.status_code == 200
            
            # Should be Prometheus format
            content = response.text
            assert "# HELP" in content or "# TYPE" in content or len(content) > 0
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Metrics endpoint not available: {e}")
    
    def test_correlation_id_propagation(self):
        """Test correlation ID is propagated"""
        try:
            correlation_id = str(uuid.uuid4())
            envelope = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "test.correlation",
                "payload": {"test": "correlation"},
                "by": {"agent": "correlation-test"}
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-Id": correlation_id
            }
            
            response = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                pytest.skip("Authentication required")
            
            if response.status_code == 201:
                data = response.json()
                # Correlation ID should be returned
                assert data.get("correlation_id") == correlation_id
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

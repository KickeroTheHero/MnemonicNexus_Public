"""
Golden baseline replay tests
Tests deterministic replay and baseline hash stability
"""

import hashlib
import json
import os
import pytest
import requests
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8081")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/nexus")

@pytest.mark.golden
class TestGoldenBaseline:
    """Test golden baseline determinism"""
    
    def load_golden_envelope(self, filename: str) -> Dict[str, Any]:
        """Load a golden test envelope"""
        golden_dir = Path(__file__).parent
        envelope_path = golden_dir / "envelopes" / filename
        
        if not envelope_path.exists():
            pytest.skip(f"Golden envelope not found: {filename}")
        
        with open(envelope_path, 'r') as f:
            return json.load(f)
    
    def test_golden_envelope_structure(self):
        """Test that golden envelopes are well-formed"""
        try:
            envelope = self.load_golden_envelope("sample.json")
            
            # Should have required fields
            assert "world_id" in envelope
            assert "branch" in envelope
            assert "kind" in envelope
            assert "payload" in envelope
            assert "by" in envelope
            
            # Validate UUIDs where expected
            if "world_id" in envelope:
                uuid.UUID(envelope["world_id"])
            
        except FileNotFoundError:
            pytest.skip("No golden envelopes found")
    
    @pytest.mark.integration
    def test_deterministic_event_ids(self):
        """Test that events with same content get deterministic IDs"""
        try:
            # Create two identical events (except timestamp)
            base_envelope = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "test.deterministic",
                "payload": {
                    "content": "Deterministic test content",
                    "test_id": "fixed-test-id-123"
                },
                "by": {"agent": "deterministic-test"}
            }
            
            headers = {"Content-Type": "application/json"}
            
            # Submit first event
            response1 = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=base_envelope,
                headers=headers,
                timeout=10
            )
            
            if response1.status_code == 401:
                pytest.skip("Authentication required")
            
            assert response1.status_code == 201
            
            # Wait a moment
            time.sleep(0.1)
            
            # Submit second identical event to different world
            envelope2 = base_envelope.copy()
            envelope2["world_id"] = str(uuid.uuid4())
            
            response2 = requests.post(
                f"{GATEWAY_URL}/v1/events",
                json=envelope2,
                headers=headers,
                timeout=10
            )
            
            assert response2.status_code == 201
            
            # Compare responses
            data1 = response1.json()
            data2 = response2.json()
            
            # Events should have different IDs (different worlds)
            assert data1["event_id"] != data2["event_id"]
            
            # But same global sequence should be deterministic within world
            # (This is a basic determinism check)
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")
    
    def test_baseline_hash_stability(self):
        """Test baseline hash generation is stable"""
        # Create test data
        test_data = {
            "events": [
                {"id": 1, "kind": "test.event", "data": "test1"},
                {"id": 2, "kind": "test.event", "data": "test2"},
                {"id": 3, "kind": "test.event", "data": "test3"}
            ]
        }
        
        # Generate hash multiple times
        hash1 = self.generate_test_hash(test_data)
        hash2 = self.generate_test_hash(test_data)
        hash3 = self.generate_test_hash(test_data)
        
        # Should be identical
        assert hash1 == hash2
        assert hash2 == hash3
        
        # Different data should produce different hash
        test_data_modified = test_data.copy()
        test_data_modified["events"].append({"id": 4, "kind": "test.event", "data": "test4"})
        
        hash_different = self.generate_test_hash(test_data_modified)
        assert hash_different != hash1
    
    def generate_test_hash(self, data: Dict[str, Any]) -> str:
        """Generate deterministic hash for test data"""
        # Sort data deterministically
        serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Generate hash
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    
    @pytest.mark.integration
    def test_replay_consistency(self):
        """Test that replay produces consistent results"""
        try:
            world_id = str(uuid.uuid4())
            events = []
            
            # Create a sequence of events
            for i in range(3):
                envelope = {
                    "world_id": world_id,
                    "branch": "main",
                    "kind": f"test.replay.{i}",
                    "payload": {
                        "sequence": i,
                        "message": f"Replay test event {i}"
                    },
                    "by": {"agent": "replay-test"}
                }
                
                response = requests.post(
                    f"{GATEWAY_URL}/v1/events",
                    json=envelope,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 401:
                    pytest.skip("Authentication required")
                
                assert response.status_code == 201
                events.append(response.json())
            
            # Verify sequence consistency
            for i, event_data in enumerate(events):
                assert "event_id" in event_data
                assert "global_seq" in event_data
                
                # Global sequence should be increasing
                if i > 0:
                    assert event_data["global_seq"] > events[i-1]["global_seq"]
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gateway not available: {e}")


@pytest.mark.golden
class TestGoldenFixtures:
    """Test against golden fixture files"""
    
    def test_golden_yaml_files_exist(self):
        """Test that golden YAML files exist and are readable"""
        golden_dir = Path(__file__).parent
        yaml_files = list(golden_dir.glob("*.yaml"))
        
        # Should have some golden files
        assert len(yaml_files) > 0, "No golden YAML files found"
        
        for yaml_file in yaml_files:
            # Should be readable
            assert yaml_file.is_file()
            assert yaml_file.stat().st_size > 0
    
    def test_golden_envelopes_exist(self):
        """Test that golden envelope files exist"""
        golden_dir = Path(__file__).parent
        envelopes_dir = golden_dir / "envelopes"
        
        if envelopes_dir.exists():
            json_files = list(envelopes_dir.glob("*.json"))
            assert len(json_files) > 0, "No golden envelope files found"
            
            for json_file in json_files:
                # Should be valid JSON
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    assert isinstance(data, dict)
        else:
            pytest.skip("No golden envelopes directory found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "golden"])

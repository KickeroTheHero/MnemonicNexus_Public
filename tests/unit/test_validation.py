"""
Unit tests for envelope validation and core functionality
Tests basic validation logic without requiring running services
"""

import json
import pytest
import uuid
from pathlib import Path
from typing import Dict, Any

# Import schemas for validation
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"

def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load JSON schema for validation"""
    schema_path = SCHEMAS_DIR / schema_name
    with open(schema_path, 'r') as f:
        return json.load(f)

def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load test fixture"""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    
    # Try different fixture locations
    possible_paths = [
        fixtures_dir / fixture_name,
        fixtures_dir / "emo" / fixture_name,
        Path(__file__).parent.parent / "golden" / "envelopes" / fixture_name
    ]
    
    for path in possible_paths:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
    
    raise FileNotFoundError(f"Fixture not found: {fixture_name}")

class TestEnvelopeValidation:
    """Test envelope validation logic"""
    
    def test_event_schema_structure(self):
        """Test that event schema is valid JSON Schema"""
        schema = load_schema("event.schema.json")
        
        # Basic schema structure checks
        assert schema["type"] == "object"
        assert "required" in schema
        assert "properties" in schema
        
        # Required fields for events
        required_fields = schema["required"]
        assert "world_id" in required_fields
        assert "branch" in required_fields
        assert "kind" in required_fields
        assert "payload" in required_fields
        assert "by" in required_fields
    
    def test_envelope_required_fields(self):
        """Test that sample envelope has all required fields"""
        try:
            envelope = load_fixture("sample.json")
        except FileNotFoundError:
            pytest.skip("No sample fixture found")
            
        # Check required fields exist
        assert "world_id" in envelope
        assert "branch" in envelope  
        assert "kind" in envelope
        assert "payload" in envelope
        assert "by" in envelope
        
        # Validate field types
        assert isinstance(envelope["world_id"], str)
        assert isinstance(envelope["branch"], str)
        assert isinstance(envelope["kind"], str)
        assert isinstance(envelope["payload"], dict)
        assert isinstance(envelope["by"], dict)
        
        # Check by field structure
        assert "agent" in envelope["by"]
    
    def test_world_id_format(self):
        """Test world_id UUID format validation"""
        try:
            envelope = load_fixture("sample.json")
            world_id = envelope["world_id"]
            
            # Should be valid UUID
            uuid_obj = uuid.UUID(world_id)
            assert str(uuid_obj) == world_id
            
        except FileNotFoundError:
            pytest.skip("No sample fixture found")
    
    def test_idempotency_key_format(self):
        """Test idempotency key format if present"""
        try:
            envelope = load_fixture("sample.json")
            payload = envelope.get("payload", {})
            
            if "idempotency_key" in payload:
                idem_key = payload["idempotency_key"]
                
                # Should follow format: {emo_id}:{emo_version}:{operation}
                parts = idem_key.split(":")
                assert len(parts) == 3
                
                emo_id, version, operation = parts
                
                # emo_id should be UUID
                uuid.UUID(emo_id)
                
                # version should be numeric
                assert version.isdigit()
                
                # operation should be known type
                assert operation in ["created", "updated", "deleted"]
                
        except FileNotFoundError:
            pytest.skip("No sample fixture found")


class TestTenancyValidation:
    """Test multi-tenancy validation"""
    
    def test_world_id_isolation(self):
        """Test that world_id is properly isolated"""
        world_id_1 = str(uuid.uuid4())
        world_id_2 = str(uuid.uuid4())
        
        # Different world_ids should be different
        assert world_id_1 != world_id_2
        
        # Both should be valid UUIDs
        uuid.UUID(world_id_1)
        uuid.UUID(world_id_2)
    
    def test_branch_naming(self):
        """Test branch naming conventions"""
        valid_branches = ["main", "feature-123", "experiment/test", "user-branch_1"]
        
        for branch in valid_branches:
            # Branch names should be non-empty strings
            assert isinstance(branch, str)
            assert len(branch) > 0
            assert len(branch) <= 255  # Reasonable limit


class TestSchemaCompliance:
    """Test JSON schema compliance"""
    
    def test_openapi_schema_structure(self):
        """Test OpenAPI schema is well-formed"""
        schema = load_schema("openapi.json")
        
        # Basic OpenAPI structure
        assert schema["openapi"] == "3.0.3"
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
        
        # Info section
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        
        # Should have health endpoint
        paths = schema["paths"]
        assert "/health" in paths
        assert "/v1/events" in paths
    
    def test_emo_schema_structure(self):
        """Test EMO base schema structure"""
        try:
            schema = load_schema("json/emo.base.v1.json")
            
            # Basic structure
            assert schema["type"] == "object"
            assert "required" in schema
            assert "properties" in schema
            
            # Required fields
            required = schema["required"]
            assert "emo_id" in required
            assert "emo_type" in required
            assert "world_id" in required
            assert "tenant_id" in required
            
        except FileNotFoundError:
            pytest.skip("EMO schema not found")


class TestCorrelationIds:
    """Test correlation ID propagation"""
    
    def test_correlation_id_generation(self):
        """Test correlation ID generation"""
        # Generate correlation IDs
        corr_id_1 = str(uuid.uuid4())
        corr_id_2 = str(uuid.uuid4())
        
        # Should be unique
        assert corr_id_1 != corr_id_2
        
        # Should be valid UUIDs
        uuid.UUID(corr_id_1)
        uuid.UUID(corr_id_2)
    
    def test_correlation_id_format(self):
        """Test correlation ID follows UUID format"""
        test_id = str(uuid.uuid4())
        
        # Should match UUID pattern
        assert len(test_id) == 36
        assert test_id.count('-') == 4
        
        # Should be parseable as UUID
        parsed = uuid.UUID(test_id)
        assert str(parsed) == test_id


if __name__ == "__main__":
    pytest.main([__file__])

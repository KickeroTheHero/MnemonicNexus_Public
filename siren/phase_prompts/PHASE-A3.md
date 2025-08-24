# PHASE A3: Enhanced Event Envelope

**Objective**: Implement robust V2 event envelope validation with comprehensive audit and integrity features

**Prerequisites**: Phase A2 complete (V2 schema with tenancy operational)

---

## 🎯 **Goals**

### **Primary**
- Implement comprehensive event envelope validation
- Establish payload hash generation for integrity verification
- Add robust audit trail with `by.agent` tracking
- Create envelope versioning strategy for future evolution

### **Non-Goals**
- Gateway implementation (Phase A6 scope)
- Projector processing logic (Phase A5 scope)
- Event replay functionality (Phase B scope)

---

## 📋 **Deliverables**

### **1. Event Envelope Validation Library** (`services/common/envelope.py`)
```python
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import json
import uuid

class EventEnvelope:
    """V2 Event Envelope with comprehensive validation"""
    
    def __init__(self, envelope_data: Dict[str, Any]):
        self.data = envelope_data
        self._validate()
        
    def _validate(self) -> None:
        """Comprehensive envelope validation"""
        # Required fields
        required = ['world_id', 'branch', 'kind', 'payload', 'by']
        for field in required:
            if field not in self.data:
                raise ValueError(f"Missing required field: {field}")
                
        # UUID validation
        try:
            uuid.UUID(self.data['world_id'])
        except ValueError:
            raise ValueError("world_id must be valid UUID")
            
        # Agent validation
        if 'agent' not in self.data['by']:
            raise ValueError("by.agent is required for audit trail")
            
        # Timestamp validation
        if 'occurred_at' in self.data:
            self._validate_timestamp(self.data['occurred_at'])
    
    def compute_payload_hash(self) -> str:
        """Generate SHA-256 hash of canonical envelope"""
        canonical = self._canonicalize()
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def _canonicalize(self) -> str:
        """Create canonical JSON representation for hashing"""
        # Sort keys recursively for deterministic hash
        return json.dumps(self.data, sort_keys=True, separators=(',', ':'))
    
    def enrich_with_server_fields(self) -> Dict[str, Any]:
        """Add server-assigned fields"""
        enriched = self.data.copy()
        enriched['received_at'] = datetime.utcnow().isoformat() + 'Z'
        enriched['payload_hash'] = self.compute_payload_hash()
        return enriched
```

### **2. Event Validation Middleware** (`services/common/validation.py`)
```python
from fastapi import HTTPException, Header
from typing import Optional

class EventValidationMiddleware:
    """FastAPI middleware for event envelope validation"""
    
    @staticmethod
    def validate_headers(
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
        correlation_id: Optional[str] = Header(None, alias="X-Correlation-Id")
    ) -> Dict[str, Optional[str]]:
        """Extract and validate HTTP headers"""
        return {
            'idempotency_key': idempotency_key,
            'correlation_id': correlation_id or str(uuid.uuid4())
        }
    
    @staticmethod
    def validate_envelope(envelope_data: Dict[str, Any]) -> EventEnvelope:
        """Validate complete event envelope"""
        try:
            envelope = EventEnvelope(envelope_data)
            return envelope
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
```

### **3. Database Integration** (`services/common/persistence.py`)
```python
import asyncpg
from typing import Dict, Any

class EventPersistence:
    """Database operations for event storage"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
    
    async def store_event(
        self, 
        envelope: EventEnvelope, 
        headers: Dict[str, Optional[str]]
    ) -> Dict[str, Any]:
        """Store event with full validation and integrity"""
        
        enriched_envelope = envelope.enrich_with_server_fields()
        
        async with self.pool.acquire() as conn:
            try:
                # Check idempotency if key provided
                if headers['idempotency_key']:
                    existing = await self._check_idempotency(
                        conn, 
                        envelope.data['world_id'],
                        envelope.data['branch'],
                        headers['idempotency_key']
                    )
                    if existing:
                        raise ConflictError("Duplicate idempotency key")
                
                # Insert event
                result = await conn.fetchrow("""
                    INSERT INTO event_core.event_log (
                        world_id, branch, event_id, kind, envelope, 
                        occurred_at, received_at, idempotency_key, payload_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING global_seq, event_id, received_at
                """, 
                    envelope.data['world_id'],
                    envelope.data['branch'],
                    str(uuid.uuid4()),
                    envelope.data['kind'],
                    json.dumps(enriched_envelope),
                    envelope.data.get('occurred_at'),
                    enriched_envelope['received_at'],
                    headers['idempotency_key'],
                    enriched_envelope['payload_hash']
                )
                
                # Add to outbox for CDC
                await conn.execute("""
                    INSERT INTO event_core.outbox (
                        global_seq, world_id, branch, event_id, envelope, payload_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    result['global_seq'],
                    envelope.data['world_id'],
                    envelope.data['branch'],
                    result['event_id'],
                    json.dumps(enriched_envelope),
                    enriched_envelope['payload_hash']
                )
                
                return {
                    'event_id': str(result['event_id']),
                    'global_seq': result['global_seq'],
                    'received_at': result['received_at'].isoformat() + 'Z'
                }
                
            except asyncpg.UniqueViolationError:
                raise ConflictError("Idempotency key conflict")
```

### **4. Envelope Test Suite** (`tests/test_envelope.py`)
```python
import pytest
from services.common.envelope import EventEnvelope

class TestEventEnvelope:
    """Comprehensive envelope validation testing"""
    
    def test_valid_envelope(self):
        """Test valid V2 envelope structure"""
        envelope_data = {
            'world_id': '550e8400-e29b-41d4-a716-446655440000',
            'branch': 'main',
            'kind': 'note.created',
            'payload': {'title': 'Test Note'},
            'by': {'agent': 'test-agent'},
            'version': 1
        }
        envelope = EventEnvelope(envelope_data)
        assert envelope.data['world_id'] == envelope_data['world_id']
    
    def test_missing_required_fields(self):
        """Test validation of required fields"""
        incomplete_data = {
            'world_id': '550e8400-e29b-41d4-a716-446655440000',
            'branch': 'main'
            # Missing kind, payload, by
        }
        with pytest.raises(ValueError, match="Missing required field"):
            EventEnvelope(incomplete_data)
    
    def test_invalid_world_id(self):
        """Test UUID validation for world_id"""
        invalid_data = {
            'world_id': 'not-a-uuid',
            'branch': 'main',
            'kind': 'test',
            'payload': {},
            'by': {'agent': 'test'}
        }
        with pytest.raises(ValueError, match="world_id must be valid UUID"):
            EventEnvelope(invalid_data)
    
    def test_payload_hash_deterministic(self):
        """Test that payload hash is deterministic"""
        envelope_data = {
            'world_id': '550e8400-e29b-41d4-a716-446655440000',
            'branch': 'main',
            'kind': 'note.created',
            'payload': {'title': 'Test', 'order': [2, 1, 3]},
            'by': {'agent': 'test-agent'}
        }
        envelope1 = EventEnvelope(envelope_data)
        envelope2 = EventEnvelope(envelope_data)
        assert envelope1.compute_payload_hash() == envelope2.compute_payload_hash()
```

---

## ✅ **Acceptance Criteria**

### **Validation Framework**
- [ ] EventEnvelope class validates all required V2 fields
- [ ] UUID validation rejects malformed world_id values
- [ ] Agent audit field validation enforces by.agent presence
- [ ] Timestamp validation handles both ISO8601 and missing occurred_at

### **Integrity Features**
- [ ] Payload hash generation is deterministic and collision-resistant
- [ ] Envelope canonicalization produces consistent JSON ordering
- [ ] Server enrichment adds received_at and payload_hash correctly
- [ ] Hash verification detects any envelope tampering

### **Database Integration**
- [ ] Event storage includes comprehensive validation
- [ ] Idempotency checking works with partial unique constraints
- [ ] Outbox population is transactionally consistent
- [ ] Conflict detection returns proper 409 responses

### **Test Coverage**
- [ ] Valid envelope structures pass validation
- [ ] Invalid envelopes generate appropriate error messages
- [ ] Edge cases (optional fields, malformed data) handled correctly
- [ ] Performance acceptable for high-volume event ingestion

---

## 🚧 **Implementation Steps**

### **Step 1: Core Validation Library**
1. Implement EventEnvelope class with comprehensive validation
2. Add payload hash generation with deterministic canonicalization
3. Create server field enrichment (received_at, payload_hash)
4. Test validation edge cases and error handling

### **Step 2: Middleware Integration**
1. Create FastAPI middleware for header extraction
2. Implement validation error handling with proper HTTP responses
3. Add correlation ID generation when not provided
4. Test middleware integration with various request formats

### **Step 3: Database Persistence**
1. Implement event storage with validation integration
2. Add idempotency checking with partial constraint handling
3. Ensure transactional consistency between event_log and outbox
4. Test conflict detection and error responses

### **Step 4: Comprehensive Testing**
1. Unit tests for all validation scenarios
2. Integration tests with database operations
3. Performance tests for high-volume scenarios
4. Error path testing for robustness

---

## 🔧 **Technical Decisions**

### **Validation Strategy**
- **Fail Fast**: Reject invalid envelopes immediately at ingestion
- **Comprehensive**: Validate structure, types, and business rules
- **Clear Errors**: Provide specific error messages for debugging

### **Hash Generation**
- **Algorithm**: SHA-256 for cryptographic strength
- **Canonicalization**: JSON with sorted keys for determinism
- **Scope**: Complete envelope for tamper detection

### **Audit Trail**
- **Required Agent**: All events must specify originating agent
- **Correlation Support**: Optional but tracked for tracing
- **Immutable Record**: Audit fields cannot be modified post-ingestion

---

## 🚨 **Risks & Mitigations**

### **Performance Impact**
- **Risk**: Validation overhead slows event ingestion
- **Mitigation**: Optimize validation logic, consider caching

### **Hash Collision**
- **Risk**: SHA-256 collision corrupts integrity checking
- **Mitigation**: Use cryptographically secure algorithm, monitor for anomalies

### **Validation Evolution**
- **Risk**: Changing validation rules breaks existing clients
- **Mitigation**: Version-aware validation, backward compatibility

---

## 📊 **Success Metrics**

- **Validation Speed**: < 1ms per envelope validation
- **Error Rate**: < 0.1% false positive validation errors
- **Hash Uniqueness**: No hash collisions in test scenarios
- **Integration Success**: Clean integration with Phase A2 schema

---

## 🔄 **Next Phase**

**Phase A4**: CDC Publisher Service
- Implement reliable outbox publisher
- Add retry logic and dead letter queue
- Establish projector notification system

**Dependencies**: A3 envelope foundation enables reliable A4 CDC and A6 Gateway implementation

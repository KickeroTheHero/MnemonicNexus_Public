# PHASE A6: Gateway 409 Handling

**Objective**: Implement FastAPI Gateway with comprehensive idempotency and request validation

**Prerequisites**: Phase A5 complete (Projector SDK operational with event processing)

---

## 🎯 **Goals**

### **Primary**
- Implement complete V2 Gateway API with header-based idempotency
- Add comprehensive request validation and error handling
- Establish 409 Conflict responses for duplicate idempotency keys
- Create robust API endpoint implementations matching OpenAPI spec

### **Non-Goals**
- Search implementations (Phase B scope)
- Administrative endpoints (Phase B scope)
- Performance optimization (Phase B scope)

---

## 📋 **Deliverables**

### **1. FastAPI Gateway Service** (`services/gateway/main.py`)
```python
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncpg
import asyncio
import logging
from typing import Optional, Dict, Any
import uuid

from .models import EventEnvelope, EventAccepted, ErrorResponse
from .validation import EventValidationMiddleware
from .persistence import EventPersistence
from .monitoring import GatewayMetrics

app = FastAPI(
    title="MnemonicNexus V2 Gateway",
    description="V2 Gateway API with tenancy and idempotency",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db_pool = None
event_persistence = None
metrics = GatewayMetrics()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection and dependencies"""
    global db_pool, event_persistence
    
    database_url = "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    db_pool = await asyncpg.create_pool(database_url)
    event_persistence = EventPersistence(db_pool)
    
    logging.info("Gateway V2 started successfully")

@app.on_event("shutdown") 
async def shutdown_event():
    """Clean up resources"""
    if db_pool:
        await db_pool.close()

@app.get("/health")
async def health_check():
    """Gateway health with dependency status"""
    try:
        # Check database connectivity
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            
        # Check projector lag (basic health indicator)
        lag_data = await event_persistence.get_projector_lag()
        
        return {
            "status": "healthy",
            "version": "2.0.0",
            "components": {
                "database": {"status": "up", "latency_ms": 2},
                "projector_lag": lag_data
            }
        }
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/v1/events", response_model=EventAccepted)
async def create_event(
    envelope: EventEnvelope,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-Id")
) -> EventAccepted:
    """Append event to event log with comprehensive validation"""
    
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    try:
        # Validate headers
        headers = EventValidationMiddleware.validate_headers(
            idempotency_key, correlation_id
        )
        
        # Validate envelope structure
        validated_envelope = EventValidationMiddleware.validate_envelope(
            envelope.dict()
        )
        
        # Store event with idempotency checking
        result = await event_persistence.store_event(
            validated_envelope, headers
        )
        
        # Record metrics
        metrics.record_event_created(
            envelope.world_id, 
            envelope.branch, 
            envelope.kind
        )
        
        return EventAccepted(
            event_id=result['event_id'],
            global_seq=result['global_seq'],
            received_at=result['received_at'],
            correlation_id=correlation_id
        )
        
    except ConflictError as e:
        # Return 409 for idempotency conflicts
        metrics.record_idempotency_conflict(envelope.world_id, envelope.branch)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": str(e),
                "correlation_id": correlation_id
            }
        )
    except ValidationError as e:
        metrics.record_validation_error(envelope.world_id, envelope.branch)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "validation_error", 
                "message": str(e),
                "correlation_id": correlation_id
            }
        )
    except Exception as e:
        logging.error(f"Event creation failed: {e}")
        metrics.record_internal_error()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "Internal server error",
                "correlation_id": correlation_id
            }
        )

@app.get("/v1/events")
async def list_events(
    world_id: str,
    branch: str = "main",
    kind: Optional[str] = None,
    after_global_seq: Optional[int] = None,
    limit: int = 100
):
    """List events with pagination and filtering"""
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 1000")
    
    try:
        events = await event_persistence.list_events(
            world_id, branch, kind, after_global_seq, limit
        )
        
        return {
            "items": events,
            "next_after_global_seq": events[-1]["global_seq"] if events else None,
            "has_more": len(events) == limit
        }
        
    except Exception as e:
        logging.error(f"Event listing failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/v1/events/{event_id}")
async def get_event(event_id: str):
    """Get specific event by ID"""
    try:
        event = await event_persistence.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Event retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Standardized error response format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": getattr(exc.detail, 'code', 'http_error'),
            "message": getattr(exc.detail, 'message', str(exc.detail)),
            "correlation_id": getattr(exc.detail, 'correlation_id', None)
        }
    )
```

### **2. Pydantic Models** (`services/gateway/models.py`)
```python
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

class EventEnvelope(BaseModel):
    """V2 Event Envelope with comprehensive validation"""
    
    world_id: str = Field(..., description="Tenancy key (UUID)")
    branch: str = Field(..., description="Branch name")
    kind: str = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Event data")
    by: Dict[str, Any] = Field(..., description="Audit information")
    version: int = Field(1, description="Envelope version")
    occurred_at: Optional[str] = Field(None, description="Client timestamp")
    causation_id: Optional[str] = Field(None, description="Causation chain ID")
    
    @validator('world_id')
    def validate_world_id(cls, v):
        """Ensure world_id is valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("world_id must be a valid UUID")
    
    @validator('by')
    def validate_by(cls, v):
        """Ensure audit information includes required agent"""
        if 'agent' not in v:
            raise ValueError("by.agent is required for audit trail")
        return v
    
    @validator('occurred_at')
    def validate_occurred_at(cls, v):
        """Validate timestamp format if provided"""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError("occurred_at must be valid ISO8601 timestamp")
        return v

class EventAccepted(BaseModel):
    """Response for successfully accepted event"""
    
    event_id: str = Field(..., description="Generated event UUID")
    global_seq: int = Field(..., description="Global sequence number")
    received_at: str = Field(..., description="Server timestamp")
    correlation_id: str = Field(..., description="Request correlation ID")

class ErrorResponse(BaseModel):
    """Standardized error response"""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
```

### **3. Enhanced Validation** (`services/gateway/validation.py`)
```python
from typing import Dict, Any, Optional
from fastapi import HTTPException
import uuid

class ConflictError(Exception):
    """Idempotency conflict error"""
    pass

class ValidationError(Exception):
    """Envelope validation error"""
    pass

class EventValidationMiddleware:
    """Comprehensive event validation middleware"""
    
    @staticmethod
    def validate_headers(
        idempotency_key: Optional[str],
        correlation_id: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """Validate and normalize HTTP headers"""
        
        # Validate idempotency key format if provided
        if idempotency_key and len(idempotency_key.strip()) == 0:
            raise ValidationError("Idempotency-Key cannot be empty string")
            
        # Validate correlation ID format if provided
        if correlation_id:
            try:
                uuid.UUID(correlation_id)
            except ValueError:
                raise ValidationError("X-Correlation-Id must be valid UUID format")
        
        return {
            'idempotency_key': idempotency_key.strip() if idempotency_key else None,
            'correlation_id': correlation_id or str(uuid.uuid4())
        }
    
    @staticmethod
    def validate_envelope(envelope_data: Dict[str, Any]) -> 'EventEnvelope':
        """Validate complete event envelope"""
        from .models import EventEnvelope
        
        try:
            # Pydantic validation handles structure and types
            envelope = EventEnvelope(**envelope_data)
            
            # Additional business logic validation
            EventValidationMiddleware._validate_business_rules(envelope)
            
            return envelope
            
        except Exception as e:
            raise ValidationError(f"Envelope validation failed: {str(e)}")
    
    @staticmethod
    def _validate_business_rules(envelope: 'EventEnvelope'):
        """Additional business logic validation"""
        
        # Validate branch name format
        if not envelope.branch.replace('_', '').replace('-', '').isalnum():
            raise ValidationError("Branch name must be alphanumeric with hyphens/underscores")
        
        # Validate event kind format
        if '.' not in envelope.kind or len(envelope.kind.split('.')) != 2:
            raise ValidationError("Event kind must be in format 'category.action'")
        
        # Validate payload is not empty
        if not envelope.payload:
            raise ValidationError("Event payload cannot be empty")
```

### **4. Database Persistence** (`services/gateway/persistence.py`)
```python
import asyncpg
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from .validation import ConflictError

class EventPersistence:
    """Database operations for event storage and retrieval"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
    
    async def store_event(
        self, 
        envelope: 'EventEnvelope', 
        headers: Dict[str, Optional[str]]
    ) -> Dict[str, Any]:
        """Store event with comprehensive validation and integrity"""
        
        # Enrich envelope with server fields
        enriched_envelope = envelope.dict()
        enriched_envelope['received_at'] = datetime.utcnow().isoformat() + 'Z'
        enriched_envelope['payload_hash'] = self._compute_payload_hash(enriched_envelope)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Check idempotency if key provided
                if headers['idempotency_key']:
                    existing = await self._check_idempotency(
                        conn,
                        envelope.world_id,
                        envelope.branch,
                        headers['idempotency_key']
                    )
                    if existing:
                        raise ConflictError(
                            f"Duplicate idempotency key: {headers['idempotency_key']}"
                        )
                
                # Generate event ID
                event_id = str(uuid.uuid4())
                
                # Insert into event log
                result = await conn.fetchrow("""
                    INSERT INTO event_core.event_log (
                        world_id, branch, event_id, kind, envelope,
                        occurred_at, received_at, idempotency_key, payload_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING global_seq, received_at
                """,
                    envelope.world_id,
                    envelope.branch,
                    event_id,
                    envelope.kind,
                    json.dumps(enriched_envelope),
                    envelope.occurred_at,
                    enriched_envelope['received_at'],
                    headers['idempotency_key'],
                    enriched_envelope['payload_hash']
                )
                
                # Add to outbox for CDC
                await conn.execute("""
                    INSERT INTO event_core.outbox (
                        global_seq, world_id, branch, event_id, 
                        envelope, payload_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    result['global_seq'],
                    envelope.world_id,
                    envelope.branch,
                    event_id,
                    json.dumps(enriched_envelope),
                    enriched_envelope['payload_hash']
                )
                
                return {
                    'event_id': event_id,
                    'global_seq': result['global_seq'],
                    'received_at': result['received_at'].isoformat() + 'Z'
                }
    
    async def _check_idempotency(
        self,
        conn: asyncpg.Connection,
        world_id: str,
        branch: str,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Check for existing event with same idempotency key"""
        return await conn.fetchrow("""
            SELECT event_id, global_seq, received_at
            FROM event_core.event_log
            WHERE world_id = $1 AND branch = $2 AND idempotency_key = $3
        """, world_id, branch, idempotency_key)
    
    async def list_events(
        self,
        world_id: str,
        branch: str,
        kind: Optional[str],
        after_global_seq: Optional[int],
        limit: int
    ) -> List[Dict[str, Any]]:
        """List events with filtering and pagination"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT event_id, world_id, branch, kind, envelope, 
                       global_seq, received_at
                FROM event_core.event_log
                WHERE world_id = $1 AND branch = $2
            """
            params = [world_id, branch]
            
            if kind:
                query += " AND kind = $3"
                params.append(kind)
                
            if after_global_seq:
                query += f" AND global_seq > ${len(params) + 1}"
                params.append(after_global_seq)
            
            query += f" ORDER BY global_seq LIMIT ${len(params) + 1}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [
                {
                    "event_id": str(row['event_id']),
                    "world_id": str(row['world_id']),
                    "branch": row['branch'],
                    "kind": row['kind'],
                    "global_seq": row['global_seq'],
                    "received_at": row['received_at'].isoformat() + 'Z',
                    **json.loads(row['envelope'])
                }
                for row in rows
            ]
    
    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get specific event by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT event_id, world_id, branch, kind, envelope,
                       global_seq, received_at
                FROM event_core.event_log
                WHERE event_id = $1
            """, event_id)
            
            if not row:
                return None
                
            return {
                "event_id": str(row['event_id']),
                "world_id": str(row['world_id']),
                "branch": row['branch'],
                "kind": row['kind'],
                "global_seq": row['global_seq'],
                "received_at": row['received_at'].isoformat() + 'Z',
                **json.loads(row['envelope'])
            }
    
    def _compute_payload_hash(self, envelope: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of canonical envelope"""
        import hashlib
        canonical = json.dumps(envelope, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

### **5. Gateway Monitoring** (`services/gateway/monitoring.py`)
```python
from prometheus_client import Counter, Histogram, Gauge
import time

class GatewayMetrics:
    """Prometheus metrics for Gateway monitoring"""
    
    def __init__(self):
        self.events_created = Counter(
            'gateway_events_created_total',
            'Total events created successfully',
            ['world_id', 'branch', 'kind']
        )
        
        self.idempotency_conflicts = Counter(
            'gateway_idempotency_conflicts_total',
            'Total idempotency conflicts (409 responses)',
            ['world_id', 'branch']
        )
        
        self.validation_errors = Counter(
            'gateway_validation_errors_total',
            'Total validation errors (400 responses)',
            ['world_id', 'branch']
        )
        
        self.internal_errors = Counter(
            'gateway_internal_errors_total',
            'Total internal server errors (500 responses)'
        )
        
        self.request_duration = Histogram(
            'gateway_request_duration_seconds',
            'Request processing duration',
            ['endpoint', 'status_code']
        )
    
    def record_event_created(self, world_id: str, branch: str, kind: str):
        """Record successful event creation"""
        self.events_created.labels(
            world_id=world_id,
            branch=branch,
            kind=kind
        ).inc()
    
    def record_idempotency_conflict(self, world_id: str, branch: str):
        """Record idempotency conflict"""
        self.idempotency_conflicts.labels(
            world_id=world_id,
            branch=branch
        ).inc()
    
    def record_validation_error(self, world_id: str, branch: str):
        """Record validation error"""
        self.validation_errors.labels(
            world_id=world_id,
            branch=branch
        ).inc()
    
    def record_internal_error(self):
        """Record internal server error"""
        self.internal_errors.inc()
```

---

## ✅ **Acceptance Criteria**

### **API Implementation**
- [ ] All core endpoints match OpenAPI specification exactly
- [ ] Header-based idempotency with proper 409 Conflict responses
- [ ] Comprehensive request validation with clear error messages
- [ ] Proper HTTP status codes and response formats

### **Idempotency Handling**
- [ ] Duplicate Idempotency-Key returns 409 with original event details
- [ ] Missing idempotency key allows multiple identical requests
- [ ] Idempotency scoped correctly to (world_id, branch, key)
- [ ] Edge cases (empty keys, malformed headers) handled gracefully

### **Error Handling**
- [ ] Validation errors return 400 with specific field information
- [ ] Database errors return 500 with correlation tracking
- [ ] Malformed requests return 400 with clear error descriptions
- [ ] All error responses include correlation_id for tracing

### **Integration**
- [ ] Clean integration with Phase A3 validation framework
- [ ] Proper interaction with Phase A2 database schema
- [ ] Events flow correctly to Phase A4 publisher via outbox
- [ ] Health endpoint reports accurate system status

---

## 🚧 **Implementation Steps**

### **Step 1: Core FastAPI Application**
1. Implement main FastAPI application with middleware
2. Add health check and basic endpoints
3. Create database connection management
4. Test basic service startup and health checks

### **Step 2: Event Ingestion Endpoint**
1. Implement POST /v1/events with full validation
2. Add header extraction and processing
3. Integrate with Phase A3 validation framework
4. Test idempotency conflict detection and 409 responses

### **Step 3: Event Retrieval Endpoints**
1. Implement GET /v1/events with pagination
2. Add GET /v1/events/{id} for specific event retrieval
3. Create proper response formatting
4. Test with various query parameters and edge cases

### **Step 4: Monitoring and Error Handling**
1. Add Prometheus metrics collection
2. Implement comprehensive error handling
3. Create structured logging for operations
4. Test monitoring integration and error scenarios

---

## 🔧 **Technical Decisions**

### **Header-Based Idempotency**
- **Idempotency-Key**: Optional header for client-controlled deduplication
- **X-Correlation-Id**: Optional header for request tracing
- **Scope**: Per (world_id, branch) for tenant isolation

### **Error Response Format**
- **Standardized Structure**: All errors include code, message, correlation_id
- **HTTP Status Codes**: 400 (validation), 409 (conflict), 500 (internal)
- **Client-Friendly**: Clear error messages for debugging

### **Database Integration**
- **Connection Pooling**: Use asyncpg pool for performance
- **Transaction Safety**: Ensure event_log and outbox consistency
- **Error Propagation**: Convert database errors to appropriate HTTP responses

---

## 🚨 **Risks & Mitigations**

### **Database Connection Failures**
- **Risk**: Database unavailability breaks Gateway completely
- **Mitigation**: Connection pooling, retry logic, health monitoring

### **Idempotency Edge Cases**
- **Risk**: Race conditions in idempotency checking
- **Mitigation**: Database-level unique constraints, proper transaction isolation

### **Performance Under Load**
- **Risk**: Gateway becomes bottleneck under high request volume
- **Mitigation**: Async processing, connection pooling, monitoring

---

## 📊 **Success Metrics**

- **Response Time**: p95 < 100ms for event ingestion
- **Throughput**: 1000+ requests/second sustainable
- **Error Rate**: < 0.1% internal server errors
- **Idempotency Accuracy**: 100% correct 409 responses for duplicates

---

## 🔄 **Next Phase**

**Phase A7**: Documentation Hygiene & Archive
- Comprehensive documentation validation
- Automated drift detection
- CI gate integration for documentation consistency

**Dependencies**: A6 Gateway completes the core V2 event ingestion pipeline, enabling end-to-end testing of the foundation

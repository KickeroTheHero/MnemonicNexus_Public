# PHASE A5: Python Projector SDK

**Objective**: Create standardized projector framework with watermark management and deterministic replay

**Prerequisites**: Phase A4 complete (CDC Publisher delivering events reliably)

## 🏗️ **Architecture Integration**

The Projector SDK integrates with the complete V2 event flow:

```
Gateway V2 → Event Validation → Outbox → CDC Publisher → Projector SDK
   ↓              ↓                ↓           ↓             ↓
HTTP API      EventEnvelope    Database   HTTP POST    FastAPI Server
 Events        Validation      Transactional  /events      Event Handler
              + Hashing         Outbox       Delivery     + Watermarks
```

**Key Integration Points:**
- **Input**: HTTP POST `/events` from CDC Publisher (Phase A4)
- **Payload**: EventPayload with `global_seq`, `event_id`, `envelope`, `payload_hash`
- **Output**: HTTP 200 (success) or 500 (failure) for Publisher retry logic
- **State**: Watermarks stored in `event_core.projector_watermarks` table
- **Target**: Lens tables (`lens_rel.*`, `lens_sem.*`, `lens_graph.*`)

---

## 🎯 **Goals**

### **Primary**
- Implement comprehensive projector SDK with standardized interface
- Establish watermark-based checkpoint management
- Create deterministic state hashing for replay validation
- Enable idempotent event processing across all projector types

### **Non-Goals**
- Specific lens implementations (Phase B scope)
- Gateway implementation (Phase A6 scope)
- Performance optimization (Phase B scope)

---

## 📋 **Deliverables**

### **1. Core Projector SDK** (`projectors/sdk/projector.py`)
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import asyncpg
import hashlib
import json
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class EventPayload(BaseModel):
    """Event payload received from CDC Publisher"""
    global_seq: int
    event_id: str
    envelope: Dict[str, Any]
    payload_hash: Optional[str] = None

class ProjectorSDK(ABC):
    """Base class for all V2 projectors with HTTP event reception"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_pool = None
        self.running = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = FastAPI(title=f"Projector {self.name}")
        self._setup_routes()
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique projector identifier"""
        pass
        
    @property
    @abstractmethod
    def lens(self) -> str:
        """Target lens: 'rel', 'sem', 'graph'"""
        pass
    
    @abstractmethod
    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to lens with idempotency guarantee"""
        pass
    
    def _setup_routes(self):
        """Setup FastAPI routes for event reception"""
        
        @self.app.post("/events")
        async def receive_event(event_data: EventPayload):
            """Receive event from CDC Publisher"""
            try:
                # Verify payload integrity if hash provided
                if event_data.payload_hash:
                    if not self._verify_payload_hash(event_data.envelope, event_data.payload_hash):
                        raise HTTPException(status_code=400, detail="Payload hash mismatch")
                
                # Apply event idempotently
                await self.apply(event_data.envelope, event_data.global_seq)
                
                # Update watermark after successful processing
                await self.set_watermark(
                    event_data.envelope['world_id'],
                    event_data.envelope['branch'], 
                    event_data.global_seq
                )
                
                self.logger.debug(f"Processed event {event_data.global_seq} for {event_data.envelope['world_id']}/{event_data.envelope['branch']}")
                return {"status": "processed", "global_seq": event_data.global_seq}
                
            except Exception as e:
                self.logger.error(f"Failed to process event {event_data.global_seq}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            watermark_count = await self._get_watermark_count()
            return {
                "service": f"projector-{self.lens}",
                "status": "healthy",
                "projector_name": self.name,
                "lens": self.lens,
                "watermark_count": watermark_count
            }
        
        @self.app.get("/metrics")
        async def metrics():
            """Metrics endpoint for monitoring"""
            return await self._get_metrics_data()
    
    async def start(self):
        """Start projector HTTP server and background tasks"""
        self.running = True
        self.db_pool = await asyncpg.create_pool(self.config['database_url'])
        
        self.logger.info(f"Starting projector {self.name} on port {self.config.get('port', 8000)}")
        
        # Start background monitoring tasks
        background_tasks = [
            asyncio.create_task(self._state_hash_monitor()),
            asyncio.create_task(self._metrics_updater())
        ]
        
        # Start FastAPI server
        config = uvicorn.Config(
            self.app, 
            host="0.0.0.0", 
            port=self.config.get('port', 8000),
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Run server and background tasks concurrently
        await asyncio.gather(
            server.serve(),
            *background_tasks
        )
    
    def _verify_payload_hash(self, envelope: Dict[str, Any], expected_hash: str) -> bool:
        """Verify payload integrity against expected hash"""
        # Remove server-added fields for canonical hashing
        canonical_envelope = {k: v for k, v in envelope.items() 
                             if k not in ['received_at', 'payload_hash']}
        
        canonical_json = json.dumps(canonical_envelope, sort_keys=True, separators=(',', ':'))
        computed_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        return computed_hash == expected_hash
    
    async def _get_watermark_count(self) -> int:
        """Get total number of watermarks tracked by this projector"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*) FROM event_core.projector_watermarks 
                WHERE projector_name = $1
            """, self.name) or 0
    
    async def _get_metrics_data(self) -> Dict[str, Any]:
        """Get current metrics data for monitoring"""
        async with self.db_pool.acquire() as conn:
            watermarks = await conn.fetch("""
                SELECT world_id, branch, last_processed_seq, updated_at
                FROM event_core.projector_watermarks 
                WHERE projector_name = $1
                ORDER BY updated_at DESC
            """, self.name)
            
            return {
                "projector_name": self.name,
                "lens": self.lens,
                "watermark_count": len(watermarks),
                "watermarks": [dict(w) for w in watermarks],
                "last_activity": watermarks[0]["updated_at"].isoformat() if watermarks else None
            }
    
    async def _state_hash_monitor(self):
        """Background task to monitor state hashing"""
        while self.running:
            try:
                # Implementation specific to projector type
                await asyncio.sleep(self.config.get('state_hash_interval_s', 300))
            except Exception as e:
                self.logger.error(f"State hash monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _metrics_updater(self):
        """Background task to update metrics"""
        while self.running:
            try:
                # Update Prometheus metrics here
                await asyncio.sleep(self.config.get('metrics_update_interval_s', 30))
            except Exception as e:
                self.logger.error(f"Metrics update error: {e}")
                await asyncio.sleep(60)
    
    async def get_watermark(self, world_id: str, branch: str) -> int:
        """Get current processing watermark for (world_id, branch)"""
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT last_processed_seq 
                FROM event_core.projector_watermarks 
                WHERE projector_name = $1 AND world_id = $2 AND branch = $3
            """, self.name, world_id, branch)
            
            return result or 0
    
    async def set_watermark(self, world_id: str, branch: str, global_seq: int) -> None:
        """Update processing watermark for (world_id, branch)"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO event_core.projector_watermarks 
                (projector_name, world_id, branch, last_processed_seq, updated_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (projector_name, world_id, branch) 
                DO UPDATE SET 
                    last_processed_seq = EXCLUDED.last_processed_seq,
                    updated_at = EXCLUDED.updated_at
            """, self.name, world_id, branch, global_seq)
    
    async def compute_state_hash(self, world_id: str, branch: str) -> str:
        """Compute deterministic state hash for replay validation"""
        # Base implementation - subclasses can override for lens-specific logic
        async with self.db_pool.acquire() as conn:
            # Get deterministic snapshot of projector state
            state_data = await self._get_state_snapshot(conn, world_id, branch)
            
            # Create canonical hash
            canonical = json.dumps(state_data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    @abstractmethod
    async def _get_state_snapshot(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str
    ) -> Dict[str, Any]:
        """Get deterministic snapshot of projector state for hashing"""
        pass
```

### **2. Relational Projector Implementation** (`projectors/relational/projector.py`)
```python
from projectors.sdk.projector import ProjectorSDK
from typing import Dict, Any
import asyncpg
import json
from datetime import datetime

class RelationalProjector(ProjectorSDK):
    """Relational lens projector implementation"""
    
    @property
    def name(self) -> str:
        return "projector_rel"
    
    @property 
    def lens(self) -> str:
        return "rel"
    
    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to relational lens with idempotency"""
        kind = envelope['kind']
        payload = envelope['payload']
        world_id = envelope['world_id']
        branch = envelope['branch']
        
        async with self.db_pool.acquire() as conn:
            if kind == 'note.created':
                await self._handle_note_created(conn, world_id, branch, payload)
            elif kind == 'note.updated':
                await self._handle_note_updated(conn, world_id, branch, payload)
            elif kind == 'tag.added':
                await self._handle_tag_added(conn, world_id, branch, payload)
            elif kind == 'tag.removed':
                await self._handle_tag_removed(conn, world_id, branch, payload)
            elif kind == 'link.added':
                await self._handle_link_added(conn, world_id, branch, payload)
            # ... other event handlers
    
    async def _handle_note_created(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        payload: Dict[str, Any]
    ):
        """Handle note.created event idempotently"""
        await conn.execute("""
            INSERT INTO lens_rel.note (
                world_id, branch, note_id, title, body, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, COALESCE($6::timestamptz, now()), COALESCE($6::timestamptz, now()))
            ON CONFLICT (world_id, branch, note_id) DO NOTHING
        """, 
            world_id,
            branch, 
            payload['id'],
            payload['title'],
            payload.get('body', ''),
            payload.get('created_at'),
        )
    
    async def _handle_note_updated(
        self, 
        conn: asyncpg.Connection,
        world_id: str,
        branch: str, 
        payload: Dict[str, Any]
    ):
        """Handle note.updated event idempotently"""
        await conn.execute("""
            UPDATE lens_rel.note 
            SET title = $4, body = $5, updated_at = COALESCE($6::timestamptz, now())
            WHERE world_id = $1 AND branch = $2 AND note_id = $3
        """,
            world_id,
            branch,
            payload['id'],
            payload['title'],
            payload.get('body', ''),
            payload.get('updated_at')
        )
    
    async def _get_state_snapshot(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str
    ) -> Dict[str, Any]:
        """Get deterministic relational lens state snapshot"""
        
        # Get sorted note data for deterministic hash
        notes = await conn.fetch("""
            SELECT note_id, title, body, created_at, updated_at
            FROM lens_rel.note
            WHERE world_id = $1 AND branch = $2
            ORDER BY note_id
        """, world_id, branch)
        
        # Get sorted tag data
        tags = await conn.fetch("""
            SELECT note_id, tag, applied_at
            FROM lens_rel.note_tag
            WHERE world_id = $1 AND branch = $2  
            ORDER BY note_id, tag
        """, world_id, branch)
        
        # Get sorted link data
        links = await conn.fetch("""
            SELECT src_id, dst_id, link_type, created_at
            FROM lens_rel.link
            WHERE world_id = $1 AND branch = $2
            ORDER BY src_id, dst_id, link_type
        """, world_id, branch)
        
        return {
            'lens': 'relational',
            'world_id': world_id,
            'branch': branch,
            'notes': [dict(note) for note in notes],
            'tags': [dict(tag) for tag in tags], 
            'links': [dict(link) for link in links]
        }
```

### **3. Projector Health Monitoring** (`projectors/sdk/monitoring.py`)
```python
from prometheus_client import Counter, Gauge, Histogram
import asyncio
import asyncpg

class ProjectorMetrics:
    """Prometheus metrics for projector monitoring"""
    
    def __init__(self, projector_name: str):
        self.projector_name = projector_name
        
        self.events_processed = Counter(
            'projector_events_processed_total',
            'Total events processed by projector',
            ['projector', 'world_id', 'branch', 'kind']
        )
        
        self.processing_lag = Gauge(
            'projector_lag_seconds',
            'Time lag between event creation and processing',
            ['projector', 'world_id', 'branch']
        )
        
        self.watermark_position = Gauge(
            'projector_watermark',
            'Current watermark position',
            ['projector', 'world_id', 'branch']
        )
        
        self.state_hash = Gauge(
            'projector_state_hash',
            'Numeric representation of state hash for monitoring',
            ['projector', 'world_id', 'branch']
        )
        
        self.processing_duration = Histogram(
            'projector_event_duration_seconds',
            'Time taken to process individual events',
            ['projector', 'kind']
        )
    
    def record_event_processed(
        self, 
        world_id: str, 
        branch: str, 
        kind: str, 
        duration: float
    ):
        """Record successful event processing"""
        self.events_processed.labels(
            projector=self.projector_name,
            world_id=world_id,
            branch=branch,
            kind=kind
        ).inc()
        
        self.processing_duration.labels(
            projector=self.projector_name,
            kind=kind
        ).observe(duration)
    
    async def update_lag_metrics(self, db_pool: asyncpg.Pool):
        """Periodically update lag and watermark metrics"""
        while True:
            try:
                async with db_pool.acquire() as conn:
                    # Get lag data per (world_id, branch)
                    lag_data = await conn.fetch("""
                        SELECT 
                            w.world_id,
                            w.branch,
                            w.last_processed_seq as watermark,
                            COALESCE(
                                EXTRACT(EPOCH FROM (now() - MAX(el.received_at))), 
                                0
                            ) as lag_seconds
                        FROM event_core.projector_watermarks w
                        LEFT JOIN event_core.event_log el ON (
                            el.world_id = w.world_id 
                            AND el.branch = w.branch 
                            AND el.global_seq <= w.last_processed_seq
                        )
                        WHERE w.projector_name = $1
                        GROUP BY w.world_id, w.branch, w.last_processed_seq
                    """, self.projector_name)
                    
                    for row in lag_data:
                        self.processing_lag.labels(
                            projector=self.projector_name,
                            world_id=str(row['world_id']),
                            branch=row['branch']
                        ).set(row['lag_seconds'])
                        
                        self.watermark_position.labels(
                            projector=self.projector_name,
                            world_id=str(row['world_id']),
                            branch=row['branch']
                        ).set(row['watermark'])
                        
            except Exception as e:
                logging.error(f"Metrics update failed: {e}")
                
            await asyncio.sleep(30)
```

### **4. Projector Configuration** (`projectors/sdk/config.py`)
```python
from pydantic import BaseSettings
from typing import Optional

class ProjectorConfig(BaseSettings):
    """Base configuration for all projectors"""
    
    # Database
    database_url: str = "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2"
    
    # HTTP Server
    port: int = 8000
    host: str = "0.0.0.0"
    
    # Health monitoring
    health_check_interval_s: int = 30
    
    # Reliability
    max_retry_attempts: int = 3
    error_backoff_seconds: int = 5
    
    # State management
    state_hash_interval_s: int = 300  # 5 minutes
    
    # Metrics
    metrics_update_interval_s: int = 30
    
    class Config:
        env_prefix = "PROJECTOR_"
```

### **5. Projector Service Template** (`projectors/relational/main.py`)
```python
import asyncio
import logging
from projectors.relational.projector import RelationalProjector
from projectors.sdk.config import ProjectorConfig

async def main():
    """Main entry point for relational projector"""
    logging.basicConfig(level=logging.INFO)
    
    config = ProjectorConfig()
    projector = RelationalProjector(config.dict())
    
    # Start projector HTTP server with integrated health/metrics
    await projector.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### **6. Requirements** (`projectors/relational/requirements.txt`)
```
asyncpg==0.30.0
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
prometheus-client==0.20.0
```

### **7. Docker Configuration** (`projectors/relational/Dockerfile`)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check via FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run projector
CMD ["python", "main.py"]
```

---

## ✅ **Acceptance Criteria**

### **SDK Framework**
- [ ] ProjectorSDK provides complete standardized interface
- [ ] Watermark management works reliably across restarts
- [ ] Idempotent event processing prevents duplicate application
- [ ] State hashing produces deterministic, collision-resistant results

### **Event Processing**
- [ ] Events processed in strict global_seq order per (world_id, branch)
- [ ] Batch processing maintains transactional consistency
- [ ] Error handling includes retry logic and graceful degradation
- [ ] Payload integrity verification detects corruption

### **Monitoring Integration**
- [ ] Prometheus metrics expose lag, throughput, and watermark position
- [ ] Health endpoints return detailed projector status
- [ ] State hash monitoring detects replay inconsistencies
- [ ] Error rates and processing duration tracked accurately

### **Relational Implementation**
- [ ] RelationalProjector handles all core event types
- [ ] Database operations are idempotent and conflict-safe
- [ ] State snapshot generation is deterministic
- [ ] Integration with Phase A2 schema works correctly

---

## 🚧 **Implementation Steps**

### **Step 1: Core SDK Framework**
1. Implement ProjectorSDK abstract base class with FastAPI HTTP server
2. Add watermark management with database persistence
3. Create HTTP event reception endpoints (`/events`, `/health`, `/metrics`)
4. Test framework with mock projector implementation

### **Step 2: HTTP Integration**
1. Implement EventPayload model for CDC Publisher integration
2. Add payload hash verification for integrity checking
3. Create error handling for HTTP event reception
4. Test HTTP endpoint with CDC Publisher events

### **Step 3: Monitoring and Health**
1. Integrate Prometheus metrics into FastAPI endpoints
2. Add health check endpoints with watermark status
3. Create state hash computation and monitoring
4. Test monitoring integration

### **Step 4: Relational Projector**
1. Implement RelationalProjector with HTTP event handlers
2. Add idempotent database operations for lens_rel tables
3. Create deterministic state snapshot generation
4. Test with Phase A2 schema and Phase A4 publisher integration

### **Step 5: Service Integration**
1. Create service templates with FastAPI/uvicorn and Docker configurations
2. Add Makefile targets for projector management
3. Update docker-compose.yml with projector services
4. Test complete event flow: Gateway → Outbox → Publisher → Projector

---

## 🔧 **Technical Decisions**

### **Event Reception Architecture**
- **HTTP Server**: FastAPI-based HTTP server for receiving events from CDC Publisher
- **Push Model**: Events are pushed from Publisher, not pulled by Projector
- **Integration**: Aligns with Phase A4 CDC Publisher HTTP delivery mechanism

### **Watermark Strategy**
- **Per-Branch Tracking**: Separate watermarks for each (world_id, branch)
- **HTTP-Based Updates**: Update watermark after each successfully processed HTTP event
- **Persistence**: Store in shared projector_watermarks table

### **Idempotency Approach**
- **Database-Level**: Use UPSERT/ON CONFLICT for safe retries
- **HTTP-Level**: Return 200 for successfully processed events, 500 for failures
- **State-Level**: Deterministic state hashing for replay validation

### **Error Handling**
- **HTTP Response Codes**: Return appropriate HTTP status for Publisher retry logic
- **Payload Verification**: Verify payload hash on event reception
- **Graceful Degradation**: Continue processing other events on single-event failures
- **Observability**: Comprehensive logging and metrics via FastAPI endpoints

---

## 🚨 **Risks & Mitigations**

### **Processing Lag**
- **Risk**: Projectors fall behind under high event volume
- **Mitigation**: Batch processing, performance monitoring, auto-scaling hooks

### **State Inconsistency**
- **Risk**: Replay produces different state than original processing
- **Mitigation**: Deterministic state hashing, comprehensive testing

### **Resource Leaks**
- **Risk**: Long-running projectors accumulate memory/connections
- **Mitigation**: Proper resource cleanup, connection pooling, health monitoring

---

## 📊 **Success Metrics**

- **Processing Latency**: p95 < 1 second under normal load
- **Throughput**: Handle 1000+ events/second per projector
- **Reliability**: 99.9% successful event processing rate
- **Determinism**: 100% consistent replay hash across runs

---

## 🔄 **Next Phase**

**Phase A6**: Gateway 409 Handling
- Implement FastAPI Gateway with idempotency
- Add request validation and error handling
- Create complete API endpoint implementations

**Dependencies**: A5 projector SDK enables testing of complete event flow from A6 Gateway through A4 Publisher to projectors

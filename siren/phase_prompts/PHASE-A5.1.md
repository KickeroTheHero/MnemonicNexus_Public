# PHASE A5.1: Graph Projector with AGE Backend

**Objective**: Implement production-ready graph projector using Apache AGE for event-driven graph construction

**Prerequisites**: Phase A2.2 complete ✅ (AGE integration tested and validated), Phase A3 complete (Event envelope validation operational)

---

## 🎯 **Goals**

### **Primary**
- Implement full graph projector using AGE backend
- Process V2 events into world/branch-isolated AGE graphs
- Complete GraphAdapter interface with AGE implementation
- Establish graph-based queries and analytics capabilities

### **Non-Goals**
- Neo4j adapter implementation (future phase)
- Advanced graph algorithms (Phase B scope)
- Real-time graph analytics (Phase B scope)
- Graph visualization interfaces

---

## 📋 **Deliverables**

### **1. Graph Projector Service** (`services/projector-graph-v2/`)

#### **Main Service** (`services/projector-graph-v2/main.py`)
```python
"""
MnemonicNexus V2 Graph Projector with AGE Backend
Processes events from the event log into AGE graphs with world/branch isolation
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.common.projector_sdk import ProjectorBase, EventEnvelope
from services.common.graph_adapter import GraphAdapter, AGEGraphAdapter

logger = logging.getLogger(__name__)

class GraphProjectorV2(ProjectorBase):
    """AGE-based graph projector for V2 events"""
    
    def __init__(self, db_pool: asyncpg.Pool, graph_adapter: GraphAdapter):
        super().__init__(
            name="graph-projector-v2",
            db_pool=db_pool,
            supported_events=[
                "note.created", "note.updated", "note.deleted",
                "tag.applied", "tag.removed",
                "link.created", "link.deleted"
            ]
        )
        self.graph_adapter = graph_adapter
        
    async def process_event(self, event: EventEnvelope) -> bool:
        """Process single event into AGE graph"""
        try:
            world_id = UUID(event.world_id)
            branch = event.branch
            
            # Ensure graph exists for this world/branch
            await self.graph_adapter.ensure_graph_exists(world_id, branch)
            
            # Route event to appropriate handler
            if event.kind.startswith("note."):
                return await self._handle_note_event(event)
            elif event.kind.startswith("tag."):
                return await self._handle_tag_event(event)
            elif event.kind.startswith("link."):
                return await self._handle_link_event(event)
            else:
                logger.warning(f"Unhandled event kind: {event.kind}")
                return True  # Skip unknown events
                
        except Exception as e:
            logger.error(f"Error processing event {event.kind} for world {event.world_id}: {e}")
            return False
            
    async def _handle_note_event(self, event: EventEnvelope) -> bool:
        """Handle note lifecycle events"""
        world_id = UUID(event.world_id)
        branch = event.branch
        payload = event.payload
        
        if event.kind == "note.created":
            cypher = '''
            CREATE (n:Note {
                note_id: $note_id,
                title: $title,
                created_at: $created_at,
                world_id: $world_id,
                branch: $branch,
                entity_type: 'note'
            })
            RETURN n
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "note_id": payload["note_id"],
                    "title": payload["title"],
                    "created_at": event.occurred_at,
                    "world_id": str(world_id),
                    "branch": branch
                }
            )
            return True
            
        elif event.kind == "note.updated":
            cypher = '''
            MATCH (n:Note {note_id: $note_id})
            SET n.title = $title,
                n.updated_at = $updated_at
            RETURN n
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "note_id": payload["note_id"],
                    "title": payload.get("title"),
                    "updated_at": event.occurred_at
                }
            )
            return True
            
        elif event.kind == "note.deleted":
            cypher = '''
            MATCH (n:Note {note_id: $note_id})
            DELETE n
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "note_id": payload["note_id"]
                }
            )
            return True
            
        return True
        
    async def _handle_tag_event(self, event: EventEnvelope) -> bool:
        """Handle tag events"""
        world_id = UUID(event.world_id)
        branch = event.branch
        payload = event.payload
        
        if event.kind == "tag.applied":
            cypher = '''
            MERGE (t:Tag {tag: $tag, world_id: $world_id, branch: $branch})
            ON CREATE SET t.entity_type = 'tag'
            WITH t
            MATCH (n:Note {note_id: $note_id})
            CREATE (n)-[r:TAGGED {
                applied_at: $applied_at,
                world_id: $world_id,
                branch: $branch
            }]->(t)
            RETURN r
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "tag": payload["tag"],
                    "note_id": payload["note_id"],
                    "applied_at": event.occurred_at,
                    "world_id": str(world_id),
                    "branch": branch
                }
            )
            return True
            
        elif event.kind == "tag.removed":
            cypher = '''
            MATCH (n:Note {note_id: $note_id})-[r:TAGGED]->(t:Tag {tag: $tag})
            DELETE r
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "note_id": payload["note_id"],
                    "tag": payload["tag"]
                }
            )
            return True
            
        return True
        
    async def _handle_link_event(self, event: EventEnvelope) -> bool:
        """Handle note linking events"""
        world_id = UUID(event.world_id)
        branch = event.branch
        payload = event.payload
        
        if event.kind == "link.created":
            cypher = '''
            MATCH (src:Note {note_id: $src_note_id}), (dst:Note {note_id: $dst_note_id})
            CREATE (src)-[r:LINKS_TO {
                link_type: $link_type,
                created_at: $created_at,
                world_id: $world_id,
                branch: $branch
            }]->(dst)
            RETURN r
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "src_note_id": payload["src_note_id"],
                    "dst_note_id": payload["dst_note_id"],
                    "link_type": payload.get("link_type", "reference"),
                    "created_at": event.occurred_at,
                    "world_id": str(world_id),
                    "branch": branch
                }
            )
            return True
            
        elif event.kind == "link.deleted":
            cypher = '''
            MATCH (src:Note {note_id: $src_note_id})-[r:LINKS_TO]->(dst:Note {note_id: $dst_note_id})
            DELETE r
            '''
            
            await self.graph_adapter.execute_cypher(
                world_id, branch, cypher, {
                    "src_note_id": payload["src_note_id"],
                    "dst_note_id": payload["dst_note_id"]
                }
            )
            return True
            
        return True

# FastAPI service setup
app = FastAPI(title="Graph Projector V2", version="2.0.0-dev")

@app.on_event("startup")
async def startup():
    """Initialize projector service"""
    global projector
    
    # Database connection
    db_pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/nexus_v2")
    )
    
    # Graph adapter
    graph_adapter = AGEGraphAdapter(db_pool)
    
    # Projector instance
    projector = GraphProjectorV2(db_pool, graph_adapter)
    
    # Start projector processing loop
    asyncio.create_task(projector.run())
    
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = await projector.get_status()
    return {
        "service": "graph-projector-v2",
        "status": "healthy" if status["healthy"] else "degraded",
        "last_processed_seq": status["watermark"],
        "events_behind": status["lag"],
        "graph_adapter": "AGE"
    }

@app.get("/stats")
async def get_stats():
    """Get projector statistics"""
    return await projector.get_statistics()
```

#### **AGE Graph Adapter** (`services/common/graph_adapter.py`)
```python
"""
GraphAdapter interface and AGE implementation
Provides abstraction layer for graph operations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import json
import logging

import asyncpg

logger = logging.getLogger(__name__)

class GraphAdapter(ABC):
    """Abstract interface for graph database operations"""
    
    @abstractmethod
    async def ensure_graph_exists(self, world_id: UUID, branch: str) -> str:
        """Ensure graph exists for world/branch, return graph name"""
        pass
        
    @abstractmethod
    async def execute_cypher(self, world_id: UUID, branch: str, cypher: str, 
                           parameters: Dict[str, Any] = None) -> Any:
        """Execute Cypher query with world/branch isolation"""
        pass

class AGEGraphAdapter(GraphAdapter):
    """Apache AGE implementation of GraphAdapter"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        
    async def ensure_graph_exists(self, world_id: UUID, branch: str) -> str:
        """Ensure AGE graph exists for world/branch"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT lens_graph.ensure_graph_exists($1, $2)",
                world_id, branch
            )
            
    async def execute_cypher(self, world_id: UUID, branch: str, cypher: str, 
                           parameters: Dict[str, Any] = None) -> Any:
        """Execute Cypher query via V2 wrapper"""
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    "SELECT lens_graph.execute_cypher($1, $2, $3, $4)",
                    world_id, branch, cypher, json.dumps(parameters or {})
                )
                return result
            except Exception as e:
                logger.error(f"Cypher execution failed: {e}")
                logger.error(f"Query: {cypher}")
                logger.error(f"Params: {parameters}")
                raise
```

### **2. Graph Query Interface** (`services/projector-graph-v2/queries.py`)

#### **Graph Analytics Queries**
```python
"""
Graph query library for AGE-based analytics
Provides high-level query interface for graph analysis
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

class GraphQueries:
    """High-level graph query interface"""
    
    def __init__(self, graph_adapter):
        self.adapter = graph_adapter
        
    async def find_connected_notes(self, world_id: UUID, branch: str, 
                                  note_id: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Find notes connected to given note within max_depth"""
        query = f"""
            MATCH (start:Note {{note_id: '{note_id}'}})
            MATCH (start)-[:LINKS_TO*1..{max_depth}]-(connected:Note)
            RETURN DISTINCT connected.note_id as note_id, 
                   connected.title as title,
                   connected.created_at as created_at
        """
        
        return await self.adapter.execute_cypher(world_id, branch, query)
        
    async def find_notes_by_tag(self, world_id: UUID, branch: str, tag: str) -> List[Dict[str, Any]]:
        """Find all notes tagged with specific tag"""
        query = f"""
            MATCH (n:Note)-[:TAGGED]->(t:Tag {{tag: '{tag}'}})
            RETURN n.note_id as note_id, n.title as title, n.created_at as created_at
            ORDER BY n.created_at DESC
        """
        
        return await self.adapter.execute_cypher(world_id, branch, query)
        
    async def find_tag_cooccurrence(self, world_id: UUID, branch: str, tag: str) -> List[Dict[str, Any]]:
        """Find tags that frequently co-occur with given tag"""
        query = f"""
            MATCH (n:Note)-[:TAGGED]->(t1:Tag {{tag: '{tag}'}})
            MATCH (n)-[:TAGGED]->(t2:Tag)
            WHERE t1 <> t2
            RETURN t2.tag as tag, COUNT(n) as cooccurrence_count
            ORDER BY cooccurrence_count DESC
            LIMIT 20
        """
        
        return await self.adapter.execute_cypher(world_id, branch, query)
        

    async def get_graph_statistics(self, world_id: UUID, branch: str) -> Dict[str, Any]:
        """Get comprehensive graph statistics"""
        stats_queries = {
            "node_count": "MATCH (n) RETURN COUNT(n) as count",
            "edge_count": "MATCH ()-[r]->() RETURN COUNT(r) as count",
            "note_count": "MATCH (n:Note) RETURN COUNT(n) as count",
            "tag_count": "MATCH (t:Tag) RETURN COUNT(t) as count",
            "link_count": "MATCH ()-[r:LINKS_TO]->() RETURN COUNT(r) as count",
            "tagged_count": "MATCH ()-[r:TAGGED]->() RETURN COUNT(r) as count"
        }
        
        stats = {}
        for stat_name, query in stats_queries.items():
            result = await self.adapter.execute_cypher(world_id, branch, query)
            stats[stat_name] = result[0]['count'] if result else 0
            
        return stats
```

### **3. Integration Tests** (`tests/graph_projector/`)

#### **Event Processing Tests** (`tests/graph_projector/test_event_processing.py`)
```python
import pytest
from uuid import uuid4, UUID
from datetime import datetime

from services.projector_graph_v2.main import GraphProjectorV2
from services.common.graph_adapter import AGEGraphAdapter
from services.common.projector_sdk import EventEnvelope

class TestGraphProjectorEvents:
    """Test graph projector event processing"""
    
    @pytest.fixture
    async def projector(self, db_pool):
        """Create graph projector instance"""
        adapter = AGEGraphAdapter(db_pool)
        return GraphProjectorV2(db_pool, adapter)
        
    async def test_note_created_event(self, projector):
        """Test note creation creates graph node"""
        world_id = UUID('550e8400-e29b-41d4-a716-446655440000')
        branch = 'test'
        note_id = str(uuid4())
        
        event = EventEnvelope(
            world_id=str(world_id),
            branch=branch,
            kind="note.created",
            payload={
                "note_id": note_id,
                "title": "Test Note",
                "body": "Test content"
            },
            by={"agent": "test"},
            occurred_at=datetime.utcnow(),
            received_at=datetime.utcnow()
        )
        
        # Process event
        success = await projector.process_event(event)
        assert success is True
        
        # Verify node created in graph
        result = await projector.graph_adapter.execute_cypher(
            world_id, branch,
            f"MATCH (n:Note {{note_id: '{note_id}'}}) RETURN n"
        )
        assert len(result) == 1
        assert result[0]['n']['title'] == "Test Note"
        
    async def test_tag_applied_event(self, projector):
        """Test tag application creates nodes and relationships"""
        world_id = UUID('550e8400-e29b-41d4-a716-446655440000')
        branch = 'test'
        note_id = str(uuid4())
        tag = "test-tag"
        
        # First create a note
        note_event = EventEnvelope(
            world_id=str(world_id),
            branch=branch,
            kind="note.created",
            payload={"note_id": note_id, "title": "Tagged Note"},
            by={"agent": "test"}
        )
        await projector.process_event(note_event)
        
        # Then add tag
        tag_event = EventEnvelope(
            world_id=str(world_id),
            branch=branch,
            kind="tag.applied",
            payload={"note_id": note_id, "tag": tag},
            by={"agent": "test"}
        )
        
        success = await projector.process_event(tag_event)
        assert success is True
        
        # Verify tag node and relationship created
        result = await projector.graph_adapter.execute_cypher(
            world_id, branch,
            f"""
            MATCH (n:Note {{note_id: '{note_id}'}})-[:TAGGED]->(t:Tag {{tag: '{tag}'}})
            RETURN n, t
            """
        )
        assert len(result) == 1
        
    async def test_world_branch_isolation(self, projector):
        """Test that different worlds/branches create isolated graphs"""
        world1 = UUID('550e8400-e29b-41d4-a716-446655440000')
        world2 = UUID('deadbeef-dead-beef-dead-beefdeadbeef')
        branch = 'isolation_test'
        
        # Create note in world1
        event1 = EventEnvelope(
            world_id=str(world1),
            branch=branch,
            kind="note.created",
            payload={"note_id": "note1", "title": "World 1 Note"},
            by={"agent": "test"}
        )
        await projector.process_event(event1)
        
        # Create note in world2
        event2 = EventEnvelope(
            world_id=str(world2),
            branch=branch,
            kind="note.created",
            payload={"note_id": "note2", "title": "World 2 Note"},
            by={"agent": "test"}
        )
        await projector.process_event(event2)
        
        # Verify isolation - world1 should only see its note
        result1 = await projector.graph_adapter.execute_cypher(
            world1, branch, "MATCH (n:Note) RETURN n.note_id as note_id"
        )
        assert len(result1) == 1
        assert result1[0]['note_id'] == "note1"
        
        # world2 should only see its note
        result2 = await projector.graph_adapter.execute_cypher(
            world2, branch, "MATCH (n:Note) RETURN n.note_id as note_id"
        )
        assert len(result2) == 1
        assert result2[0]['note_id'] == "note2"
```

---

## ✅ **Acceptance Criteria**

### **Core Functionality**
- [ ] Graph projector processes all V2 event types (note, tag, link, mention)
- [ ] AGE graphs maintain world/branch isolation
- [ ] Event processing is idempotent (re-processing same event safe)
- [ ] Graph state reflects current event log state

### **Performance**
- [ ] Projector keeps up with event stream (< 100ms lag per event)
- [ ] Graph queries perform within acceptable limits (< 1s for basic queries)
- [ ] Memory usage stable under continuous processing
- [ ] No significant impact on database performance

### **Reliability**
- [ ] Projector recovers gracefully from failures
- [ ] Watermark management prevents event loss or duplication
- [ ] Error handling preserves graph consistency
- [ ] Monitoring and alerting functional

### **Integration**
- [ ] GraphAdapter interface complete and testable
- [ ] Integration with V2 event sourcing working
- [ ] Graph queries return correct results
- [ ] Development workflow supports graph operations

---

## 🚧 **Implementation Steps**

### **Step 1: Core Projector Implementation**
1. Implement GraphProjectorV2 with event routing
2. Create event handlers for each event type
3. Integrate with ProjectorSDK watermark management
4. Add comprehensive error handling and logging

### **Step 2: AGE Adapter Implementation**
1. Complete AGEGraphAdapter interface
2. Implement Cypher query building utilities
3. Add proper parameter sanitization and escaping
4. Test all adapter methods with real AGE backend

### **Step 3: Graph Query Interface**
1. Implement high-level query abstractions
2. Create graph analytics and search capabilities
3. Add performance optimization for common patterns
4. Document query patterns and best practices

### **Step 4: Testing and Validation**
1. Create comprehensive test suite for all event types
2. Test world/branch isolation thoroughly
3. Performance testing and benchmarking
4. Integration testing with full V2 stack

---

## 🔧 **Technical Decisions**

### **Event Processing Strategy**
- **Watermark-based**: Use projector SDK for reliable processing
- **Idempotent**: Safe to reprocess events multiple times
- **Typed**: Specific handlers for each event type
- **Isolated**: Separate graphs per world/branch

### **Graph Schema Design**
- **Node Types**: Note, Tag, Person, Organization (extensible)
- **Edge Types**: TAGGED, LINKS_TO, MENTIONS (typed relationships)
- **Properties**: Include world_id, branch for isolation
- **Constraints**: Unique constraints on entity IDs within world/branch

### **Query Performance**
- **Indexing**: AGE indexes on frequently queried properties
- **Caching**: Query result caching for expensive operations
- **Batching**: Bulk operations where possible
- **Monitoring**: Query performance metrics and alerting

---

## 🚨 **Risks & Mitigations**

### **Performance Bottlenecks**
- **Risk**: Graph operations slower than expected
- **Mitigation**: Comprehensive benchmarking, query optimization
- **Fallback**: Optimize query patterns, consider caching

### **Data Consistency**
- **Risk**: Graph state diverges from event log
- **Mitigation**: Idempotent processing, comprehensive testing
- **Recovery**: Projector reset and rebuild capabilities

### **AGE Stability**
- **Risk**: AGE extension issues in production
- **Mitigation**: Extensive testing, monitoring, fallback plans
- **Escalation**: Engage AGE community, consider Neo4j adapter

---

## 📊 **Success Metrics**

- **Event Processing**: > 95% success rate, < 100ms average latency
- **Query Performance**: 90% of queries < 1s response time
- **Data Accuracy**: 100% consistency with event log state
- **Uptime**: > 99.9% availability in production

---

## 🔄 **Next Phase**

**Phase A6: Enhanced Gateway with Graph Endpoints**
- Add graph query endpoints to Gateway API
- Integrate graph search with relational and vector search
- Implement hybrid search combining all three lenses
- Production-ready graph analytics capabilities

**Dependencies**: A5.1 provides production graph functionality for Gateway integration

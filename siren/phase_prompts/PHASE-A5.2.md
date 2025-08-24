# PHASE A5.2: Semantic Projector with pgvector Backend

**Objective**: Implement semantic lens projector with vector embeddings for similarity search and semantic retrieval

**Prerequisites**: Phase A5 complete (Python Projector SDK operational), pgvector extension validated

## 🏗️ **Architecture Integration**

The Semantic Projector integrates with the V2 event flow using vector embeddings:

```
Gateway V2 → CDC Publisher → Semantic Projector → lens_sem.embedding
   ↓             ↓               ↓                    ↓
HTTP Events   HTTP POST      Vector Generation   pgvector Storage
              /events        + Embedding          + Similarity Search
```

**Key Integration Points:**
- **Input**: HTTP POST `/events` from CDC Publisher (Phase A4)
- **Processing**: Extract text, generate embeddings, store vectors
- **Target**: `lens_sem.embedding` table with pgvector support
- **Queries**: Cosine similarity search via `lens_sem.find_similar_embeddings()`

---

## 🎯 **Goals**

### **Primary**
- Implement semantic projector using pgvector for vector storage
- Generate embeddings for note content and metadata
- Enable similarity search and semantic retrieval
- Support configurable embedding models (OpenAI, local, etc.)

### **Non-Goals**
- Embedding model training (use existing models)
- Real-time embedding generation (async processing acceptable)
- Graph relationships (Phase A5.1 scope)

---

## 📋 **Deliverables**

### **1. Semantic Projector Implementation** (`projectors/semantic/projector.py`)
```python
from projectors.sdk.projector import ProjectorSDK
from typing import Dict, Any, List
import asyncpg
import json
import logging
import openai
import numpy as np
from sentence_transformers import SentenceTransformer

class SemanticProjector(ProjectorSDK):
    """Semantic lens projector with vector embeddings"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.embedding_model = self._initialize_embedding_model()
        
    @property
    def name(self) -> str:
        return "projector_sem"
    
    @property 
    def lens(self) -> str:
        return "sem"
    
    def _initialize_embedding_model(self):
        """Initialize embedding model based on configuration"""
        model_type = self.config.get('embedding_model_type', 'sentence-transformer')
        
        if model_type == 'openai':
            openai.api_key = self.config.get('openai_api_key')
            return None  # Use OpenAI API directly
        elif model_type == 'sentence-transformer':
            model_name = self.config.get('sentence_transformer_model', 'all-MiniLM-L6-v2')
            return SentenceTransformer(model_name)
        else:
            raise ValueError(f"Unsupported embedding model type: {model_type}")
    
    async def apply(self, envelope: Dict[str, Any], global_seq: int) -> None:
        """Apply event to semantic lens with vector generation"""
        kind = envelope['kind']
        payload = envelope['payload']
        world_id = envelope['world_id']
        branch = envelope['branch']
        
        async with self.db_pool.acquire() as conn:
            if kind == 'note.created':
                await self._handle_note_created(conn, world_id, branch, payload, global_seq)
            elif kind == 'note.updated':
                await self._handle_note_updated(conn, world_id, branch, payload, global_seq)
            elif kind == 'note.deleted':
                await self._handle_note_deleted(conn, world_id, branch, payload)
            elif kind == 'tag.applied':
                await self._handle_tag_applied(conn, world_id, branch, payload, global_seq)
            # Handle other events that affect semantic representation
    
    async def _handle_note_created(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        payload: Dict[str, Any],
        global_seq: int
    ):
        """Generate and store embeddings for new note"""
        note_id = payload['id']
        title = payload.get('title', '')
        body = payload.get('body', '')
        
        # Generate embeddings for different text components
        embeddings_to_store = []
        
        # Title embedding
        if title:
            title_embedding = await self._generate_embedding(title)
            embeddings_to_store.append({
                'entity_id': note_id,
                'entity_type': 'note_title',
                'text_content': title,
                'embedding': title_embedding
            })
        
        # Body embedding
        if body:
            body_embedding = await self._generate_embedding(body)
            embeddings_to_store.append({
                'entity_id': note_id,
                'entity_type': 'note_body', 
                'text_content': body,
                'embedding': body_embedding
            })
        
        # Combined embedding for full-text search
        if title or body:
            combined_text = f"{title}\n{body}".strip()
            combined_embedding = await self._generate_embedding(combined_text)
            embeddings_to_store.append({
                'entity_id': note_id,
                'entity_type': 'note_full',
                'text_content': combined_text,
                'embedding': combined_embedding
            })
        
        # Store all embeddings
        for emb_data in embeddings_to_store:
            await self._store_embedding(conn, world_id, branch, emb_data, global_seq)
    
    async def _handle_note_updated(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        payload: Dict[str, Any],
        global_seq: int
    ):
        """Update embeddings for modified note"""
        note_id = payload['id']
        
        # Delete existing embeddings for this note
        await conn.execute("""
            DELETE FROM lens_sem.embedding 
            WHERE world_id = $1 AND branch = $2 AND entity_id = $3
        """, world_id, branch, note_id)
        
        # Regenerate embeddings (same logic as create)
        await self._handle_note_created(conn, world_id, branch, payload, global_seq)
    
    async def _handle_note_deleted(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        payload: Dict[str, Any]
    ):
        """Remove embeddings for deleted note"""
        note_id = payload['id']
        
        await conn.execute("""
            DELETE FROM lens_sem.embedding 
            WHERE world_id = $1 AND branch = $2 AND entity_id = $3
        """, world_id, branch, note_id)
    
    async def _handle_tag_applied(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        payload: Dict[str, Any],
        global_seq: int
    ):
        """Generate embeddings for tag semantic relationships"""
        note_id = payload['note_id']
        tag = payload['tag']
        
        # Generate embedding for tag in context
        tag_embedding = await self._generate_embedding(f"tag:{tag}")
        
        await self._store_embedding(
            conn, world_id, branch, {
                'entity_id': f"{note_id}:{tag}",
                'entity_type': 'note_tag',
                'text_content': tag,
                'embedding': tag_embedding
            }, global_seq
        )
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text"""
        model_type = self.config.get('embedding_model_type', 'sentence-transformer')
        
        if model_type == 'openai':
            response = await openai.Embedding.acreate(
                model=self.config.get('openai_model', 'text-embedding-ada-002'),
                input=text
            )
            return response['data'][0]['embedding']
        
        elif model_type == 'sentence-transformer':
            # Run embedding generation in thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, 
                lambda: self.embedding_model.encode(text).tolist()
            )
            return embedding
        
        else:
            raise ValueError(f"Unsupported embedding model: {model_type}")
    
    async def _store_embedding(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str, 
        embedding_data: Dict[str, Any],
        global_seq: int
    ):
        """Store embedding in lens_sem.embedding table"""
        model_config = self._get_model_info()
        
        await conn.execute("""
            INSERT INTO lens_sem.embedding (
                world_id, branch, entity_id, entity_type, 
                text_content, embedding, model_name, model_version,
                created_at, source_seq
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), $9)
            ON CONFLICT (world_id, branch, entity_id, entity_type) 
            DO UPDATE SET 
                text_content = EXCLUDED.text_content,
                embedding = EXCLUDED.embedding,
                model_name = EXCLUDED.model_name,
                model_version = EXCLUDED.model_version,
                created_at = EXCLUDED.created_at,
                source_seq = EXCLUDED.source_seq
        """, 
            world_id,
            branch,
            embedding_data['entity_id'],
            embedding_data['entity_type'],
            embedding_data['text_content'],
            embedding_data['embedding'],
            model_config['name'],
            model_config['version'],
            global_seq
        )
    
    def _get_model_info(self) -> Dict[str, str]:
        """Get current model name and version for tracking"""
        model_type = self.config.get('embedding_model_type', 'sentence-transformer')
        
        if model_type == 'openai':
            return {
                'name': self.config.get('openai_model', 'text-embedding-ada-002'),
                'version': 'openai-api'
            }
        elif model_type == 'sentence-transformer':
            model_name = self.config.get('sentence_transformer_model', 'all-MiniLM-L6-v2')
            return {
                'name': model_name,
                'version': 'sentence-transformers'
            }
        
        return {'name': 'unknown', 'version': 'unknown'}
    
    async def _get_state_snapshot(
        self, 
        conn: asyncpg.Connection, 
        world_id: str, 
        branch: str
    ) -> Dict[str, Any]:
        """Get deterministic semantic lens state snapshot"""
        
        # Get sorted embedding data for deterministic hash
        embeddings = await conn.fetch("""
            SELECT entity_id, entity_type, text_content, model_name, model_version, created_at
            FROM lens_sem.embedding
            WHERE world_id = $1 AND branch = $2
            ORDER BY entity_id, entity_type
        """, world_id, branch)
        
        return {
            'lens': 'semantic',
            'world_id': world_id,
            'branch': branch,
            'embedding_count': len(embeddings),
            'embeddings': [dict(emb) for emb in embeddings],
            'model_info': self._get_model_info()
        }
```

### **2. Semantic Query Interface** (`projectors/semantic/queries.py`)
```python
from typing import List, Dict, Any, Optional
import asyncpg

class SemanticQueryInterface:
    """Interface for semantic similarity queries"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
    
    async def find_similar_notes(
        self, 
        world_id: str, 
        branch: str,
        query_text: str,
        similarity_threshold: float = 0.7,
        limit: int = 10,
        embedding_generator = None
    ) -> List[Dict[str, Any]]:
        """Find notes semantically similar to query text"""
        
        # Generate embedding for query
        query_embedding = await embedding_generator(query_text)
        
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM lens_sem.find_similar_embeddings(
                    $1::uuid, $2::text, $3::vector, $4::float, $5::int
                )
            """, world_id, branch, query_embedding, similarity_threshold, limit)
            
            return [dict(result) for result in results]
    
    async def get_embedding_stats(
        self, 
        world_id: str, 
        branch: str
    ) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_embeddings,
                    COUNT(DISTINCT entity_id) as unique_entities,
                    COUNT(DISTINCT entity_type) as entity_types,
                    COUNT(DISTINCT model_name) as model_count,
                    MIN(created_at) as first_embedding,
                    MAX(created_at) as latest_embedding
                FROM lens_sem.embedding
                WHERE world_id = $1 AND branch = $2
            """, world_id, branch)
            
            return dict(stats) if stats else {}
```

### **3. Configuration** (`projectors/semantic/config.py`)
```python
from projectors.sdk.config import ProjectorConfig
from typing import Optional

class SemanticProjectorConfig(ProjectorConfig):
    """Configuration for semantic projector"""
    
    # Embedding model configuration
    embedding_model_type: str = "sentence-transformer"  # "openai" or "sentence-transformer"
    
    # OpenAI configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "text-embedding-ada-002"
    
    # Sentence Transformer configuration
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    
    # Processing configuration
    max_text_length: int = 8192  # Maximum text length for embedding
    batch_embedding_size: int = 10  # Batch size for embedding generation
    
    # Vector storage
    vector_dimensions: int = 768  # Default for all-MiniLM-L6-v2
    
    class Config:
        env_prefix = "SEMANTIC_"
```

### **4. Service Template** (`projectors/semantic/main.py`)
```python
import asyncio
import logging
from projectors.semantic.projector import SemanticProjector
from projectors.semantic.config import SemanticProjectorConfig

async def main():
    """Main entry point for semantic projector"""
    logging.basicConfig(level=logging.INFO)
    
    config = SemanticProjectorConfig()
    projector = SemanticProjector(config.dict())
    
    # Start semantic projector HTTP server
    await projector.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### **5. Requirements** (`projectors/semantic/requirements.txt`)
```
# Base projector dependencies
asyncpg==0.30.0
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
prometheus-client==0.20.0

# Semantic/ML dependencies
sentence-transformers==2.2.2
openai==1.3.8
numpy==1.24.3
torch==2.1.0
transformers==4.35.2
```

### **6. Docker Configuration** (`projectors/semantic/Dockerfile`)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check via FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run semantic projector
CMD ["python", "main.py"]
```

---

## ✅ **Acceptance Criteria**

### **Embedding Generation**
- [ ] Support multiple embedding models (OpenAI, Sentence Transformers)
- [ ] Generate embeddings for note titles, bodies, and tags
- [ ] Handle text preprocessing and chunking for long content
- [ ] Store embeddings with model versioning for consistency

### **Vector Storage**
- [ ] Integrate with pgvector for efficient vector storage
- [ ] Support cosine similarity search via database functions
- [ ] Handle embedding updates when content changes
- [ ] Maintain referential integrity with source events

### **Similarity Search**
- [ ] Implement semantic similarity queries with configurable thresholds
- [ ] Support batch similarity operations
- [ ] Provide query performance within acceptable latencies
- [ ] Return results with similarity scores and metadata

### **Integration**
- [ ] Process events from CDC Publisher via HTTP endpoints
- [ ] Update watermarks after successful embedding generation
- [ ] Handle embedding model changes gracefully
- [ ] Integrate with existing lens_sem schema and functions

---

## 🚧 **Implementation Steps**

### **Step 1: Basic Embedding Generation**
1. Implement SemanticProjector with sentence-transformers support
2. Add text preprocessing and embedding generation
3. Test embedding storage in lens_sem.embedding table
4. Validate vector similarity search functionality

### **Step 2: Multi-Model Support**
1. Add OpenAI embedding API integration
2. Implement configurable model switching
3. Add model versioning and tracking
4. Test consistency across different models

### **Step 3: Event Processing**
1. Implement note.created/updated/deleted handlers
2. Add tag embedding generation
3. Handle batch embedding operations
4. Test integration with CDC Publisher events

### **Step 4: Query Interface**
1. Implement semantic similarity search
2. Add embedding statistics and monitoring
3. Create query optimization and caching
4. Test performance with realistic data volumes

### **Step 5: Production Readiness**
1. Add comprehensive error handling and retries
2. Implement embedding generation monitoring
3. Create Docker deployment with ML dependencies
4. Test full stack integration and performance

---

## 🔧 **Technical Decisions**

### **Embedding Strategy**
- **Multi-Model Support**: Support both OpenAI and local models for flexibility
- **Granular Embeddings**: Store separate embeddings for titles, bodies, and tags
- **Model Versioning**: Track embedding model for consistency during upgrades

### **Performance Optimization**
- **Async Processing**: Non-blocking embedding generation using thread pools
- **Batch Operations**: Process multiple embeddings efficiently
- **Vector Indexing**: Leverage pgvector's optimized similarity search

### **Data Management**
- **Incremental Updates**: Update embeddings only when content changes
- **Model Migration**: Support embedding regeneration for model upgrades
- **Cleanup**: Remove embeddings when source entities are deleted

---

## 🚨 **Risks & Mitigations**

### **Embedding Quality**
- **Risk**: Poor quality embeddings reduce semantic search effectiveness
- **Mitigation**: Support multiple models, configurable preprocessing, quality metrics

### **Performance Impact**
- **Risk**: Embedding generation adds significant latency
- **Mitigation**: Async processing, batch operations, local model options

### **Storage Growth**
- **Risk**: Vector storage requirements grow rapidly with content
- **Mitigation**: Configurable retention, efficient vector compression, monitoring

---

## 📊 **Success Metrics**

- **Embedding Latency**: p95 < 2 seconds for note embedding generation
- **Search Quality**: Semantic similarity results demonstrate clear relevance
- **Storage Efficiency**: Vector storage growth remains manageable
- **Integration**: Seamless event processing from CDC Publisher

---

## 🔄 **Next Phase**

**Phase A6**: Gateway V2 with Enhanced Query API
- Multi-lens query coordination
- Semantic search endpoints
- Cross-lens result fusion

**Dependencies**: A5.2 semantic projector enables semantic search capabilities in A6 Gateway

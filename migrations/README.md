# MnemonicNexus Database Migrations

**Phase A2: Schema & Event Envelope Implementation**

This directory contains the complete database schema migrations for MnemonicNexus.

## Migration Files

### Core Infrastructure
- **`001_event_core.sql`** - Event log, branches, and core utilities
- **`002_outbox.sql`** - Transactional outbox pattern for reliable CDC
- **`005_watermarks.sql`** - Projector watermark tracking and determinism validation

### Multi-Lens Architecture
- **`003_lens_foundation.sql`** - All lens schemas (relational, semantic, graph)
- **`004_age_setup.sql`** - Apache AGE graph extension integration

## Quick Start

```bash
# Start infrastructure (PostgreSQL + pgvector)
cd infra
docker-compose up -d

# Run all migrations
for file in ../migrations/*.sql; do
  psql postgresql://postgres:postgres@localhost:5433/nexus -f "$file"
done

# Test schema functionality
# Use individual migration test queries or golden tests
```

## Schema Overview

### Event Core (`event_core` schema)
- **`event_log`** - Append-only event storage with tenancy
- **`outbox`** - Transactional outbox for reliable event publishing
- **`dead_letter_queue`** - Failed event handling
- **`branches`** - DVCS-lite branch registry
- **`projector_watermarks`** - Projector state tracking
- **`determinism_log`** - Replay validation logs

### Relational Lens (`lens_rel` schema)
- **`note`** - Core note entities with world/branch tenancy
- **`note_tag`** - Note tagging system
- **`link`** - Inter-note relationships
- **`mv_note_enriched`** - Materialized view (MV discipline)

### Semantic Lens (`lens_sem` schema)
- **`embedding`** - Vector embeddings with pgvector integration
- Vector indexes: `ivfflat` for cosine similarity search

### Graph Lens (`lens_graph` schema)
- **`projector_state`** - Graph projector tracking
- **`graph_metadata`** - AGE graph registry and naming
- **`operation_log`** - Graph operation audit log

## Key Features

### Tenancy & Isolation
- All tables include `(world_id, branch)` composite keys
- Row Level Security (RLS) enabled for multi-tenancy
- Complete isolation between worlds and branches

### Idempotency & Reliability
- Partial unique constraint on `(world_id, branch, idempotency_key)`
- Transactional outbox pattern for exactly-once semantics
- Dead letter queue for poison message handling

### Performance & Scalability
- Comprehensive indexing strategy for tenant-scoped queries
- pgvector IVFFlat indexes for semantic similarity
- Materialized views following MV discipline

### Deterministic Replay
- Determinism hash computation for event ranges
- Projector watermark management with integrity validation
- Crash-safe event processing guarantees

### Graph Operations
- Apache AGE integration with world/branch graph isolation
- Graph naming convention: `g_{world_prefix}_{branch}`
- GraphAdapter interface for pluggable engines

## Validation

Each migration includes comprehensive validation:
- Schema existence verification
- Function creation validation
- Index and constraint verification
- Basic functionality testing
- Error handling and rollback safety

## Dependencies

### Required Extensions
- **`uuid-ossp`** - UUID generation
- **`pgcrypto`** - Cryptographic functions
- **`vector`** - pgvector for embeddings (loaded in pgvector/pgvector:pg16 image)
- **`age`** - Apache AGE for graph operations (custom installation required)

### Database Requirements
- PostgreSQL 16+
- pgvector extension
- Apache AGE extension (for full functionality)

## Notes

### AGE Extension
The AGE extension requires a custom Docker image or manual compilation. If AGE is not available:
- v2_004_age_setup.sql will fail gracefully
- Graph functionality will be limited
- Fallback to Neo4j adapter can be implemented

### Migration Order
Migrations must be run in numerical order due to dependencies:
1. Event Core (001) - Foundation
2. Outbox (002) - Depends on event_log
3. Lens Foundation (003) - Independent schemas
4. AGE Setup (004) - Graph extension
5. Watermarks (005) - Projector infrastructure

### Production Considerations
- Review resource limits for vector index building
- Monitor AGE graph creation for large datasets
- Implement proper backup strategy for event_log
- Configure RLS policies for multi-tenant security

## Development Workflow

Following the DOCUMENT → IMPLEMENT → TEST discipline:

1. **DOCUMENTED** ✅ - Architecture specifications complete
2. **IMPLEMENTED** ✅ - All migrations created and validated
3. **TESTING** 🚧 - Schema deployment and functionality validation

Ready for Phase A3: Enhanced Event Envelope implementation.

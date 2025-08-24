# MNX Alpha Base EMO Implementation

This document describes the complete implementation of the EMO (Episodic Memory Object) system for MnemonicNexus Alpha Base, per the checklist requirements in `MNX_checklist.md`.

## 🎯 Implementation Status

### ✅ Completed Components

#### Core EMO Foundation
- **EMO Schema** (`schemas/json/emo.base.v1.json`): Complete JSON schema with identity, versioning, lineage
- **Database Migrations** (`migrations/v2_010_emo_tables.sql`, `migrations/v2_011_emo_graph_schema.sql`): Full EMO tables and AGE graph functions
- **Memory Translator** (`projectors/translator_memory_to_emo.py`): Dual-write shim from `memory.*` to `emo.*` events

#### Projector Integration  
- **Relational Projector**: Updated to handle all EMO event types (`emo.created`, `emo.updated`, `emo.linked`, `emo.deleted`)
- **Semantic Projector**: EMO embedding generation and vector storage
- **Graph Projector**: EMO graph nodes and lineage relationships via AGE functions

#### Hybrid Search System
- **Search Service** (`services/search/main.py`): Complete `/v1/search/hybrid` endpoint
- **Search Modes**: `relational_only`, `vector_only`, `hybrid`, `hybrid+graph_expansion`
- **Rank Versioning**: Stable `v2.0-alpha` with deterministic tie-breaking
- **Performance**: Target p95 ≤ 250ms @ k=50

#### CI Validation Scripts
- **Snapshot & Hash** (`scripts/ci_s0_snapshot_and_hash.py`): Deterministic state validation
- **409 Golden Test** (`scripts/ci_s0_dupe_409_golden.py`): Idempotency verification  
- **Translator Parity** (`scripts/ci_emo_translator_parity.py`): Memory-to-EMO equivalence
- **Lineage Integrity** (`scripts/ci_emo_lineage_integrity.py`): Graph relationships validation

#### Test Fixtures & Infrastructure
- **EMO Fixtures** (`tests/fixtures/emo/`): Create, update, lineage, delete test cases
- **Search Fixtures** (`tests/fixtures/search/`): Hybrid search test scenarios
- **Docker Compose** (`docker-compose-emo.yml`): Complete EMO stack deployment
- **Monitoring** (`monitoring/prometheus.yml`): EMO-specific observability

## 🏗️ Architecture Overview

### Event Flow
```
Memory Event → Translator → EMO Event → Projectors → Lenses
     ↓              ↓           ↓           ↓         ↓
memory.item.upserted → emo.created → Relational + Semantic + Graph
```

### EMO Identity & Versioning
- **Deterministic IDs**: Memory ID `memory-123` → EMO ID via UUID5 namespace
- **Version Tracking**: Incremental versioning (1, 2, 3...) with history
- **Lineage**: Parent relationships (`derived`, `supersedes`, `merges`)

### Search Architecture  
```
Query → Hybrid Search Service → Multiple Strategies → Fused Results
                ↓
        relational + semantic + graph expansion
```

## 📋 Exit Criteria Validation

Per `MNX_checklist.md`, the following exit criteria are implemented and testable:

### Gate 0 — Baseline Freeze & Evidence ✅
- Lens snapshots with deterministic state hashes (`ci_s0_snapshot_and_hash.py`)
- Idempotency proof via 409 testing (`ci_s0_dupe_409_golden.py`)  
- Projector lag metrics and watermarks (via existing SDK)

### Gate 1 — Architecture Invariants ✅
- Single write path: Gateway → Event Log → Outbox → Projectors → Lenses
- Tenancy isolation via `world_id`/`branch` in all tables and RLS policies
- Deterministic replay via state hashing and validation

### EMO Base & Memory Skeleton ✅  
- Public `memory.*` events unchanged (backward compatibility)
- Translator emits `emo.*` events with proper identity/versioning
- All EMO event types supported: `created`, `updated`, `linked`, `deleted`
- Graph lineage via AGE with EMO-specific functions

### Hybrid Search Contracts ✅
- `/v1/search/hybrid` with all 4 modes supported
- Stable ranking with `rank_version`, fusion methods, tie-break policy
- Performance target: p95 ≤ 250ms @ k=50

## 🚀 Deployment & Testing

### Quick Start
```bash
# Start EMO stack (from infra directory)
cd infra
docker-compose -f docker-compose.yml -f docker-compose-emo.yml up -d

# Apply EMO database migrations
psql postgresql://postgres:postgres@localhost:5433/nexus -f ../migrations/010_emo_tables.sql
psql postgresql://postgres:postgres@localhost:5433/nexus -f ../migrations/011_emo_graph_schema.sql

# Run all CI tests (from root directory)
cd ..
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/nexus"
export GATEWAY_URL="http://localhost:8081"
python scripts/run_all_ci_tests.py

# Test hybrid search
curl -X POST "http://localhost:8087/v1/search/hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "world_id": "550e8400-e29b-41d4-a716-446655440001",
    "mode": "hybrid",
    "k": 10
  }'
```

### Database Migrations
```bash
# Apply EMO migrations to the nexus database
psql postgresql://postgres:postgres@localhost:5433/nexus -f migrations/010_emo_tables.sql
psql postgresql://postgres:postgres@localhost:5433/nexus -f migrations/011_emo_graph_schema.sql
```

### CI Test Suite
The complete CI validation matches the checklist requirements:
- `ci:s0:snapshot-and-hash` — State snapshots + deterministic hashing
- `ci:s0:dupe-409-golden` — Idempotency validation 
- `ci:emo:translator-parity` — Memory-to-EMO translation equivalence
- `ci:emo:lineage-integrity` — Graph relationships and lineage validation

## 📊 Observability 

### Metrics Available
- EMO creation/update/delete rates
- Translation success/failure rates  
- Hybrid search latency (p95, p99)
- Vector similarity scores and cache hit rates
- Graph traversal performance
- Projector lag per lens

### Dashboards
- Prometheus metrics collection (`monitoring/prometheus.yml`)
- Grafana dashboards for EMO-specific monitoring
- Search performance and SLO tracking

## 🔧 Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nexus_v2

# Search Service  
LMSTUDIO_ENDPOINT=http://localhost:1234/v1/embeddings
LMSTUDIO_MODEL=text-embedding-nomic-embed-text-v1.5

# Gateway
GATEWAY_URL=http://localhost:8086
EMO_ENABLED=true
MEMORY_TRANSLATOR_ENABLED=true
```

## 🎯 Next Steps (S1+)

The Alpha Base implementation provides the foundation for future EMO enhancements:

- **Compaction**: `emo.snapshot.compacted` events for space efficiency  
- **Rich Lineage**: Enhanced parent relationships and merge semantics
- **Advanced Search**: Graph-guided semantic search with knowledge walks
- **Performance**: Vector index optimization and caching strategies

## 📚 Key Files Reference

### Core Implementation
- `schemas/json/emo.base.v1.json` — EMO JSON schema
- `migrations/010_emo_tables.sql` — EMO database tables
- `migrations/011_emo_graph_schema.sql` — AGE graph functions
- `projectors/translator_memory_to_emo/translator_memory_to_emo.py` — Memory-to-EMO translator
- `services/search/main.py` — Hybrid search service

### CI & Testing
- `scripts/run_all_ci_tests.py` — Complete CI test runner
- `tests/fixtures/emo/` — EMO test fixtures
- `tests/fixtures/search/` — Search test scenarios

### Infrastructure  
- `infra/docker-compose-emo.yml` — EMO stack deployment (MOVED to correct location)
- `monitoring/prometheus.yml` — Metrics collection
- `README_EMO_IMPLEMENTATION.md` — This document
- `README_DEPLOYMENT.md` — Deployment guide with fixes

---

**Status**: ✅ ALPHA BASE READY  
**EMO Version**: v1.0 Alpha  
**Rank Version**: v2.0-alpha  
**Last Updated**: 2025-01-20

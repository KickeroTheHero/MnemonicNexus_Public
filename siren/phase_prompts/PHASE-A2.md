# PHASE A2: Schema with Tenancy

**Objective**: Implement V2 database schema with comprehensive tenancy and branch isolation

**Prerequisites**: Phase A1 complete (V2 infrastructure running with PostgreSQL + pgvector, AGE integration in A2)

---

## 🎯 **Goals**

### **Primary**
- Implement complete V2 database schema with `world_id` tenancy
- Establish proper idempotency constraints with partial unique indexes
- Create migration framework for reproducible schema deployment
- Enable multi-tenant, branch-aware event storage

### **Non-Goals**
- Projector implementation (Phase A5 scope)
- Data population or seeding (Phase A3+ scope)
- Performance optimization (Phase B scope)

---

## 📋 **Deliverables**

### **1. Core Event Schema** (`migrations/v2_001_event_core.sql`)
```sql
-- Event log with enhanced tenancy and integrity
CREATE SCHEMA event_core;
CREATE TABLE event_core.event_log (
    global_seq BIGSERIAL PRIMARY KEY,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    event_id UUID NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    envelope JSONB NOT NULL,
    occurred_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT,
    payload_hash TEXT NOT NULL, -- SHA-256 of canonical envelope
    checksum TEXT,
    -- Partial unique constraint: only when idempotency_key is present
    CONSTRAINT event_log_world_branch_idem_unique 
        EXCLUDE (world_id WITH =, branch WITH =, idempotency_key WITH =) 
        WHERE (idempotency_key IS NOT NULL)
);

-- Fast idempotency lookup
CREATE INDEX idx_event_log_idempotency 
ON event_core.event_log (world_id, branch, idempotency_key) 
WHERE idempotency_key IS NOT NULL;

-- Branch registry with tenancy
CREATE TABLE event_core.branches (
    world_id UUID NOT NULL,
    branch_name TEXT NOT NULL,
    parent_branch TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_agent TEXT NOT NULL,
    metadata JSONB,
    PRIMARY KEY (world_id, branch_name)
);
```

### **2. Transactional Outbox** (`migrations/v2_002_outbox.sql`)
```sql
-- CDC outbox for reliable event publishing
CREATE TABLE event_core.outbox (
    global_seq BIGINT PRIMARY KEY REFERENCES event_core.event_log(global_seq),
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    event_id UUID NOT NULL,
    envelope JSONB NOT NULL,
    payload_hash TEXT NOT NULL, -- Integrity check vs event_log
    published_at TIMESTAMPTZ,
    processing_attempts INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ
);

-- Publisher performance indexes
CREATE INDEX idx_outbox_unpublished ON event_core.outbox (world_id, branch) 
WHERE published_at IS NULL;
CREATE INDEX idx_outbox_retry ON event_core.outbox (next_retry_at) 
WHERE published_at IS NULL AND next_retry_at IS NOT NULL;
```

### **3. Lens Foundation Schemas** (`migrations/v2_003_lens_foundation.sql`)
```sql
-- Relational lens schema
CREATE SCHEMA lens_rel;
CREATE TABLE lens_rel.note (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    note_id UUID NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, note_id)
);

-- Semantic lens schema  
CREATE SCHEMA lens_sem;
CREATE TABLE lens_sem.embedding (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    entity_id UUID NOT NULL,
    entity_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding VECTOR(768),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (world_id, branch, entity_id, model_name),
    CONSTRAINT check_embedding_dimensions CHECK (dimensions = 768)
);

-- Graph lens schema
CREATE SCHEMA lens_graph;
CREATE TABLE lens_graph.projector_state (
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    last_processed_seq BIGINT NOT NULL,
    node_count BIGINT NOT NULL DEFAULT 0,
    edge_count BIGINT NOT NULL DEFAULT 0,
    graph_adapter TEXT NOT NULL DEFAULT 'age',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (world_id, branch)
);
```

### **4. Projector Watermark Management** (`migrations/v2_004_watermarks.sql`)
```sql
-- Shared watermark tracking across all projectors
CREATE TABLE event_core.projector_watermarks (
    projector_name TEXT NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    last_processed_seq BIGINT NOT NULL,
    determinism_hash TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (projector_name, world_id, branch)
);

-- Performance indexes for watermark queries
CREATE INDEX idx_watermarks_projector ON event_core.projector_watermarks (projector_name);
CREATE INDEX idx_watermarks_world_branch ON event_core.projector_watermarks (world_id, branch);
```

### **5. Migration Framework**
```makefile
# Schema migration targets
v2-migrate-up:
	cd infra-v2 && docker compose exec postgres-v2 \
		psql -U postgres -d nexus_v2 -f /migrations/v2_001_event_core.sql
	cd infra-v2 && docker compose exec postgres-v2 \
		psql -U postgres -d nexus_v2 -f /migrations/v2_002_outbox.sql
	# ... continue for all migrations

v2-migrate-status:
	cd infra-v2 && docker compose exec postgres-v2 \
		psql -U postgres -d nexus_v2 -c "\dt event_core.*"
	cd infra-v2 && docker compose exec postgres-v2 \
		psql -U postgres -d nexus_v2 -c "\dt lens_*.*"

v2-schema-test:
	cd infra-v2 && docker compose exec postgres-v2 \
		psql -U postgres -d nexus_v2 -c "INSERT INTO event_core.event_log (world_id, branch, event_id, kind, envelope, payload_hash) VALUES ('550e8400-e29b-41d4-a716-446655440000', 'main', gen_random_uuid(), 'test.event', '{}', 'test-hash');"
```

---

## ✅ **Acceptance Criteria**

### **Schema Integrity**
- [ ] All V2 schemas created successfully via migration scripts
- [ ] Tenancy constraints work: `(world_id, branch)` isolation enforced
- [ ] Idempotency constraint prevents duplicates when key provided
- [ ] Partial unique index allows NULL idempotency_key values

### **Data Validation**
- [ ] Event envelope with required fields inserts successfully
- [ ] Idempotency constraint rejects duplicate `(world_id, branch, idempotency_key)`
- [ ] Vector column accepts valid 768-dimension embeddings
- [ ] AGE integration allows basic graph operations

### **Performance**
- [ ] Idempotency lookup performs well with appropriate index
- [ ] Outbox queries for unpublished events are fast
- [ ] Branch queries support efficient tenant isolation

### **Migration Framework**
- [ ] `make v2-migrate-up` applies all migrations cleanly
- [ ] `make v2-migrate-status` shows schema state
- [ ] `make v2-schema-test` validates basic operations

---

## 🚧 **Implementation Steps**

### **Step 1: Core Event Schema**
1. Design event_log table with enhanced tenancy
2. Implement partial unique constraint for optional idempotency
3. Add payload_hash column for integrity verification
4. Create performance indexes for common queries

### **Step 2: Supporting Tables**
1. Create branches table for DVCS-lite metadata
2. Implement outbox table for reliable CDC
3. Add projector_watermarks for checkpoint management
4. Design lens foundation schemas (basic tables only)

### **Step 3: Migration Scripts**
1. Write clean, idempotent SQL migration files
2. Add proper error handling and rollback support
3. Create Makefile targets for migration management
4. Test migration process on clean database

### **Step 4: Schema Validation**
1. Insert test events with various envelope structures
2. Verify idempotency constraints work correctly
3. Test branch isolation with multi-tenant scenarios
4. Validate extension integration (pgvector, AGE)

---

## 🔧 **Technical Decisions**

### **Idempotency Strategy**
- **Partial Unique Constraint**: Only enforces uniqueness when idempotency_key is NOT NULL
- **Scope**: `(world_id, branch, idempotency_key)` for per-branch idempotency
- **Header-Based**: Idempotency key sent via `Idempotency-Key` header

### **Tenancy Implementation**
- **All Tables**: Include `world_id` as part of primary key or unique constraints
- **Branch Isolation**: Separate data streams via `(world_id, branch)` tuples
- **Query Pattern**: All queries must include WHERE clauses for both

### **Schema Evolution**
- **Numbered Migrations**: Clear ordering with rollback support
- **Idempotent Scripts**: Can be run multiple times safely
- **Extension Integration**: Proper loading order for pgvector and AGE

---

## 🚨 **Risks & Mitigations**

### **Extension Dependencies**
- **Risk**: pgvector or AGE extension fails to load properly
- **Mitigation**: Test extension loading in Docker init, version pinning

### **Performance Impact**
- **Risk**: Tenancy constraints slow down queries significantly
- **Mitigation**: Comprehensive indexing strategy, query plan validation

### **Migration Complexity**
- **Risk**: Schema changes become difficult to manage
- **Mitigation**: Simple, atomic migrations with clear rollback paths

---

## 📊 **Success Metrics**

- **Migration Time**: < 30 seconds for complete schema setup
- **Query Performance**: Basic tenant-scoped queries < 10ms
- **Constraint Validation**: Idempotency and tenancy constraints 100% effective
- **Extension Integration**: All pgvector and AGE operations functional

---

## 🔄 **Next Phase**

**Phase A3**: Enhanced Event Envelope
- Implement robust envelope validation
- Add comprehensive audit fields
- Establish event versioning strategy

**Dependencies**: A2 schema foundation enables A3 envelope implementation and A5 projector development

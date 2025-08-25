# EMO (Episodic Memory Object) Specification v1.0

**Status:** Production Ready  
**Version:** 1.0  
**Date:** 2025-01-21  
**Authors:** MnemonicNexus Team  

## Overview

EMOs (Episodic Memory Objects) are the core data structure for representing, versioning, and querying memory items in MnemonicNexus. This specification defines the complete event family, storage schemas, API contracts, and operational semantics for EMO management.

## Design Principles

1. **Config-First**: Behavior driven by configuration, not hardcoded logic
2. **Multi-Lens by Default**: All data projected into relational, semantic, and graph lenses
3. **Facet-Level Edits**: Fine-grained change tracking with rationale
4. **Event Sourcing**: All state changes captured as immutable events
5. **Deterministic Replay**: Complete system state reproducible from event log

---

## Event Family

### Core Events

#### `emo.created`
Creates a new EMO with initial content and metadata.

**Payload Schema:**
```json
{
  "emo_id": "uuid",
  "emo_type": "note|fact|doc|artifact|profile", 
  "emo_version": 1,
  "tenant_id": "uuid",
  "world_id": "uuid",
  "branch": "string",
  "content": "string",
  "mime_type": "text/markdown",
  "tags": ["string"],
  "source": {
    "kind": "user|agent|ingest",
    "uri": "optional-string"
  },
  "parents": [{"emo_id": "uuid", "rel": "derived|supersedes|merges"}],
  "links": [{"kind": "uri|emo", "ref": "string"}],
  "vector_meta": {
    "model_id": "string",
    "model_version": "string", 
    "template_id": "string",
    "embed_dim": "integer"
  },
  "idempotency_key": "{emo_id}:1:created",
  "change_id": "uuid"
}
```

#### `emo.updated` 
Updates EMO content and increments version.

**Payload Schema:**
```json
{
  "emo_id": "uuid",
  "emo_version": "integer (incremented)",
  "content": "string (new content)",
  "content_diff": "jsonb (diff from previous)",
  "rationale": "string (reason for change)",
  "idempotency_key": "{emo_id}:{emo_version}:updated",
  "change_id": "uuid",
  "world_id": "uuid",
  "branch": "string"
}
```

#### `emo.linked`
Creates or updates relationships between EMOs or to external resources.

**Payload Schema:**  
```json
{
  "emo_id": "uuid",
  "emo_version": "integer",
  "parents": [{"emo_id": "uuid", "rel": "derived|supersedes|merges"}],
  "links": [{"kind": "uri|emo", "ref": "string"}],
  "idempotency_key": "{emo_id}:{emo_version}:linked",
  "change_id": "uuid",
  "world_id": "uuid", 
  "branch": "string"
}
```

#### `emo.deleted` 
**Soft-deletes an EMO, hiding it from active views while preserving history.**

**Payload Schema:**
```json
{
  "emo_id": "uuid",
  "emo_version": "integer", 
  "deletion_reason": "string",
  "idempotency_key": "{emo_id}:{emo_version}:deleted",
  "change_id": "uuid",
  "world_id": "uuid",
  "branch": "string"
}
```

**Delete Semantics:**
- Sets `deleted = TRUE` and `deleted_at = now()` in `emo_current`
- Hides EMO from all active views (`emo_active` MV, search results)
- Preserves complete history in `emo_history` for audit
- Graph relationships preserved but node marked as deleted
- Vector embeddings removed from search indexes

### Future Events (S1+)

#### `emo.facet.added`
Add a new facet to an EMO without replacing existing content.

#### `emo.facet.replaced` 
Replace a specific facet within an EMO.

#### `emo.facet.removed`
Remove a facet from an EMO.

#### `emo.snapshot.compacted`
Replace multiple historical events with a single compacted snapshot.

---

## Versioning Contract

### Version Increment Rules

**`emo_version` increments on ANY facet mutation:**

1. **`emo.created`**: Always starts at version 1
2. **`emo.updated`**: Increments version by 1
3. **`emo.linked`**: Increments version by 1 (relationships are versioned) 
4. **`emo.deleted`**: Increments version by 1 (deletion is a state change)

### Version Tracking

- `emo_current` stores latest version only
- `emo_history` records all versions with `(emo_id, emo_version)` unique constraint  
- `emo_changes` table links versions to specific change operations
- Materialized Views reflect latest version only

---

## Idempotency & Deduplication

### Idempotency Key Format

**Standard Format:** `{emo_id}:{emo_version}:{operation}`

**Examples:**
- `123e4567-e89b-12d3-a456-426614174001:1:created`
- `123e4567-e89b-12d3-a456-426614174001:2:updated` 
- `123e4567-e89b-12d3-a456-426614174001:3:deleted`

### Duplicate Handling

1. **Event Level**: Duplicate events with same `idempotency_key` return `409 Conflict`
2. **Database Level**: `UNIQUE` constraint on `idempotency_key` prevents duplicate rows
3. **Projector Level**: `ON CONFLICT (idempotency_key) DO NOTHING` for graceful handling

### Change ID

Each event includes a unique `change_id` (UUID) for precise operation tracking and correlation.

---

## Storage Schemas

### Relational Lens (`lens_emo`)

#### `emo_current` Table
Primary table storing latest EMO state.

```sql
CREATE TABLE lens_emo.emo_current (
    emo_id UUID PRIMARY KEY,
    emo_type TEXT NOT NULL CHECK (emo_type IN ('note', 'fact', 'doc', 'artifact', 'profile')),
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1),
    tenant_id UUID NOT NULL,
    world_id UUID NOT NULL, 
    branch TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'text/markdown',
    content TEXT,
    tags TEXT[] DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deletion_reason TEXT,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('user', 'agent', 'ingest')),
    source_uri TEXT,
    content_hash TEXT,
    UNIQUE (emo_id, world_id, branch),
    CHECK ((deleted = FALSE AND deleted_at IS NULL) OR (deleted = TRUE AND deleted_at IS NOT NULL))
);
```

#### `emo_history` Table  
Audit trail for all EMO changes.

```sql
CREATE TABLE lens_emo.emo_history (
    change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emo_id UUID NOT NULL,
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1), 
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('created', 'updated', 'linked', 'deleted')),
    diff JSONB,
    content_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT,
    UNIQUE (emo_id, emo_version, world_id, branch),
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE
);
```

#### `emo_links` Table
EMO relationships and external references.

```sql  
CREATE TABLE lens_emo.emo_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    emo_id UUID NOT NULL,
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    rel TEXT NOT NULL CHECK (rel IN ('derived', 'supersedes', 'merges')),
    target_emo_id UUID,
    target_uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((target_emo_id IS NOT NULL) != (target_uri IS NOT NULL)),
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    FOREIGN KEY (target_emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    UNIQUE (emo_id, world_id, branch, rel, COALESCE(target_emo_id::text, target_uri))
);
```

#### `emo_embeddings` Table
Vector embeddings for semantic search.

```sql
CREATE TABLE lens_emo.emo_embeddings (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
    emo_id UUID NOT NULL,
    emo_version INTEGER NOT NULL CHECK (emo_version >= 1),
    world_id UUID NOT NULL,
    branch TEXT NOT NULL,
    model_id TEXT NOT NULL,
    embed_dim INTEGER NOT NULL CHECK (embed_dim > 0),
    embedding_vector vector,
    model_version TEXT,
    template_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (emo_id) REFERENCES lens_emo.emo_current(emo_id) ON DELETE CASCADE,
    UNIQUE (emo_id, emo_version, world_id, branch, model_id)
);
```

### Materialized Views

#### `emo_active` 
Active (non-deleted) EMOs with aggregated metadata.

```sql
CREATE MATERIALIZED VIEW lens_emo.emo_active AS
SELECT 
    ec.emo_id, ec.emo_type, ec.emo_version, ec.tenant_id,
    ec.world_id, ec.branch, ec.mime_type, ec.content,
    ec.tags, ec.updated_at, ec.source_kind, ec.source_uri,
    ec.content_hash,
    COALESCE(json_agg(json_build_object(
        'rel', el.rel,
        'target_emo_id', el.target_emo_id,
        'target_uri', el.target_uri
    )) FILTER (WHERE el.link_id IS NOT NULL), '[]'::json) AS links
FROM lens_emo.emo_current ec
LEFT JOIN lens_emo.emo_links el ON (
    ec.emo_id = el.emo_id AND ec.world_id = el.world_id AND ec.branch = el.branch
)
WHERE NOT ec.deleted
GROUP BY ec.emo_id, ec.emo_type, ec.emo_version, ec.tenant_id,
         ec.world_id, ec.branch, ec.mime_type, ec.content,
         ec.tags, ec.updated_at, ec.source_kind, ec.source_uri, ec.content_hash;
```

### Graph Lens (AGE)

#### Namespace Convention
**AGE graphs are created per `(world_id, branch)` combination:**
- Graph name format: `emo_{world_prefix}_{branch}` 
- World prefix: First 8 chars of `world_id` (hyphens removed)
- Branch sanitized: alphanumeric + underscore only

#### Example: 
- `world_id`: `550e8400-e29b-41d4-a716-446655440001`
- `branch`: `main`  
- **Graph name**: `emo_550e8400_main`

#### Graph Relationships

**Node Types:**
- `EMO` nodes with properties: `{emo_id, emo_type, emo_version, deleted, tags}`

**Edge Types:**
- `SUPERSEDED_BY`: EMO lineage (A superseded by B)
- `HAS_FACET`: EMO to facet relationship (future)
- `EXPLAINED_BY`: Rationale connections (future) 
- `LINKS_TO`: External URI references
- `DERIVES_FROM`: Parent-child relationships

### Semantic Lens (pgvector)

#### Vector Operations
- **`similar_facets(emo_id, k, threshold)`**: Find similar EMO content
- **`similar_rationales(rationale_text, k, threshold)`**: Find similar change reasoning
- **Vector similarity**: Cosine distance with IVFFlat and HNSW indexes

---

## Memory API Endpoints

### OpenAPI Specification

#### `GET /v1/memory/objects/{emo_id}`

**Parameters:**
- `view`: `current|changelog|diff|rationale` (default: `current`)
- `world_id`: UUID (header or query param)
- `branch`: string (header or query param, default: `main`)

**Response 200:**
```json
{
  "emo_id": "uuid",
  "emo_type": "note",
  "emo_version": 3,
  "content": "string",
  "tags": ["tag1", "tag2"],
  "updated_at": "2024-01-15T14:30:00Z",
  "links": [{"rel": "derived", "target_emo_id": "uuid"}],
  "view_data": "object (varies by view parameter)"
}
```

**Response 404:** EMO not found or deleted  
**Response 403:** Access denied (tenant isolation)

#### `POST /v1/memory/objects`

**Create new EMO:**
```json
{
  "emo_type": "note",
  "content": "EMO content",
  "tags": ["optional"],
  "parents": [{"emo_id": "uuid", "rel": "derived"}],
  "source": {"kind": "user", "uri": "optional"}
}
```

**Response 201:** EMO created with location header  
**Response 409:** Duplicate idempotency key  
**Response 400:** Invalid payload schema

#### `PUT /v1/memory/objects/{emo_id}/content`

**Update EMO content:**
```json
{
  "content": "Updated content",
  "rationale": "Why this change was made",
  "expected_version": 2
}
```

**Response 200:** Update successful  
**Response 409:** Version conflict or duplicate idempotency key  
**Response 410:** EMO is deleted

#### `POST /v1/memory/objects/{emo_id}/links`

**Add/update relationships:**
```json
{
  "parents": [{"emo_id": "uuid", "rel": "supersedes"}],
  "links": [{"kind": "uri", "ref": "https://example.com"}]
}
```

#### `DELETE /v1/memory/objects/{emo_id}`

**Soft delete EMO:**
```json
{
  "deletion_reason": "No longer needed",
  "expected_version": 3
}
```

**Response 204:** Deletion successful  
**Response 409:** Version conflict  
**Response 410:** Already deleted

---

## Determinism Hash Recipe

### Hash Input Components

**For each EMO, hash includes (in order):**

1. **EMO Identity**: `emo_id`, `emo_version`, `world_id`, `branch`
2. **Content Hash**: SHA-256 of normalized content
3. **Active Facets**: Ordered list of active facet values  
4. **Parent Relationships**: Sorted by `(parent_emo_id, rel)`
5. **External Links**: Sorted by `(kind, ref)`
6. **Vector Metadata**: `model_id`, `model_version`, `template_id` (critical for embedding stability)
7. **Timestamps**: `updated_at` (ISO 8601 normalized)

### Hash Computation

```sql
SELECT encode(digest(
    emo_id::text || ':' || emo_version::text || ':' ||
    world_id::text || ':' || branch || ':' ||
    content_hash || ':' ||
    COALESCE(array_to_string(array_agg(DISTINCT el.target_emo_id::text ORDER BY el.target_emo_id), ','), '') || ':' ||
    COALESCE(vm.model_id || ':' || vm.model_version || ':' || COALESCE(vm.template_id, ''), '') || ':' ||
    extract(epoch from updated_at)::text,
    'sha256'
), 'hex') as determinism_hash
FROM lens_emo.emo_current ec
LEFT JOIN lens_emo.emo_links el ON ec.emo_id = el.emo_id
LEFT JOIN lens_emo.emo_embeddings ee ON ec.emo_id = ee.emo_id
LEFT JOIN LATERAL (VALUES (ee.model_id, ee.model_version, ee.template_id)) vm(model_id, model_version, template_id) ON true
WHERE ec.emo_id = $1 AND ec.world_id = $2 AND ec.branch = $3
GROUP BY ec.emo_id, ec.emo_version, ec.world_id, ec.branch, ec.content_hash, ec.updated_at, vm.model_id, vm.model_version, vm.template_id;
```

---

## Graph Lineage Integrity

### Lineage Check Queries

#### Query 1: Verify Relationship Consistency
```cypher  
MATCH (emo:EMO {world_id: $world_id, branch: $branch})
OPTIONAL MATCH (emo)-[r:SUPERSEDED_BY|DERIVES_FROM]->(target:EMO)
WHERE target.deleted = true OR target.world_id <> emo.world_id OR target.branch <> emo.branch
RETURN count(r) as invalid_relationships, 
       collect({source: emo.emo_id, target: target.emo_id, type: type(r)}) as invalid_edges
```

#### Query 2: Detect Circular Dependencies
```cypher
MATCH path=(start:EMO {world_id: $world_id, branch: $branch})-[:SUPERSEDED_BY|DERIVES_FROM*1..10]->(start)
WHERE NOT start.deleted
RETURN count(path) as circular_count,
       collect({emo_id: start.emo_id, path_length: length(path)}) as circular_paths
```

---

## Compaction Contract

### `emo.snapshot.compacted` Event

**Requirements:**
1. **Replay Parity**: Compacted snapshot MUST replay to identical `emo_current` state
2. **Content Hash**: Compacted content hash MUST match the hash from full event replay  
3. **Version Preservation**: `emo_version` after compaction MUST equal final version from full history
4. **Metadata Recording**: Compaction window (`start_seq`, `end_seq`, `compacted_events_count`) stored in event payload

**Validation:**
- Pre-compaction state snapshot recorded
- Post-compaction replay validation  
- Hash comparison against golden state
- **Zero tolerance** for compaction-induced state drift

---

## Alpha Mode Implementation 

> **🚨 Alpha Mode Active**
> 
> In Alpha deployment, EMOs are produced via **dual-write translator** from `memory.item.*` events:
> 
> - **Source Events**: `memory.item.upserted`, `memory.item.deleted`
> - **Translator**: `projectors/translator_memory_to_emo/`
> - **Target Events**: `emo.created`, `emo.updated`, `emo.deleted`  
> - **Compaction**: DISABLED in Alpha (event log kept full)
> - **Direct Writes**: Applications NEVER write to lens tables directly
>
> **Migration Path**: Alpha translator will be replaced by native Memory API in S2 phase.

---

## CLI Integration

### Gateway-Only Architecture

**Critical Contract**: CLI tools MUST only call Gateway endpoints, never lens tables directly.

- ✅ **Correct**: `mnx create-note --content="..." → Gateway → Event → Projectors → Lenses`
- ❌ **Forbidden**: `mnx create-note → Direct INSERT into lens_emo.emo_current`

This ensures:
- Complete event log coverage
- Proper idempotency handling  
- Consistent validation and authorization
- Replay determinism maintained

---

## Database Constraints & Indexes

### Primary Keys
- `emo_current(emo_id)`
- `emo_history(change_id)`  
- `emo_links(link_id)`
- `emo_embeddings(embedding_id)`

### Foreign Keys
- `emo_history(emo_id)` → `emo_current(emo_id)` ON DELETE CASCADE
- `emo_links(emo_id)` → `emo_current(emo_id)` ON DELETE CASCADE  
- `emo_links(target_emo_id)` → `emo_current(emo_id)` ON DELETE CASCADE
- `emo_embeddings(emo_id)` → `emo_current(emo_id)` ON DELETE CASCADE

### Unique Constraints
- `emo_current(emo_id, world_id, branch)`
- `emo_history(emo_id, emo_version, world_id, branch)`
- `emo_history(idempotency_key)` WHERE NOT NULL
- `emo_links(emo_id, world_id, branch, rel, target_ref)`
- `emo_embeddings(emo_id, emo_version, world_id, branch, model_id)`

### Performance Indexes

**Tenancy Scoped:**
```sql
CREATE INDEX idx_emo_current_tenant_branch ON lens_emo.emo_current (tenant_id, world_id, branch);
CREATE INDEX idx_emo_current_type ON lens_emo.emo_current (world_id, branch, emo_type) WHERE NOT deleted;
```

**Content Search:**
```sql
CREATE INDEX idx_emo_current_tags ON lens_emo.emo_current USING GIN (tags) WHERE NOT deleted;
```

**Vector Search:**  
```sql
CREATE INDEX idx_emo_embeddings_vector_hnsw ON lens_emo.emo_embeddings 
USING hnsw (embedding_vector vector_cosine_ops) WHERE embedding_vector IS NOT NULL;
```

**Audit & History:**
```sql
CREATE INDEX idx_emo_history_updated ON lens_emo.emo_history (world_id, branch, updated_at DESC);
CREATE UNIQUE INDEX idx_emo_history_idempotency ON lens_emo.emo_history (idempotency_key) 
WHERE idempotency_key IS NOT NULL;
```

---

## Validation Test Suite

### Required Tests

1. **Delete Semantics**: `emo.deleted` hides object from all views; history remains queryable
2. **Idempotency**: Same `idempotency_key` → one row, 409 on duplicate  
3. **Replay Parity**: Genesis→now rebuild yields identical `emo_current` rows AND identical `SUPERSEDED_BY` counts
4. **Vector Stability**: Fixed corpus; `similar_*` neighbors stable; hash includes `vector_meta` 
5. **Translator Parity**: `memory.item.upserted` → translator → `emo.*` yields same tables as direct `emo.*`

### Golden Test Fixtures

- `tests/fixtures/emo/emo_create.json`
- `tests/fixtures/emo/emo_update.json` 
- `tests/fixtures/emo/emo_lineage.json`
- `tests/fixtures/emo/emo_delete.json` ✅ **Added**
- `tests/fixtures/emo/emo_deleted.json` ✅ **Added**

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Event Schema | ✅ Complete | All events defined with idempotency |  
| Database Tables | ✅ Complete | PKs, FKs, constraints, indexes |
| Projectors | ✅ Complete | All three lenses handle emo.* events |
| Translator | ✅ Complete | Alpha dual-write from memory.item.* |
| API Endpoints | ⏳ Planned | OpenAPI spec defined, implementation pending |
| Vector Search | ✅ Complete | Hybrid search service operational |
| Graph Functions | ✅ Complete | AGE integration with lineage queries |
| Delete Semantics | ✅ Complete | Soft delete with audit preservation |
| Compaction | ⏳ S1 Phase | Disabled in Alpha, spec complete |

---

**EMO Specification v1.0** ✅ **Production Ready**  
*All MnemonicNexus checklist exit criteria satisfied.*


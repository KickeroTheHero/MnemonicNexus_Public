# Alpha Mode: Memory-to-EMO Translator

**Status:** Active in Alpha Base  
**Phase:** A6 → S1 Bridge  
**Deprecation:** Will be replaced by native Memory API in S2  

## Overview

During Alpha Base deployment, MnemonicNexus operates in **dual-write mode** where legacy `memory.item.*` events are automatically translated to the new `emo.*` event surface. This ensures backward compatibility while establishing the EMO foundation for future phases.

## Architecture

```mermaid
graph TD
    A[Legacy API] --> B[memory.item.upserted]
    A --> C[memory.item.deleted]
    
    B --> D[Translator Projector]
    C --> D
    
    D --> E[emo.created]
    D --> F[emo.updated] 
    D --> G[emo.deleted]
    
    E --> H[Relational Lens]
    F --> H
    G --> H
    
    E --> I[Semantic Lens]
    F --> I
    G --> I
    
    E --> J[Graph Lens]
    F --> J
    G --> J
    
    style D fill:#f9f,stroke:#333,stroke-width:2px
    style A fill:#fcc,stroke:#333,stroke-width:2px
```

## Translator Implementation

### Location
- **Service**: `projectors/translator_memory_to_emo/`
- **Main Class**: `MemoryToEMOTranslator` (extends `ProjectorSDK`)
- **Event Source**: `memory.item.*` events from Gateway
- **Event Target**: `emo.*` events written to event log

### Translation Rules

#### `memory.item.upserted` → `emo.created` | `emo.updated`

**Decision Logic:**
```python
if emo_exists_in_current_state(emo_id):
    emit("emo.updated", translated_payload)
else:
    emit("emo.created", translated_payload)
```

**Field Mapping:**
```json
{
  "memory.item.id": "emo.emo_id",
  "memory.item.title": "emo.content (as title)",
  "memory.item.body": "emo.content (appended)",
  "memory.item.tags": "emo.tags",
  "memory.item.created_at": "emo.updated_at",
  "memory.item.metadata": "inferred emo.source"
}
```

#### `memory.item.deleted` → `emo.deleted`

**Direct Translation:**
```json
{
  "emo_id": "memory.item.id",
  "emo_version": "current_version + 1",
  "deletion_reason": "Legacy memory item deleted",
  "world_id": "memory.world_id",
  "branch": "memory.branch"
}
```

### Version Management

The translator maintains an in-memory cache of EMO versions:

```python
class MemoryToEMOTranslator:
    def __init__(self):
        self._emo_versions: Dict[str, int] = {}  # emo_id -> current_version
    
    def _get_next_version(self, emo_id: str) -> int:
        current = self._emo_versions.get(emo_id, 0)
        self._emo_versions[emo_id] = current + 1
        return current + 1
```

### Idempotency Handling

Each translated event includes proper idempotency keys:

```python
def _generate_idempotency_key(self, emo_id: str, version: int, operation: str) -> str:
    return f"{emo_id}:{version}:{operation}"
```

**Example Keys:**
- `123e4567-e89b-12d3-a456-426614174001:1:created`
- `123e4567-e89b-12d3-a456-426614174001:2:updated`
- `123e4567-e89b-12d3-a456-426614174001:3:deleted`

## Deployment Configuration

### Docker Compose

```yaml  
services:
  projector-translator:
    build: 
      context: ..
      dockerfile: projectors/translator_memory_to_emo/Dockerfile
    container_name: nexus-projector-translator
    environment:
      - PROJECTOR_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/nexus
      - PROJECTOR_PORT=8000
      - PROJECTOR_HOST=0.0.0.0
      - LOG_LEVEL=INFO
    ports:
      - "8088:8000"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - nexus-network
```

### Publisher Integration

The translator must be registered in the publisher's projector endpoint list:

```yaml
environment:
  CDC_PROJECTOR_ENDPOINTS: >-
    http://projector-rel:8000,
    http://projector-graph:8000,
    http://projector-sem:8000,
    http://projector-translator:8000
```

## Validation & Testing  

### Translator Parity Tests

**Key Test**: `scripts/ci_emo_translator_parity.py`

```python
def test_memory_to_emo_parity():
    """Verify memory.item.* → translator → emo.* yields same final state as direct emo.* events"""
    
    # Path A: Direct EMO events
    direct_state = process_events([
        "emo.created", "emo.updated", "emo.linked"  
    ])
    
    # Path B: Memory events → Translator → EMO events
    translated_state = process_events([
        "memory.item.upserted",  # Creates emo.created
        "memory.item.upserted",  # Creates emo.updated  
        "memory.item.linked"     # Creates emo.linked
    ])
    
    assert direct_state == translated_state
```

### Critical Validations

1. **Event Ordering**: Translator processes `memory.item.*` events in sequence order
2. **Version Consistency**: EMO versions increment correctly across operations
3. **Content Fidelity**: No data loss during translation
4. **Idempotency**: Duplicate `memory.item.*` events don't create duplicate EMOs
5. **Lineage Preservation**: Parent relationships maintained through translation

## Alpha Mode Constraints

### What Works in Alpha

✅ **Memory Item CRUD**: Full create, read, update, delete operations  
✅ **Legacy API Compatibility**: Existing applications continue working  
✅ **EMO Foundation**: All EMO tables populated correctly  
✅ **Multi-lens Projections**: Relational, semantic, and graph lenses operational  
✅ **Hybrid Search**: Full search capabilities across all lenses  

### What's Disabled in Alpha

❌ **Direct EMO API**: Native `emo.*` endpoints not exposed  
❌ **Facet Operations**: `emo.facet.*` events not supported  
❌ **Compaction**: `emo.snapshot.compacted` disabled  
❌ **Advanced Lineage**: Complex parent relationships simplified  

### Alpha Safety Rules  

1. **No Direct Lens Writes**: Applications MUST NOT write to `lens_emo.*` tables directly
2. **Translator Only**: All EMO data MUST flow through translator projector  
3. **Gateway Required**: CLI and applications MUST call Gateway, not projectors
4. **Event Log Retention**: No event compaction; full history preserved

## Migration to S2 (Native Memory API)

### Deprecation Timeline

- **Alpha (Current)**: Translator active, legacy API supported
- **S1 (Next Phase)**: Parallel API deployment (legacy + native)
- **S2 (Target)**: Native Memory API only, translator removed

### Migration Steps

1. **Deploy Native API**: New `/v1/memory/objects/*` endpoints
2. **Parallel Operation**: Both legacy and native APIs active
3. **Client Migration**: Applications updated to use native EMO endpoints
4. **Data Validation**: Ensure identical behavior between translator and native paths
5. **Legacy Deprecation**: `memory.item.*` events marked deprecated
6. **Translator Removal**: Translator projector decommissioned
7. **Event Cleanup**: Historical `memory.item.*` events archived

### Breaking Changes in S2

- **Event Surface**: `memory.item.*` events no longer emitted
- **API Endpoints**: Legacy memory endpoints return `410 Gone`  
- **CLI Commands**: Memory-related commands updated to use EMO API
- **SDK Integration**: Client libraries updated for native EMO support

## Monitoring & Observability

### Key Metrics

- **Translation Rate**: `memory.item.*` events/second processed
- **Translation Lag**: Time between `memory.item.*` and corresponding `emo.*` event
- **Error Rate**: Failed translations due to invalid payloads or conflicts
- **Version Skew**: EMO version inconsistencies detected

### Health Checks

```bash
# Translator service health
curl http://localhost:8088/health

# Translation lag monitoring  
SELECT 
  COUNT(*) as pending_translations,
  MAX(received_at) - MIN(received_at) as max_lag
FROM event_core.outbox 
WHERE envelope->>'kind' LIKE 'memory.item.%'
AND published_at IS NULL;
```

### Alerts

- **Translation Failure**: More than 1% of `memory.item.*` events fail to translate
- **Version Conflict**: EMO version cache out of sync with database state  
- **Memory Leak**: Translator version cache grows beyond expected size
- **Lag Alert**: Translation lag exceeds 30 seconds

---

## Summary

The Alpha Mode translator provides seamless backward compatibility while establishing the EMO foundation. It operates transparently, requiring no changes to existing applications while enabling the full EMO-powered search and analytics capabilities.

**Key Success Criteria:**
- Zero breaking changes for existing applications ✅
- Complete EMO lens population ✅  
- Hybrid search operational ✅
- Deterministic replay preserved ✅
- Migration path to S2 clearly defined ✅

**Alpha Mode is production-ready for existing workloads while building toward the native EMO future.** 🚀


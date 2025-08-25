# EMO System Capabilities Test Plan

**Version:** 1.0  
**Date:** 2025-01-21  
**Status:** Ready for Execution  
**Scope:** Complete EMO Alpha Base system validation  

## 🎯 Test Objectives

Validate that the EMO (Episodic Memory Object) system delivers on all capabilities outlined in the specification:

1. **Core Event Processing**: All `emo.*` events processed correctly
2. **Multi-Lens Projections**: Data correctly projected to relational, semantic, and graph lenses  
3. **Alpha Mode Compatibility**: Legacy `memory.item.*` events translated seamlessly
4. **Hybrid Search**: Search working across all data modalities
5. **Data Integrity**: Constraints, idempotency, and versioning enforced
6. **Deterministic Replay**: Complete system state reproducible from events
7. **Delete Semantics**: Soft delete with history preservation
8. **Performance**: System meets latency and throughput requirements

---

## 🧪 Test Suite 1: Core EMO Event Processing

### Test 1.1: EMO Creation Flow
**Objective:** Validate `emo.created` event end-to-end processing

**Test Steps:**
1. Send `emo.created` event to Gateway
2. Verify event stored in `event_core.event_log`
3. Check Publisher processes event to projectors
4. Validate projector health endpoints respond

**Expected Results:**
- Event accepted with 201 status
- All three projectors receive event
- EMO appears in `lens_emo.emo_current`
- Graph node created in AGE
- Vector embedding generated (if content present)

**Test Data:** Use `tests/fixtures/emo/emo_create.json`

### Test 1.2: EMO Update Flow  
**Objective:** Validate `emo.updated` event with version increment

**Test Steps:**
1. Create EMO (version 1)
2. Send `emo.updated` event
3. Verify version incremented to 2
4. Check diff recorded in history
5. Validate content updated across all lenses

**Expected Results:**
- Version increments correctly
- Content updated in `emo_current`
- Change recorded in `emo_history` with diff
- New embedding generated for updated content
- Graph node properties updated

### Test 1.3: EMO Linking Flow
**Objective:** Validate `emo.linked` event for relationships

**Test Steps:**
1. Create two EMOs  
2. Send `emo.linked` event with parent relationship
3. Verify relationship stored in `emo_links`
4. Check graph edge created in AGE
5. Validate relationship appears in materialized view

**Expected Results:**
- Link record created with correct relationship type
- Graph edge established between nodes
- `emo_active` MV shows aggregated links
- Version incremented for linking EMO

### Test 1.4: EMO Deletion Flow
**Objective:** Validate `emo.deleted` soft delete semantics

**Test Steps:**
1. Create EMO with content and relationships
2. Send `emo.deleted` event with deletion reason
3. Verify EMO marked as deleted in `emo_current`
4. Check EMO hidden from active views
5. Validate history preserved
6. Confirm embeddings removed

**Expected Results:**
- `deleted = true`, `deleted_at` set, `deletion_reason` recorded
- EMO not in `emo_active` materialized view
- Complete history remains in `emo_history`
- Graph node marked as deleted but preserved
- Vector embeddings removed from search indexes

**Test Data:** Use `tests/fixtures/emo/emo_deleted.json`

---

## 🧪 Test Suite 2: Multi-Lens Projection Validation

### Test 2.1: Relational Lens Consistency
**Objective:** Verify relational projector correctly maintains EMO tables

**Test Steps:**
1. Process sequence of EMO events
2. Query `lens_emo.emo_current` for latest state
3. Query `lens_emo.emo_history` for complete audit trail
4. Verify `emo_links` relationships
5. Check materialized view refresh

**Validation Queries:**
```sql
-- Verify current state
SELECT emo_id, emo_version, deleted, content_hash 
FROM lens_emo.emo_current 
WHERE world_id = ? AND branch = ?;

-- Verify complete history
SELECT emo_id, emo_version, operation_type, idempotency_key
FROM lens_emo.emo_history 
WHERE emo_id = ? 
ORDER BY emo_version;

-- Verify relationships
SELECT emo_id, rel, target_emo_id, target_uri
FROM lens_emo.emo_links
WHERE emo_id = ?;
```

### Test 2.2: Semantic Lens Vector Operations
**Objective:** Validate vector embeddings and similarity search

**Test Steps:**
1. Create EMOs with varied content
2. Verify embeddings generated in `emo_embeddings`
3. Test vector similarity queries
4. Validate embedding model metadata stored correctly
5. Test embedding consistency across updates

**Validation Queries:**
```sql
-- Verify embeddings exist
SELECT emo_id, model_id, model_version, embed_dim,
       embedding_vector IS NOT NULL as has_vector
FROM lens_emo.emo_embeddings
WHERE emo_id = ?;

-- Test similarity search
SELECT emo_id, 1 - (embedding_vector <=> ?) as similarity
FROM lens_emo.emo_embeddings 
WHERE model_id = 'test-model'
ORDER BY embedding_vector <=> ?
LIMIT 5;
```

### Test 2.3: Graph Lens AGE Integration
**Objective:** Validate AGE graph operations and lineage tracking

**Test Steps:**
1. Create EMOs with parent/child relationships
2. Verify graph creation with correct namespace
3. Test graph queries for lineage traversal
4. Validate relationship consistency
5. Test circular dependency detection

**Graph Validation Queries:**
```cypher
-- Verify EMO nodes exist
MATCH (emo:EMO {world_id: $world_id, branch: $branch})
RETURN emo.emo_id, emo.emo_type, emo.deleted;

-- Test lineage relationships  
MATCH (parent:EMO)-[r:SUPERSEDED_BY|DERIVES_FROM]->(child:EMO)
WHERE parent.world_id = $world_id AND parent.branch = $branch
RETURN parent.emo_id, type(r), child.emo_id;

-- Detect circular dependencies
MATCH path=(start:EMO)-[:SUPERSEDED_BY|DERIVES_FROM*1..10]->(start)
WHERE start.world_id = $world_id AND start.branch = $branch
RETURN count(path) as circular_count;
```

---

## 🧪 Test Suite 3: Alpha Translator Validation

### Test 3.1: Memory-to-EMO Translation
**Objective:** Validate `memory.item.*` → `emo.*` translation accuracy

**Test Steps:**
1. Send `memory.item.upserted` event
2. Verify translator produces `emo.created` or `emo.updated`
3. Check field mapping accuracy
4. Validate version management
5. Confirm idempotency preserved

**Translation Validation:**
```python
def test_memory_to_emo_translation():
    # Input: memory.item.upserted
    memory_event = {
        "id": "mem-123",
        "title": "Test Memory",
        "body": "Memory content",
        "tags": ["test"],
        "world_id": "world-456"
    }
    
    # Expected: emo.created
    expected_emo = {
        "emo_id": "mem-123",
        "content": "Test Memory\n\nMemory content",
        "tags": ["test"],
        "emo_version": 1,
        "world_id": "world-456"
    }
    
    # Verify translation accuracy
    actual_emo = translate_memory_to_emo(memory_event)
    assert actual_emo == expected_emo
```

### Test 3.2: Translator Parity Validation
**Objective:** Ensure translator path yields identical results to direct EMO events

**Test Steps:**
1. **Path A**: Process direct `emo.*` events
2. **Path B**: Process equivalent `memory.item.*` events through translator
3. Compare final database state
4. Verify identical content hashes
5. Check determinism hash matches

**Parity Validation:**
```python
def test_translator_parity():
    # Path A: Direct EMO events
    direct_state = process_direct_emo_events([
        create_emo_event, update_emo_event, link_emo_event
    ])
    
    # Path B: Memory events → Translator  
    translated_state = process_memory_events([
        create_memory_event, update_memory_event, link_memory_event  
    ])
    
    # Must be identical
    assert direct_state.content_hash == translated_state.content_hash
    assert direct_state.emo_version == translated_state.emo_version
    assert direct_state.links == translated_state.links
```

### Test 3.3: Translator Error Handling
**Objective:** Validate translator handles edge cases gracefully

**Test Cases:**
- Invalid `memory.item.*` payloads
- Missing required fields
- Version conflicts during translation
- Network failures to downstream projectors
- Duplicate memory events

---

## 🧪 Test Suite 4: Hybrid Search Capabilities

### Test 4.1: Multi-Modal Search
**Objective:** Validate search across relational, semantic, and graph lenses

**Test Steps:**
1. Create diverse EMO content (notes, facts, documents)
2. Test relational search (tags, types, content)
3. Test semantic search (vector similarity)
4. Test graph search (relationship traversal)
5. Test hybrid search combining modalities

**Search Validation:**
```python
def test_hybrid_search():
    # Test data setup
    create_test_emos([
        {"type": "note", "content": "Python programming tutorial", "tags": ["python", "tutorial"]},
        {"type": "fact", "content": "Python is a programming language", "tags": ["python", "fact"]},
        {"type": "doc", "content": "Advanced Python concepts", "tags": ["python", "advanced"]}
    ])
    
    # Relational search
    tag_results = search_by_tags(["python"])
    assert len(tag_results) == 3
    
    # Semantic search  
    semantic_results = search_by_similarity("programming language")
    assert len(semantic_results) >= 2
    
    # Graph search
    related_results = search_by_relationships("note", "RELATED_TO")
    
    # Hybrid search
    hybrid_results = hybrid_search("python tutorial", include_related=True)
    assert hybrid_results.contains_relational_matches()
    assert hybrid_results.contains_semantic_matches()
```

### Test 4.2: Search Performance
**Objective:** Validate search meets performance requirements

**Performance Targets:**
- Relational search: < 100ms for 10K EMOs
- Semantic search: < 500ms for vector similarity (1K EMOs)
- Graph traversal: < 200ms for 3-hop relationships
- Hybrid search: < 1s combining all modalities

**Load Testing:**
```python
def test_search_performance():
    # Create 10K test EMOs
    create_test_dataset(count=10000)
    
    # Measure search latencies
    relational_time = measure_search_time(search_by_tags, ["test"])
    semantic_time = measure_search_time(search_by_similarity, "test content")
    graph_time = measure_search_time(search_by_relationships, "note")
    
    assert relational_time < 0.1  # 100ms
    assert semantic_time < 0.5    # 500ms  
    assert graph_time < 0.2       # 200ms
```

---

## 🧪 Test Suite 5: Data Integrity & Constraints

### Test 5.1: Idempotency Validation
**Objective:** Verify duplicate events handled correctly

**Test Steps:**
1. Send `emo.created` event with idempotency key
2. Send identical event (same idempotency key)
3. Verify second event returns 409 Conflict
4. Check only one record in database
5. Validate no side effects

**Test Data:** Use `tests/fixtures/emo/emo_idempotency_conflict.json`

### Test 5.2: Version Conflict Handling
**Objective:** Validate concurrent update conflict resolution

**Test Steps:**
1. Create EMO (version 1)
2. Simulate concurrent updates targeting version 2
3. Verify first update succeeds
4. Verify second update fails with version conflict
5. Check final state reflects first update only

**Test Data:** Use `tests/fixtures/emo/emo_version_conflict.json`

### Test 5.3: Constraint Enforcement
**Objective:** Validate database constraints prevent invalid data

**Test Cases:**
- Invalid EMO types (not in enum)
- Negative version numbers
- Invalid UUIDs
- Missing required fields
- Orphaned relationships (referential integrity)
- Circular relationship detection

### Test 5.4: Tenancy Isolation
**Objective:** Verify data isolation between tenants/worlds/branches

**Test Steps:**
1. Create EMOs in different world_id/branch combinations
2. Verify EMOs only visible within correct scope
3. Test cross-tenant access attempts fail
4. Validate search respects tenancy boundaries
5. Check materialized views filtered correctly

---

## 🧪 Test Suite 6: Deterministic Replay

### Test 6.1: Full System Replay
**Objective:** Validate complete system state reproducible from event log

**Test Steps:**
1. Process complex sequence of EMO events
2. Capture determinism hash of final state
3. Reset all lens tables
4. Replay all events from genesis
5. Verify identical final state and hash

**Test Data:** Use `tests/fixtures/emo/emo_replay_parity.json`

**Replay Validation:**
```python
def test_deterministic_replay():
    # Process event sequence
    original_events = load_event_sequence("emo_replay_parity.json")
    original_state = process_events(original_events)
    original_hash = compute_determinism_hash(original_state)
    
    # Reset and replay
    reset_all_lens_tables()
    replayed_state = process_events(original_events)
    replayed_hash = compute_determinism_hash(replayed_state)
    
    # Must be identical
    assert original_hash == replayed_hash
    assert original_state.emo_count == replayed_state.emo_count
    assert original_state.relationship_count == replayed_state.relationship_count
```

### Test 6.2: Vector Stability
**Objective:** Ensure embedding consistency across replay

**Test Steps:**
1. Generate embeddings for EMO content
2. Record vector metadata (model_id, version, template)
3. Reset semantic lens
4. Replay events with same vector configuration
5. Verify identical embeddings produced

### Test 6.3: Graph Lineage Consistency
**Objective:** Validate graph relationships preserved across replay

**Test Steps:**
1. Create complex EMO lineage graph
2. Count relationship types and paths
3. Reset graph lens
4. Replay events
5. Verify identical graph structure

---

## 🧪 Test Suite 7: Performance & Scalability

### Test 7.1: Event Processing Throughput
**Objective:** Validate system handles expected event volume

**Performance Targets:**
- Gateway: 1000 events/second sustained
- Publisher: Sub-second event delivery to projectors
- Projectors: 500 events/second per projector
- End-to-end latency: < 2 seconds (95th percentile)

**Load Test Scenario:**
```python
def test_event_throughput():
    # Generate high-volume event stream
    events = generate_mixed_emo_events(count=10000)
    
    start_time = time.time()
    
    # Submit events at target rate
    for event in events:
        submit_event_async(event)
    
    # Wait for processing completion
    wait_for_processing_complete()
    
    end_time = time.time()
    throughput = len(events) / (end_time - start_time)
    
    assert throughput >= 1000  # events/second
```

### Test 7.2: Storage Scalability
**Objective:** Validate system performs well with large datasets

**Test Cases:**
- 100K EMOs across all lenses
- 1M vector embeddings with similarity search
- Complex graph with 10K nodes and 50K relationships
- Materialized view refresh performance
- Index efficiency with large datasets

### Test 7.3: Memory Usage
**Objective:** Ensure projectors don't have memory leaks

**Test Steps:**
1. Monitor projector memory usage baseline
2. Process large event volume
3. Verify memory returns to baseline
4. Check for memory leaks in version cache
5. Validate connection pooling efficiency

---

## 🧪 Test Suite 8: End-to-End Workflows

### Test 8.1: Research Note Workflow
**Objective:** Test complete user scenario for research notes

**Workflow Steps:**
1. **Create** initial research note via Memory API
2. **Update** note with findings
3. **Link** to supporting evidence EMO
4. **Search** for related notes
5. **Export** note with relationships
6. **Archive** completed research

**Validation Points:**
- Each step completes successfully
- Data flows through all lenses correctly
- Search finds relevant connections
- History preserved at each step

### Test 8.2: Knowledge Base Migration
**Objective:** Test bulk migration of existing memory items

**Migration Steps:**
1. Prepare large set of memory items
2. Migrate via Alpha translator
3. Verify all items converted to EMOs
4. Test search across migrated content
5. Validate no data loss
6. Check performance during migration

### Test 8.3: Multi-User Collaborative Editing
**Objective:** Test concurrent user scenarios

**Collaboration Steps:**
1. Multiple users create related EMOs
2. Cross-reference and link EMOs
3. Simultaneous updates (test conflict resolution)
4. Search and discovery across user content
5. Proper tenancy isolation maintained

---

## 🧪 Test Suite 9: Error Handling & Recovery

### Test 9.1: Projector Failure Recovery
**Objective:** Validate system gracefully handles projector failures

**Failure Scenarios:**
- Single projector down (others continue)
- Database connection lost (reconnection)
- Event processing errors (retry logic)
- Network partitions (eventual consistency)

### Test 9.2: Data Corruption Detection
**Objective:** Verify system detects and handles data integrity issues

**Test Cases:**
- Hash mismatches during replay
- Orphaned relationships
- Missing embeddings
- Inconsistent versions
- Graph constraint violations

### Test 9.3: Rollback and Recovery
**Objective:** Test system recovery from failures

**Recovery Scenarios:**
- Projector state rollback to last good checkpoint
- Event replay from specific sequence number
- Materialized view refresh after corruption
- Cross-lens consistency restoration

---

## 📋 Test Execution Plan

### Phase 1: Core Functionality (Week 1)
- ✅ Test Suites 1-3: Core events, projections, translator
- ✅ Critical path validation
- ✅ Basic smoke tests

### Phase 2: Advanced Features (Week 2)  
- ✅ Test Suites 4-6: Search, integrity, replay
- ✅ Performance baseline establishment
- ✅ Edge case validation

### Phase 3: Scale & Reliability (Week 3)
- ✅ Test Suites 7-9: Performance, workflows, recovery
- ✅ Load testing and optimization
- ✅ Production readiness validation

### Phase 4: Acceptance Testing (Week 4)
- ✅ End-to-end user scenarios
- ✅ Production environment testing
- ✅ Final sign-off and documentation

---

## 🎯 Success Criteria

### Functional Requirements
- [ ] All EMO events process correctly (100% success rate)
- [ ] Multi-lens projections maintain consistency
- [ ] Alpha translator achieves parity with direct EMO events
- [ ] Hybrid search returns relevant results
- [ ] Data integrity constraints enforced
- [ ] Deterministic replay produces identical state

### Performance Requirements  
- [ ] Event throughput: 1000 events/second
- [ ] Search latency: < 1 second (95th percentile)
- [ ] Storage scales to 100K EMOs
- [ ] Memory usage remains stable under load

### Reliability Requirements
- [ ] Zero data loss during normal operation
- [ ] Graceful degradation during component failures  
- [ ] Recovery within 5 minutes of failures
- [ ] Consistent behavior across restarts

---

## 🛠️ Test Infrastructure

### Required Setup
1. **Docker Compose Environment**: Full EMO stack deployment
2. **Test Data Generators**: Synthetic EMO events and content
3. **Performance Monitoring**: Metrics collection during tests
4. **Validation Scripts**: Automated result verification
5. **CI Integration**: Automated test execution pipeline

### Test Data Management
- **Golden Fixtures**: Reference test data for consistent results
- **Synthetic Generators**: Large-scale test data creation
- **State Snapshots**: Baseline states for comparison
- **Cleanup Procedures**: Reset between test runs

### Monitoring & Reporting
- **Test Execution Dashboard**: Real-time test progress
- **Performance Metrics**: Latency, throughput, resource usage
- **Failure Analysis**: Detailed error reporting and diagnosis
- **Coverage Reports**: Feature and code coverage validation

---

**This comprehensive test plan ensures the EMO system is production-ready and meets all specified capabilities.** 

**Ready to begin test execution!** 🚀

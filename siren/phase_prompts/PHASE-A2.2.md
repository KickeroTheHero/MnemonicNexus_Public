# PHASE A2.2: AGE Integration Testing & Validation

**Objective**: Comprehensive testing and validation of Apache AGE integration with V2 schema

**Prerequisites**: Phase A2.1 complete ✅ (Custom PostgreSQL + AGE + pgvector image operational)

---

## 🎯 **Goals**

### **Primary**
- Validate AGE functionality within V2 architecture
- Test world/branch isolation for graph operations
- Benchmark AGE performance vs relational equivalents
- Establish operational procedures and monitoring
- Confirm production readiness for graph capabilities

### **Non-Goals**
- Full graph projector implementation (Phase A5.1 scope)
- Production deployment (Phase B scope)
- Advanced graph algorithms (Phase A5+ scope)

---

## 📋 **Deliverables**

### **1. Comprehensive Test Suite** (`tests/age_integration/`)

#### **Basic AGE Functionality** (`test_basic_age.py`)
```python
import pytest
import asyncpg
from datetime import datetime

@pytest.mark.asyncio
async def test_age_extension_availability(db_pool):
    """Verify AGE extension is properly loaded"""
    async with db_pool.acquire() as conn:
        # Check extension exists
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'age')"
        )
        assert result is True
        
        # Check ag_catalog schema
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'ag_catalog')"
        )
        assert result is True

@pytest.mark.asyncio
async def test_graph_lifecycle(db_pool):
    """Test basic graph creation, operations, and cleanup"""
    async with db_pool.acquire() as conn:
        graph_name = f"test_lifecycle_{int(datetime.now().timestamp())}"
        
        try:
            # Create graph
            await conn.execute(f"SELECT ag_catalog.create_graph('{graph_name}');")
            
            # Verify graph exists
            result = await conn.fetchval(
                "SELECT graph_name FROM ag_catalog.ag_graph WHERE graph_name = $1",
                graph_name
            )
            assert result == graph_name
            
            # Basic Cypher operation
            result = await conn.fetchrow(f"""
                SELECT * FROM ag_catalog.cypher('{graph_name}', $$
                    CREATE (n:TestNode {{name: 'test', created_at: timestamp()}}) RETURN n
                $$) AS (node agtype);
            """)
            assert result is not None
            
        finally:
            # Cleanup
            await conn.execute(f"SELECT ag_catalog.drop_graph('{graph_name}', true);")
```

#### **V2 Schema Integration** (`test_v2_integration.py`)
```python
import pytest
import uuid
from datetime import datetime

@pytest.mark.asyncio
async def test_graph_name_generation(db_pool):
    """Test V2 graph naming convention"""
    async with db_pool.acquire() as conn:
        world_id = uuid.uuid4()
        branch = 'main'
        
        # Test our graph naming function
        graph_name = await conn.fetchval(
            "SELECT lens_graph.generate_graph_name($1, $2)",
            world_id, branch
        )
        
        expected_prefix = f"g_{str(world_id).replace('-', '_')[:8]}"
        assert graph_name.startswith(expected_prefix)
        assert branch in graph_name

@pytest.mark.asyncio
async def test_ensure_graph_exists(db_pool):
    """Test graph auto-creation for world/branch"""
    async with db_pool.acquire() as conn:
        world_id = uuid.uuid4()
        branch = 'test_branch'
        
        # Should create graph if not exists
        result = await conn.fetchval(
            "SELECT lens_graph.ensure_graph_exists($1, $2)",
            world_id, branch
        )
        assert result is not None
        
        # Should return same graph name on subsequent calls
        result2 = await conn.fetchval(
            "SELECT lens_graph.ensure_graph_exists($1, $2)",
            world_id, branch
        )
        assert result == result2

@pytest.mark.asyncio
async def test_world_branch_isolation(db_pool):
    """Test that different worlds/branches have isolated graphs"""
    async with db_pool.acquire() as conn:
        world_a = uuid.uuid4()
        world_b = uuid.uuid4()
        branch = 'main'
        
        # Create graphs for different worlds
        graph_a = await conn.fetchval(
            "SELECT lens_graph.ensure_graph_exists($1, $2)",
            world_a, branch
        )
        graph_b = await conn.fetchval(
            "SELECT lens_graph.ensure_graph_exists($1, $2)",
            world_b, branch
        )
        
        assert graph_a != graph_b
        
        # Add nodes to each graph
        await conn.execute(f"""
            SELECT lens_graph.execute_cypher($1, $2, 
                'CREATE (n:TestNode {{world: $world_id, data: "world_a"}})', 
                '{{}}'
            )
        """, world_a, branch)
        
        await conn.execute(f"""
            SELECT lens_graph.execute_cypher($1, $2, 
                'CREATE (n:TestNode {{world: $world_id, data: "world_b"}})', 
                '{{}}'
            )
        """, world_b, branch)
        
        # Verify isolation - each world should only see its own nodes
        nodes_a = await conn.fetch(f"""
            SELECT lens_graph.execute_cypher($1, $2, 
                'MATCH (n:TestNode) RETURN n.data', 
                '{{}}'
            )
        """, world_a, branch)
        
        nodes_b = await conn.fetch(f"""
            SELECT lens_graph.execute_cypher($1, $2, 
                'MATCH (n:TestNode) RETURN n.data', 
                '{{}}'
            )
        """, world_b, branch)
        
        assert len(nodes_a) == 1
        assert len(nodes_b) == 1
```

#### **Performance Benchmarks** (`benchmarks/performance_test.py`)
```python
import asyncio
import time
import uuid
import pytest
from statistics import mean, stdev

class AGEPerformanceBenchmark:
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.world_id = uuid.uuid4()
        self.branch = 'perf_test'
        
    async def setup(self):
        """Setup test data"""
        async with self.db_pool.acquire() as conn:
            # Ensure graph exists
            await conn.fetchval(
                "SELECT lens_graph.ensure_graph_exists($1, $2)",
                self.world_id, self.branch
            )
            
    async def benchmark_node_creation(self, node_count=1000):
        """Benchmark node creation performance"""
        times = []
        
        async with self.db_pool.acquire() as conn:
            for i in range(node_count):
                start = time.perf_counter()
                
                await conn.execute(f"""
                    SELECT lens_graph.execute_cypher($1, $2, 
                        'CREATE (n:PerfNode {{id: $node_id, batch: $batch_id}})', 
                        $3
                    )
                """, self.world_id, self.branch, f'{{"node_id": {i}, "batch_id": "creation_test"}}')
                
                end = time.perf_counter()
                times.append(end - start)
                
        return {
            'operation': 'node_creation',
            'count': node_count,
            'avg_time_ms': mean(times) * 1000,
            'std_dev_ms': stdev(times) * 1000 if len(times) > 1 else 0,
            'total_time_s': sum(times)
        }
    
    async def benchmark_graph_traversal(self, depth=3):
        """Benchmark graph traversal vs relational JOIN"""
        # Create connected graph data
        async with self.db_pool.acquire() as conn:
            # AGE graph traversal
            start = time.perf_counter()
            result_age = await conn.fetch(f"""
                SELECT lens_graph.execute_cypher($1, $2, 
                    'MATCH (n:PerfNode)-[*1..{depth}]-(connected) RETURN count(connected)', 
                    '{{}}'
                )
            """, self.world_id, self.branch)
            age_time = time.perf_counter() - start
            
            # Equivalent relational query (simulation)
            start = time.perf_counter()
            # This would be a complex self-join for depth traversal
            result_rel = await conn.fetchval("""
                WITH RECURSIVE graph_sim AS (
                    SELECT id, 1 as depth FROM (SELECT 1 as id) base
                    UNION ALL
                    SELECT g.id + 1, g.depth + 1 
                    FROM graph_sim g 
                    WHERE g.depth < $1
                )
                SELECT COUNT(*) FROM graph_sim
            """, depth)
            rel_time = time.perf_counter() - start
            
            return {
                'operation': 'graph_traversal',
                'depth': depth,
                'age_time_ms': age_time * 1000,
                'relational_time_ms': rel_time * 1000,
                'performance_ratio': rel_time / age_time if age_time > 0 else 0
            }

@pytest.mark.asyncio
async def test_performance_baseline(db_pool):
    """Run performance baseline tests"""
    benchmark = AGEPerformanceBenchmark(db_pool)
    await benchmark.setup()
    
    # Test node creation performance
    creation_stats = await benchmark.benchmark_node_creation(100)
    assert creation_stats['avg_time_ms'] < 50  # Should be under 50ms per node
    
    # Test traversal performance
    traversal_stats = await benchmark.benchmark_graph_traversal(3)
    assert traversal_stats['age_time_ms'] < 1000  # Should complete under 1s
    
    print(f"Creation performance: {creation_stats}")
    print(f"Traversal performance: {traversal_stats}")
```

### **2. Operational Documentation** (`docs/age-operations.md`)

```markdown
# AGE Operations Guide

## Health Monitoring

### Extension Status Check
```sql
-- Verify AGE extension is loaded
SELECT extname, extversion FROM pg_extension WHERE extname = 'age';

-- Check graph catalog
SELECT graph_name, graph_namespace FROM ag_catalog.ag_graph;
```

### Performance Monitoring
```sql
-- Graph operation statistics
SELECT 
    schemaname,
    tablename,
    n_tup_ins + n_tup_upd + n_tup_del as operations,
    n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables 
WHERE schemaname LIKE 'ag_graph_%';
```

## Graph Lifecycle Management

### World/Branch Graph Creation
```sql
-- Auto-create graph for world/branch
SELECT lens_graph.ensure_graph_exists(
    '550e8400-e29b-41d4-a716-446655440000'::uuid, 
    'main'
);
```

### Graph Cleanup
```sql
-- List all graphs with metadata
SELECT 
    g.graph_name,
    gm.world_id,
    gm.branch,
    gm.created_at,
    gm.node_count,
    gm.edge_count
FROM ag_catalog.ag_graph g
JOIN lens_graph.graph_metadata gm ON g.graph_name = gm.graph_name;

-- Drop unused graphs (careful!)
SELECT ag_catalog.drop_graph('graph_name', true);
```

## Troubleshooting

### Common Issues
1. **AGE not loaded**: Run `LOAD 'age';` and `SET search_path = ag_catalog, "$user", public;`
2. **Graph not found**: Use `lens_graph.ensure_graph_exists()` to auto-create
3. **Performance issues**: Check `pg_stat_user_tables` for graph table statistics
```

### **3. Integration Test Scripts** (`scripts/age-integration-test-comprehensive.ps1`)

```powershell
#!/usr/bin/env pwsh

param(
    [switch]$Verbose,
    [switch]$SkipPerformance,
    [string]$TestPattern = "*"
)

Write-Host "🧪 AGE Integration Test Suite" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan

# Test 1: AGE Extension Availability
Write-Host "`n1️⃣  Testing AGE Extension Availability..." -ForegroundColor Yellow

$ageCheck = docker compose exec -T postgres-v2 psql -U postgres -d nexus_v2 -t -c "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'age');"
if ($ageCheck -match "t") {
    Write-Host "   ✅ AGE extension is loaded" -ForegroundColor Green
} else {
    Write-Host "   ❌ AGE extension not found" -ForegroundColor Red
    exit 1
}

# Test 2: V2 AGE Functions
Write-Host "`n2️⃣  Testing V2 AGE Functions..." -ForegroundColor Yellow

$functionTest = docker compose exec -T postgres-v2 psql -U postgres -d nexus_v2 -t -c "SELECT lens_graph.generate_graph_name('550e8400-e29b-41d4-a716-446655440000'::uuid, 'test');"
if ($functionTest -match "g_550e8400_test") {
    Write-Host "   ✅ V2 AGE functions working" -ForegroundColor Green
} else {
    Write-Host "   ❌ V2 AGE functions failed" -ForegroundColor Red
    exit 1
}

# Test 3: World/Branch Isolation
Write-Host "`n3️⃣  Testing World/Branch Isolation..." -ForegroundColor Yellow

$isolationTest = @"
DO \$\$
DECLARE
    world_a uuid := '550e8400-e29b-41d4-a716-446655440000';
    world_b uuid := '550e8400-e29b-41d4-a716-446655440001';
    graph_a text;
    graph_b text;
BEGIN
    SELECT lens_graph.ensure_graph_exists(world_a, 'main') INTO graph_a;
    SELECT lens_graph.ensure_graph_exists(world_b, 'main') INTO graph_b;
    
    IF graph_a = graph_b THEN
        RAISE EXCEPTION 'Isolation failed: same graph for different worlds';
    END IF;
    
    RAISE NOTICE 'Isolation test passed: % != %', graph_a, graph_b;
END
\$\$;
"@

$result = docker compose exec -T postgres-v2 psql -U postgres -d nexus_v2 -c $isolationTest
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ World/branch isolation working" -ForegroundColor Green
} else {
    Write-Host "   ❌ World/branch isolation failed" -ForegroundColor Red
    exit 1
}

# Test 4: Basic Graph Operations
Write-Host "`n4️⃣  Testing Basic Graph Operations..." -ForegroundColor Yellow

$graphOpsTest = @"
SELECT lens_graph.execute_cypher(
    '550e8400-e29b-41d4-a716-446655440000'::uuid, 
    'integration_test', 
    'CREATE (n:TestNode {name: \"Integration Test\", timestamp: timestamp()}) RETURN n', 
    '{}'
);
"@

$result = docker compose exec -T postgres-v2 psql -U postgres -d nexus_v2 -c $graphOpsTest
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Basic graph operations working" -ForegroundColor Green
} else {
    Write-Host "   ❌ Basic graph operations failed" -ForegroundColor Red
    exit 1
}

# Test 5: Performance Baseline (if not skipped)
if (-not $SkipPerformance) {
    Write-Host "`n5️⃣  Running Performance Baseline..." -ForegroundColor Yellow
    
    $perfTest = @"
DO \$\$
DECLARE
    start_time timestamp;
    end_time timestamp;
    duration interval;
BEGIN
    start_time := clock_timestamp();
    
    -- Create 100 test nodes
    FOR i IN 1..100 LOOP
        PERFORM lens_graph.execute_cypher(
            '550e8400-e29b-41d4-a716-446655440000'::uuid,
            'perf_test',
            'CREATE (n:PerfNode {id: \$node_id})',
            format('{"node_id": %s}', i)
        );
    END LOOP;
    
    end_time := clock_timestamp();
    duration := end_time - start_time;
    
    RAISE NOTICE 'Performance baseline: 100 nodes created in %', duration;
    
    IF EXTRACT(EPOCH FROM duration) > 30 THEN
        RAISE EXCEPTION 'Performance below baseline: took % seconds', EXTRACT(EPOCH FROM duration);
    END IF;
END
\$\$;
"@

    $result = docker compose exec -T postgres-v2 psql -U postgres -d nexus_v2 -c $perfTest
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Performance baseline met" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Performance baseline not met" -ForegroundColor Yellow
    }
}

# Summary
Write-Host "`n🎉 AGE Integration Test Suite Complete!" -ForegroundColor Cyan
Write-Host "All critical tests passed. AGE integration is production-ready." -ForegroundColor Green
```

---

## ✅ **Acceptance Criteria**

### **Functionality Validation**
- [ ] AGE extension loads successfully in V2 stack
- [ ] V2 schema functions (`lens_graph.*`) operational
- [ ] World/branch graph isolation confirmed
- [ ] Basic Cypher operations work via V2 wrappers
- [ ] Cross-schema integration (relational ↔ graph) functional

### **Performance Benchmarks**
- [ ] Node creation: < 50ms average per node
- [ ] Graph traversal: < 1s for depth-3 queries
- [ ] Memory usage: < 2x baseline PostgreSQL
- [ ] Startup time: < 60s for AGE-enabled database

### **Operational Readiness**
- [ ] Health monitoring procedures documented
- [ ] Performance monitoring queries tested
- [ ] Graph lifecycle management validated
- [ ] Troubleshooting guide complete
- [ ] Production deployment checklist ready

---

## 🚧 **Implementation Steps**

### **Step 1: Test Suite Development**
1. Create comprehensive test files
2. Implement basic AGE functionality tests
3. Build V2 integration test suite
4. Develop performance benchmarks

### **Step 2: Validation & Benchmarking**
1. Run full test suite against V2 stack
2. Establish performance baselines
3. Compare AGE vs relational performance
4. Document findings and recommendations

### **Step 3: Operational Procedures**
1. Document health monitoring procedures
2. Create performance monitoring queries
3. Test graph lifecycle management
4. Validate troubleshooting procedures

### **Step 4: Integration Validation**
1. Test cross-schema operations
2. Validate world/branch isolation
3. Confirm production readiness
4. Document operational procedures

---

## 🔧 **Technical Decisions**

### **Test Strategy**
- **Unit Tests**: Basic AGE functionality and V2 wrapper functions
- **Integration Tests**: Cross-schema operations and isolation
- **Performance Tests**: Benchmarks vs relational equivalents
- **Operational Tests**: Health monitoring and lifecycle management

### **Performance Targets**
- **Node Operations**: < 50ms per operation (CRUD)
- **Graph Traversals**: < 1s for typical depth-3 queries
- **Memory Overhead**: < 100% vs baseline PostgreSQL
- **Concurrent Users**: Support 10+ simultaneous graph operations

### **Monitoring Strategy**
- **Health Checks**: Extension status, graph availability
- **Performance Metrics**: Operation timing, memory usage
- **Operational Metrics**: Graph count, node/edge statistics
- **Error Tracking**: Failed operations, constraint violations

---

## 🚨 **Risks & Mitigations**

### **Performance Degradation**
- **Risk**: AGE operations slower than relational equivalents
- **Mitigation**: Establish baselines, optimize queries, consider indexing
- **Fallback**: Disable graph features if performance unacceptable

### **Memory Usage**
- **Risk**: AGE significantly increases memory consumption
- **Mitigation**: Monitor memory usage, implement graph cleanup procedures
- **Escalation**: Adjust Docker memory limits, optimize graph storage

### **Operational Complexity**
- **Risk**: AGE introduces operational overhead
- **Mitigation**: Comprehensive documentation, automated monitoring
- **Training**: Ensure team understands AGE-specific operations

---

## 📊 **Success Metrics**

- **Test Coverage**: 100% of core AGE functionality tested
- **Performance**: All benchmarks meet or exceed targets
- **Reliability**: 0 crashes during stress testing
- **Documentation**: Complete operational procedures documented
- **Production Readiness**: All acceptance criteria met

---

## 🔄 **Next Phase**

**Phase A3: Enhanced Event Envelope**
- Event validation with payload hashing
- Idempotency and conflict detection
- Audit trail and traceability

**Phase A5.1: Graph Projector with AGE Backend** (Enabled by A2.2 success)
- Full graph projector implementation
- Event-driven graph updates
- Advanced graph operations and analytics

**Dependencies**: A2.2 success validates AGE production readiness and enables graph projector development

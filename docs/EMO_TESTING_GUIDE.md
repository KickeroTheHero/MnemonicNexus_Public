# EMO System Testing Guide

**Version:** 1.0  
**Date:** 2025-01-21  
**Status:** Ready for Execution  

This guide provides comprehensive instructions for testing the EMO (Episodic Memory Object) system capabilities, from quick validation to full system testing.

---

## 🎯 Testing Overview

The EMO testing framework consists of three levels:

1. **Quick Validation** - Fast system readiness check
2. **Capability Testing** - Comprehensive feature validation 
3. **Performance Testing** - Scalability and throughput validation

### Test Tools

| Tool | Purpose | Duration | Prerequisites |
|------|---------|----------|---------------|
| `quick_emo_validation.py` | System readiness check | 30 seconds | Database + Gateway |
| `test_emo_capabilities.py` | Full capability testing | 5-10 minutes | All services running |
| `run_all_emo_tests.py` | Complete orchestrated testing | 10-15 minutes | Full EMO stack |

---

## 🚀 Quick Start

### Step 1: Deploy EMO System

First, ensure the EMO system is running:

```bash
# Deploy full EMO stack
cd infra
docker compose -f docker-compose-emo.yml up -d

# Wait for services to be healthy
docker compose -f docker-compose-emo.yml ps
```

### Step 2: Quick Validation

Run a fast system check:

```bash
# Basic validation
python scripts/quick_emo_validation.py

# Detailed validation with service info
python scripts/quick_emo_validation.py --details --verbose
```

**Expected Output:**
```
✅ PASS Database Connectivity
✅ PASS EMO Schema Presence  
✅ PASS Gateway Service
✅ PASS Search Service
✅ PASS Basic Event Processing
✅ PASS Multi-Lens Status
📊 Validation Summary: 6/6 passed
🎉 EMO system is ready for comprehensive testing!
```

### Step 3: Run Core Tests

Execute core capability tests:

```bash
# Core functionality tests only
python scripts/test_emo_capabilities.py --suite core

# All capability tests  
python scripts/test_emo_capabilities.py --suite all --verbose
```

### Step 4: Complete Test Suite

Run the full orchestrated test suite:

```bash
# Complete testing (recommended)
python scripts/run_all_emo_tests.py

# Performance testing only
python scripts/run_all_emo_tests.py --performance-only
```

---

## 🧪 Detailed Testing Instructions

### Quick Validation (`quick_emo_validation.py`)

**Purpose:** Verify system readiness before comprehensive testing

**What it checks:**
- Database connectivity and EMO schema presence
- Service endpoint availability (Gateway, Search)
- Basic event submission and acceptance
- Projector health status

**Usage:**
```bash
# Standard validation
python scripts/quick_emo_validation.py

# Verbose output with debugging
python scripts/quick_emo_validation.py --verbose

# Detailed JSON output
python scripts/quick_emo_validation.py --details
```

**Success Criteria:**
- All 6 validations must pass
- Database contains EMO schema with required tables
- Gateway accepts test events (201 status)
- At least 2 projectors are healthy

**Troubleshooting:**
```bash
# Check service logs if validation fails
docker logs nexus-gateway
docker logs nexus-projector-rel
docker logs nexus-postgres

# Verify database migration status
docker exec nexus-postgres psql -U postgres -d nexus -c "\dn lens_emo"
```

---

### Capability Testing (`test_emo_capabilities.py`)

**Purpose:** Comprehensive validation of EMO system features

**Test Suites Available:**

#### Core Event Processing (`--suite core`)
- **EMO Creation Flow**: End-to-end `emo.created` processing
- **EMO Update Flow**: Version increment and content updates
- **EMO Linking Flow**: Relationship creation and management
- **EMO Deletion Flow**: Soft delete semantics validation

#### Multi-Lens Projections (`--suite multi-lens`)
- **Relational Lens**: PostgreSQL table consistency
- **Semantic Lens**: Vector embedding generation
- **Graph Lens**: AGE graph node creation

#### Search Capabilities (`--suite search`)
- **Relational Search**: Tag and content queries
- **Semantic Search**: Vector similarity via hybrid service
- **Performance**: Search latency validation

#### Data Integrity (`--suite integrity`)
- **Idempotency**: Duplicate event handling (409 conflicts)
- **Version Conflicts**: Concurrent update resolution
- **Constraint Enforcement**: Database validation rules

**Usage Examples:**
```bash
# Run all tests with verbose output
python scripts/test_emo_capabilities.py --suite all --verbose

# Core functionality only
python scripts/test_emo_capabilities.py --suite core

# Search capabilities only  
python scripts/test_emo_capabilities.py --suite search

# Performance tests only
python scripts/test_emo_capabilities.py --suite performance

# Custom database connection
python scripts/test_emo_capabilities.py --database-url postgresql://user:pass@host:5432/db
```

**Test Results Interpretation:**
```
✅ emo_creation_flow (2.34s)
✅ emo_update_flow (1.87s)  
✅ emo_linking_flow (2.12s)
✅ emo_deletion_flow (1.95s)
✅ relational_search (0.45s)
❌ semantic_search (0.12s) - Search service not available
✅ idempotency_enforcement (1.23s)
```

- **Green (✅)**: Test passed successfully
- **Red (❌)**: Test failed - check error details
- **Yellow (⚠️)**: Test skipped - optional component unavailable

---

### Complete Test Orchestration (`run_all_emo_tests.py`)

**Purpose:** Orchestrated testing with reporting and validation

**Test Phases:**

1. **System Readiness Validation** (30s)
   - Quick validation to ensure system is operational
   - Fails fast if system not ready

2. **Core Capability Testing** (5-8 minutes)
   - All capability tests from previous section
   - Comprehensive feature validation

3. **Performance Testing** (2-3 minutes)
   - Event throughput measurement
   - Search latency validation
   - Resource usage monitoring

4. **Report Generation** (10s)
   - JSON test report with detailed results
   - Summary statistics and recommendations

**Usage:**
```bash
# Complete test suite (recommended)
python scripts/run_all_emo_tests.py

# Skip validation if system known to be ready
python scripts/run_all_emo_tests.py --skip-validation

# Performance testing only
python scripts/run_all_emo_tests.py --performance-only

# Verbose output
python scripts/run_all_emo_tests.py --verbose
```

**Report Output:**
- **Console Summary**: Real-time test progress and final results
- **JSON Report**: `test_reports/emo_test_report_<timestamp>.json`
- **Details**: Test duration, success rates, error analysis

---

## 📊 Understanding Test Results

### Success Indicators

**Complete Success:**
```
🎯 OVERALL RESULT: ✅ SUCCESS
⏱️ Total Duration: 8m 23.4s
📊 Validation Summary: 6/6 passed
📊 Capability Tests: 12/12 passed
📊 Performance Tests: 3/3 passed
🎉 EMO system is fully validated and ready for production!
```

**Partial Success:**
```
🎯 OVERALL RESULT: ⚠️ PARTIAL SUCCESS
📊 Capability Tests: 10/12 passed
❌ Failed Tests:
  - semantic_search: Search service not available
  - graph_lens_age_integration: AGE extension not found
⚠️ Some tests failed - review results before production deployment
```

### Performance Benchmarks

**Target Performance Metrics:**

| Metric | Target | Good | Needs Attention |
|--------|--------|------|-----------------|
| Event Throughput | >500 events/sec | >200 events/sec | <100 events/sec |
| Search Latency | <500ms | <1000ms | >2000ms |
| Processing Latency | <2s end-to-end | <5s | >10s |
| Database Connections | Stable | Growing slowly | Memory leaks |

**Example Performance Results:**
```json
{
  "basic_throughput": {
    "events_submitted": 100,
    "events_processed": 100,
    "submission_throughput": 45.2,
    "processing_rate": 23.1,
    "total_time": 4.33
  }
}
```

---

## 🔧 Troubleshooting Common Issues

### Database Connection Issues

**Symptoms:**
```
❌ FAIL Database Connectivity: connection refused
```

**Solutions:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check database logs
docker logs nexus-postgres

# Verify connection manually
docker exec nexus-postgres psql -U postgres -d nexus -c "SELECT 1"

# Reset database if needed
docker compose -f docker-compose-emo.yml down -v
docker compose -f docker-compose-emo.yml up postgres -d
```

### EMO Schema Missing

**Symptoms:**
```
❌ FAIL EMO Schema Presence: table "emo_current" not found
```

**Solutions:**
```bash
# Check if migrations have run
docker exec nexus-postgres psql -U postgres -d nexus -c "\dt lens_emo.*"

# Run migrations manually
docker exec nexus-postgres psql -U postgres -d nexus -f /docker-entrypoint-initdb.d/010_emo_tables.sql

# Check migration status
ls -la migrations/
```

### Gateway Service Issues

**Symptoms:**
```
❌ FAIL Gateway Service: connection refused
❌ FAIL Basic Event Processing: Event rejected with 500
```

**Solutions:**
```bash
# Check Gateway logs
docker logs nexus-gateway

# Verify Gateway health
curl http://localhost:8086/health

# Restart Gateway
docker compose -f docker-compose-emo.yml restart gateway

# Check Gateway configuration
docker exec nexus-gateway env | grep DATABASE
```

### Projector Health Issues

**Symptoms:**
```
❌ FAIL Multi-Lens Status: Only 1/4 projectors healthy
```

**Solutions:**
```bash
# Check all projector statuses
curl http://localhost:8087/health  # Relational
curl http://localhost:8088/health  # Translator  
curl http://localhost:8089/health  # Graph
curl http://localhost:8091/health  # Semantic

# Check projector logs
docker logs nexus-projector-rel
docker logs nexus-projector-translator
docker logs nexus-projector-graph
docker logs nexus-projector-sem

# Restart failed projectors
docker compose -f docker-compose-emo.yml restart projector-rel
```

### Event Processing Failures

**Symptoms:**
```
❌ emo_creation_flow: EMO not found in relational lens
```

**Solutions:**
```bash
# Check if event reached database
docker exec nexus-postgres psql -U postgres -d nexus -c "SELECT COUNT(*) FROM event_core.event_log WHERE kind = 'emo.created'"

# Check publisher logs for CDC processing
docker logs nexus-publisher

# Verify projector received events
curl http://localhost:8087/metrics | grep events_processed

# Check for processing errors
docker exec nexus-postgres psql -U postgres -d nexus -c "SELECT * FROM lens_emo.emo_current LIMIT 5"
```

---

## 📈 Performance Tuning

### Optimizing for Higher Throughput

**Database Tuning:**
```sql
-- Increase connection pool
ALTER SYSTEM SET max_connections = 200;

-- Optimize for writes
ALTER SYSTEM SET checkpoint_segments = 32;
ALTER SYSTEM SET wal_buffers = 16MB;
```

**Projector Scaling:**
```yaml
# In docker-compose-emo.yml
projector-rel:
  deploy:
    replicas: 2
  environment:
    - WORKER_CONCURRENCY=4
```

**Event Batching:**
```python
# Submit events in batches
async def submit_batch(events):
    tasks = []
    for event in events:
        task = submit_event_async(event)
        tasks.append(task)
    
    await asyncio.gather(*tasks)
```

### Monitoring Performance

**Key Metrics to Track:**
- Event log growth rate
- Projector lag (time between event and projection)
- Database connection pool utilization
- Memory usage per projector
- Search query latency distribution

**Prometheus Metrics:**
```bash
# Gateway metrics
curl http://localhost:8086/metrics

# Projector metrics  
curl http://localhost:8087/metrics
curl http://localhost:8088/metrics
curl http://localhost:8089/metrics
curl http://localhost:8091/metrics
```

---

## 🎯 Test Environment Setup

### Minimal Test Environment

**Requirements:**
- PostgreSQL with EMO schema
- Gateway service
- At least 1 projector (relational recommended)

**Quick Setup:**
```bash
# Minimal stack for testing
docker compose up postgres gateway projector-rel -d

# Run basic tests
python scripts/quick_emo_validation.py
python scripts/test_emo_capabilities.py --suite core
```

### Full Test Environment  

**Requirements:**
- Complete EMO stack from `docker-compose-emo.yml`
- All projectors running
- Search service (optional but recommended)
- Monitoring stack (optional)

**Complete Setup:**
```bash
# Full EMO stack
docker compose -f docker-compose-emo.yml up -d

# Verify all services
docker compose -f docker-compose-emo.yml ps

# Run complete test suite
python scripts/run_all_emo_tests.py
```

### CI/CD Integration

**GitHub Actions Example:**
```yaml
name: EMO System Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Start EMO Stack
      run: docker compose -f infra/docker-compose-emo.yml up -d
      
    - name: Wait for Services
      run: sleep 30
      
    - name: Run EMO Tests
      run: python scripts/run_all_emo_tests.py --skip-validation
      
    - name: Upload Test Reports
      uses: actions/upload-artifact@v2
      with:
        name: test-reports
        path: test_reports/
```

---

## 📋 Test Checklist

### Pre-Testing Checklist

- [ ] EMO stack deployed and running
- [ ] Database contains EMO schema (lens_emo.*)
- [ ] Gateway service healthy (responds to /health)
- [ ] At least 2 projectors healthy
- [ ] Event log table exists and accessible
- [ ] Test fixtures available in tests/fixtures/emo/

### Post-Testing Checklist

- [ ] All core EMO events process successfully
- [ ] Multi-lens projections working correctly
- [ ] Search capabilities functional
- [ ] Data integrity constraints enforced
- [ ] Performance meets acceptable thresholds
- [ ] Test reports generated and reviewed
- [ ] Failed tests analyzed and addressed

### Production Readiness Checklist

- [ ] All capability tests pass (100% success rate)
- [ ] Performance tests meet production requirements
- [ ] Error handling validates correctly
- [ ] Monitoring and observability working
- [ ] Security validation completed
- [ ] Documentation complete and accurate

---

**Ready to test your EMO system? Start with the quick validation and work your way up to the complete test suite!** 🚀

```bash
# Quick start command
python scripts/quick_emo_validation.py && python scripts/run_all_emo_tests.py
```


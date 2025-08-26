_Archived from alpha/s0-migration on 2025-01-20; retained for historical context._

# MnemonicNexus V2 Changelog

**Development Model**: DOCUMENT → IMPLEMENT → TEST  
**Architecture**: Event Sourcing + Multi-Lens Projections + AGE Graph + Comprehensive Tenancy

---

## [V2.0.0-dev] - In Development

### Phase A6 COMPLETE - Gateway 409 Handling + Complete Event Ingestion Pipeline (2025-08-16)

**🎯 Status**: Phase A6 (Gateway 409 Handling) COMPLETED with comprehensive idempotency, validation, and monitoring

#### Major Achievement - Complete V2 Event Ingestion Pipeline Operational
- **🎉 Gateway V2 Complete**: Full FastAPI implementation with comprehensive idempotency and 409 handling
- **✅ Event Ingestion Pipeline**: Complete end-to-end flow from Gateway → Publisher → All 3 Projectors
- **✅ 409 Conflict Handling**: Perfect idempotency conflict detection with proper HTTP status codes
- **✅ Request Validation**: Comprehensive validation with clear error messages and correlation tracking
- **✅ Monitoring Integration**: Prometheus metrics for performance monitoring and alerting

#### Phase A6 Implementation Complete
- **✅ FastAPI Gateway Service**: Complete V2 Gateway with CORS middleware and error handling
- **✅ Pydantic Models**: EventEnvelope, EventAccepted, ErrorResponse with comprehensive validation
- **✅ Enhanced Validation**: Business rule enforcement, header validation, request parameter validation
- **✅ Database Persistence**: Event storage with idempotency checking and graceful watermark handling
- **✅ Prometheus Monitoring**: Comprehensive metrics collection for requests, errors, performance, database
- **✅ Production-Ready Endpoints**: `/v1/events` (POST/GET), `/health`, `/metrics`, `/docs` all operational

#### System Integration Achievements
- **✅ Header-Based Idempotency**: `Idempotency-Key` and `X-Correlation-Id` headers working perfectly
- **✅ Error Response Standardization**: Consistent error format with codes, messages, and correlation IDs
- **✅ Database Integration**: Connection pooling, transaction safety, proper error propagation
- **✅ Docker Health Checks**: Service health monitoring with component status reporting
- **✅ API Documentation**: OpenAPI docs accessible with complete endpoint documentation

### Phase A5.2 COMPLETE - LMStudio Integration Breakthrough + Advanced Semantic Features (2025-08-16)

**🎯 Status**: Phase A5.2 (Semantic Projector) COMPLETED with real LMStudio embedding generation and advanced query capabilities

#### Major Breakthrough - Real LMStudio Integration
- **🎉 LMStudio Integration**: Real 768-dimensional embeddings from `text-embedding-nomic-embed-text-v1.5` operational
- **✅ Event Routing Fix**: Corrected event format from `"NoteCreated"` to `"note.created"` for proper projector routing
- **✅ Multi-Model Architecture**: Support for LMStudio, OpenAI, and sentence-transformers embedding providers
- **✅ End-to-End Pipeline**: Publisher → Semantic Projector → Database with real embedding storage confirmed
- **✅ Database Verification**: Real 768-dimensional vectors stored in `lens_sem.embedding` with proper metadata

#### Advanced Semantic Features Implemented
- **✅ Query Caching**: 5-minute TTL with automatic cleanup and cache hit metrics
- **✅ Optimized Batch Search**: Single-query performance for multiple embedding vectors with deduplication
- **✅ Performance Metrics**: Comprehensive analytics with query timing, cache rates, and index usage tracking
- **✅ Semantic Clustering**: Automatic discovery of similar content clusters with configurable thresholds
- **✅ Advanced FastAPI Endpoints**: `/batch-search`, `/analytics`, `/clusters`, `/cache/clear` for production operations
- **✅ Vector Performance Optimization**: HNSW indexes created (9 specialized indexes) for maximum similarity search performance

#### Infrastructure Enhancements
- **✅ Project Structure Cleanup**: Organized diagnostic tools to `scripts/`, test assets to `tests/` directory
- **✅ Enhanced Documentation**: Updated implementation review to reflect real embedding generation success
- **✅ Vector Database Optimization**: Applied HNSW indexing and composite indexes for optimal query performance
- **✅ Code Quality**: Fixed pre-commit hooks, type annotations, and eliminated technical debt

#### Technical Achievements Beyond Specification
- **Performance**: Single-query batch search with UNION ALL optimization for multiple embeddings
- **Caching Layer**: In-memory query cache with TTL and automatic cleanup
- **Analytics**: Real-time performance metrics and query optimization insights
- **Clustering**: Advanced semantic content discovery with similarity-based grouping
- **Production Ready**: Comprehensive error handling, logging, and operational endpoints

### Phase A5/A5.1 Complete Implementation + Issue Resolution (2025-08-15)

**🎯 Status**: Phase A5 (Python Projector SDK) and A5.1 (Graph Projector with AGE) COMPLETED with comprehensive test validation

#### Added - Complete Projector Framework
- **✅ Python Projector SDK**: Complete abstract base class with watermark management, state hashing, metrics integration
- **✅ All Three Projector Types**: Relational (8083), Graph (8084), Semantic (8085) fully implemented
- **✅ Prometheus Metrics**: Comprehensive monitoring with `ProjectorMetrics` and `MetricsIntegration` classes
- **✅ CDC Publisher Pipeline**: Transactional outbox pattern with event distribution to all projectors
- **✅ Docker Infrastructure**: Complete V2 stack with proper port mapping and networking

#### Fixed - Critical AGE Issues
- **✅ AGE Literal Graph Name Limitation**: Resolved `lens_graph.execute_cypher` issue by using f-string interpolation for graph names
- **✅ Test Infrastructure**: Updated all AGE tests to use direct `cypher()` calls with literal graph names
- **✅ Connection Pooling**: Fixed async fixture issues and proper AGE initialization per connection

#### Previous Issues - All Resolved
- **✅ RESOLVED**: CDC Publisher operational with corrected import paths
- **✅ RESOLVED**: All projector health issues fixed with proper JSON serialization
- **✅ RESOLVED**: Event format validation corrected for proper envelope handling
- **✅ RESOLVED**: Real embedding generation replacing placeholder vectors

### Phase A5.1 Graph Projector + AGE Test Stabilization (2025-01-21)

**🎯 Status**: Phase A5.1 complete with Graph Projector implementation; AGE test infrastructure stabilized via clean refactor approach

#### Added - Graph Projector Implementation
- **Graph Projector Service**: Complete `projectors/graph/` with AGE backend integration
- **Event-Driven Graph Construction**: Handlers for note.created, note.updated, mention.added events
- **Tenant Isolation**: World/branch scoped Cypher queries with parameterized isolation
- **State Snapshot Management**: Graph state capture with deterministic ordering
- **GraphAdapter Typing**: Enhanced interface with execute_cypher method and proper error handling

#### Added - AGE Test Infrastructure Stabilization  
- **Clean Refactor Strategy**: Reverted AGE tests to stable baseline (commit 7b46ef0) with minimal fixes
- **Connection Initialization**: Proper AGE loading and search_path configuration in test fixtures
- **JSON Response Handling**: Fixed V2 wrapper function parsing (execute_cypher, test_age_integration)
- **Idempotent Test Operations**: Added ON CONFLICT DO NOTHING for reliable test re-runs
- **Session-Scoped Fixtures**: Eliminated duplicate connection pools causing agtype errors

#### Technical Achievements - Stability Focus
- **Branching Strategy**: Preserved complex fixes while reverting to proven stable base
- **Minimal Changes**: Applied only essential JSON parsing and connection setup fixes
- **Test Reliability**: Removed race conditions and schema conflicts from concurrent AGE operations
- **Development Workflow**: Demonstrated clean refactor approach for complex integration issues

### Phase A5 Projector SDK + Critical Security Complete (2025-01-20)

**🎯 Status**: Projector SDK operational with RLS tenant isolation, contract validation, GraphAdapter interface, and admin endpoints

#### Added - Core Components
- **Projector SDK Framework**: Complete `projectors/sdk/` with FastAPI HTTP event reception
- **Relational Projector**: Full implementation with idempotent database operations
- **Row Level Security**: Comprehensive RLS policies for tenant isolation with application context
- **GraphAdapter Interface**: Pluggable graph engines with AGE primary + Neo4j fallback
- **Admin Endpoints**: Operational management for projector rebuilds, health checks, tenancy testing

#### Added - Security & Operations
- **Tenant Isolation**: RLS policies on all tables with automatic world_id context setting
- **Contract Validation**: Automated API documentation drift detection (found 29 mismatches)
- **Tenancy Testing**: Comprehensive isolation validation with injection resistance
- **Admin Operations**: Projector rebuild, MV refresh, health monitoring capabilities

#### Technical Achievements - Stratum's Recommendations Implemented
- **RLS Implementation**: Created 6 tenant isolation policies with context management functions
- **Contract Discipline**: API validation detecting documentation drift across 46 vs 20 endpoints
- **GraphAdapter Reality**: Actual AGE implementation with proper graph naming and constraints
- **Operational Tooling**: Background task coordination for projector rebuilds and monitoring

#### Discovery Notes
- **RLS Complexity**: Superuser bypass is expected behavior; application roles required for validation
- **Documentation Drift**: 29 endpoint mismatches identified between docs and OpenAPI spec
- **Graph Naming**: AGE identifiers limited to 63 chars requiring careful tenant/branch encoding
- **Integration Points**: Tenant context must be set per-event, not per-projector instance

#### Files with Planned Obsolescence
- `migrations/v2_004_rls_policies_basic.sql` - Basic RLS for existing tables (→ comprehensive version)
- `services/common/graph_adapter.py:MockNeo4jAdapter` - Neo4j placeholder (→ real driver)
- `scripts/validate_contracts.py` - Basic validation (→ professional OpenAPI tools)
- `PLANNED_OBSOLESCENCE.md` - Complete tracking document for temporary implementations

### Phase A4 CDC Publisher Complete (2025-08-12)

**🎯 Status**: CDC Publisher service operational with comprehensive testing, ready for Phase A5 projector implementation

#### Added
- **CDC Publisher Service**: Complete `services/publisher_v2/` with crash-safe outbox polling
- **Modular Architecture**: Separated `config.py`, `monitoring.py`, `retry.py` for maintainability
- **Comprehensive Testing**: Full smoke test suite validating database integration and event flows
- **Prometheus Metrics**: Outbox lag, publish rates, DLQ monitoring with periodic updates
- **Dead Letter Queue**: Poison message handling with configurable retry policies
- **Docker Integration**: Service containerization with health checks and environment configuration

#### Technical Achievements
- **Transactional Outbox**: Reliable at-least-once delivery using database-managed state
- **Exponential Backoff**: Intelligent retry logic with jitter to prevent thundering herds
- **Database Functions**: Full integration with `get_unpublished_batch`, `mark_published`, `mark_retry`, `move_to_dlq`
- **Smoke Testing**: Validates synthetic event creation, outbox processing, and publish/retry/DLQ flows

### Phase A3 Enhanced Event Envelope Complete (2025-08-12)

**🎯 Status**: Event validation and enrichment operational with payload integrity verification

#### Added
- **EventEnvelope Class**: Strict RFC3339 timestamp validation and payload hash verification
- **Server Enrichment**: Automatic `received_at` and `payload_hash` field injection
- **Validation Middleware**: FastAPI integration with header validation and error handling
- **Database Persistence**: Transactional event storage with idempotency key support
- **Test Coverage**: 17/17 unit tests passing with comprehensive edge case validation

#### Technical Decisions
- **Timestamp Strictness**: RFC3339/ISO8601 with UTC enforcement for global consistency
- **Hash Integrity**: SHA-256 payload verification for tamper detection
- **Version Support**: Envelope versions 1-2 with backward compatibility
- **Error Handling**: Detailed validation error messages for debugging

### Phase A2 V2 Schema & AGE Integration Complete (2025-08-12)

**🎯 Status**: V2 database schema deployed with AGE extension fully operational

#### Added
- **Event Core Schema**: Multi-tenant event log with `world_id` and `branch` isolation
- **Transactional Outbox**: CDC pattern with retry logic and dead letter queue
- **AGE Extension Track**: Custom PostgreSQL+AGE Docker image with graph functions
- **Database Functions**: Complete suite for event validation, hashing, and outbox management
- **Integration Testing**: AGE graph operations with world/branch isolation validated

#### Technical Achievements
- **Custom AGE Image**: `nexus/postgres-age:pg16` with PostgreSQL 16 + AGE 1.5.0 + pgvector 0.8.0
- **Graph Isolation**: World/branch scoped graph naming with `lens_graph.ensure_graph_exists()`
- **Database Migrations**: Clean V2 schema with proper foreign keys and performance indexes
- **Async Testing**: Full pytest-asyncio integration with database and AGE test fixtures

### Phase A1 Infrastructure Complete (2025-08-12)

**🎯 Status**: V2 infrastructure running and validated with comprehensive monitoring

#### Added
- **V2 Docker Stack**: Complete `infra-v2/` with PostgreSQL 16 + pgvector + AGE
- **Gateway V2 Service**: FastAPI with event validation and persistence
- **Publisher V2 Service**: CDC outbox polling with projector delivery
- **Development Workflow**: Enhanced Makefile targets with Windows PowerShell compatibility
- **Port Isolation**: Clean separation (5433, 8081, 8082) from archived V1 services
- **Health Monitoring**: Comprehensive status checks for all infrastructure components

#### Technical Decisions
- **AGE Extension**: Successfully integrated with custom Docker image
- **Infrastructure Stability**: All services running healthy with proper dependency management
- **Test Framework**: Async test infrastructure with database integration testing

### Phase A Documentation Complete (2025-01-15)

**🎯 Status**: All Phase A0-A7 documentation complete with Stratum redlines integrated

#### Added
- **Phase A Prompts**: Complete implementation guides for all Phase A sub-phases (A0-A7)
- **Stratum Redlines**: All 8 critical architecture refinements documented
- **Architecture Completeness**: 1000+ line `docs/architecture.md` with full V2 system design
- **Quality Gates**: `docs/ci-gates.md` with hard acceptance criteria for all phases
- **Determinism Hash**: Algorithm specification for replay validation
- **AGE Graph Naming**: Formal `g_{world_prefix}_{branch}` convention with utilities
- **MV Discipline**: Clear separation between base tables and materialized views

#### Enhanced
- **Idempotency**: Partial UNIQUE index pattern (performance improvement over EXCLUDE)
- **Event Schema**: Added `dead_letter_queue`, confirmed `note_tag` and `link` tables
- **OpenAPI Headers**: Reusable components for `Idempotency-Key`, `X-Correlation-Id`, `X-World-Id`
- **SQL Parameterization**: Fixed `COALESCE($6::timestamptz, now())` pattern in projector examples

#### Status
- **Documentation**: ✅ Complete and ready for implementation
- **Architecture Review**: ✅ All Stratum redlines addressed
- **Contract Validation**: ✅ All API examples validate against OpenAPI
- **Next Phase**: Ready for Phase A1 infrastructure implementation

### Phase A0: Documentation Foundation (2025-01-15)

**🎯 Goal**: Establish clean V2 development foundation

#### Added
- **Documentation Discipline**: `docs/development-workflow.md` with mandatory DOCUMENT → IMPLEMENT → TEST workflow
- **V2 API Contracts**: Updated `docs/openapi.yaml` with V2 event envelope (`world_id`, `by.agent` audit fields)
- **GraphAdapter Interface**: Formalized AGE primary + Neo4j fallback with hard B2 gates
- **VCS Routes**: Added `/v1/vcs/status`, `/v1/vcs/diff` for branch operations
- **Admin Endpoints**: Complete `/v1/admin/projectors/*` API for snapshot/restore/rebuild

#### Archived
- **V1 Documentation**: Moved 8 V1-heavy documents to `archive-v1/docs/` with metadata
- **V1 Implementation**: Complete V1 services archived to `archive-v1/services/`, `archive-v1/migrations/`
- **V1 Siren System**: Archived `siren/` development tracking to `archive-v1/siren-v1/`

#### Changed  
- **Schema References**: Updated validators and Makefile for V2 patterns (`lens_rel.note` vs `rl_note`)
- **Event Envelope**: Require `world_id UUID` and `by.agent` in all events
- **Development Tracking**: Replaced JSON with markdown for better visibility (`siren/checklists/v2-development-progress.md`)

#### Technical Decisions
- **Tenancy Strategy**: `world_id` in every primary key, single tenant in operation
- **Graph Strategy**: AGE primary with Neo4j adapter fallback via configuration
- **Schema Naming**: `lens_rel`, `lens_sem`, `lens_graph` (not `rl_*`, `sl_*`)
- **Contract-First**: All implementation must follow documented OpenAPI contracts

---

## V1 Archive Reference

**V1 Phases 0-9**: Complete implementation archived in `archive-v1/`
- **V1 Changelog**: `archive-v1/CHANGELOG-v1.md`
- **V1 Development Tracking**: `archive-v1/siren-v1/checklists/todo.json`
- **V1 Services**: `archive-v1/services/` (gateway, projectors, snapshot-manager)
- **V1 Infrastructure**: `archive-v1/infra/docker-compose.yml`
- **V1 Migrations**: `archive-v1/migrations/` (event core, relational, graph)

### V1 Achievements Summary
- ✅ **Event Sourcing Core** with DVCS-lite branching
- ✅ **Relational Lens** (PostgreSQL with materialized views)
- ✅ **Semantic Lens** (pgvector with HNSW indexing)
- ✅ **Graph Lens** (Neo4j with branch isolation)
- ✅ **Hybrid Search** (vector + relational + graph fusion)
- ✅ **Snapshots & Rebuild** (point-in-time recovery)
- ✅ **Observability** (Prometheus, Grafana integration)
- ✅ **Admin APIs** (health, watermarks, rebuild operations)

---

## V2 Development Roadmap

### **Phase A: Foundations** ✅ **COMPLETE**
- [x] **A0**: Documentation Foundation & V1 Archival
- [x] **A1**: Fresh V2 Infrastructure (PostgreSQL + AGE + pgvector)
- [x] **A2**: V2 Schema & Event Envelope (tenancy + canonical format)
- [x] **A3**: Enhanced Event Envelope (validation + enrichment)
- [x] **A4**: CDC Publisher Service (crash-safe outbox)
- [x] **A5**: Python Projector SDK (complete)
- [x] **A5.1**: Graph Projector with AGE Backend (complete)
- [x] **A5.2**: Semantic Projector with pgvector Backend ✅ **COMPLETE** - Real LMStudio embeddings + advanced features operational
- [x] **A6**: Gateway 409 Handling ✅ **COMPLETE** - Comprehensive idempotency, validation, and monitoring

### **Phase B: Core Services** 📋 **READY FOR IMPLEMENTATION**
- [ ] **B1**: Multi-Lens Query Engine (cross-projector coordination with semantic search)
- [ ] **B2**: Enhanced Branching (event-sourced VCS operations)
- [ ] **B3**: Advanced Gateway Features (multi-lens query coordination)

### **Phase C: Migration & Integration**
- [ ] **C1**: Archivist Migrator (V1 → V2 transformation)
- [ ] **C2**: Hybrid Search Planner (cross-lens optimization)
- [ ] **C3**: Production Readiness (observability + security)

### **Phase D: Hardening**
- [ ] **D1**: Load Testing & SLO Validation
- [ ] **D2**: Security & Governance
- [ ] **D3**: Documentation & Training

---

## V2 Architecture Highlights

### **Core Improvements over V1**
- **Comprehensive Tenancy**: `world_id` in every operation for true multi-tenant readiness
- **Graph Engine Abstraction**: AGE primary with Neo4j fallback via GraphAdapter interface
- **Schema Organization**: Clean `lens_*` naming with proper isolation
- **Contract-First Development**: OpenAPI drives implementation, not vice versa
- **CI Gates**: Mandatory idempotency, determinism, and crash-safety validation

### **Technology Stack**
- **Event Store**: PostgreSQL 16+ with `uuid-ossp`, `pgcrypto`
- **Semantic Search**: pgvector with HNSW indexing
- **Graph Engine**: Apache AGE (PostgreSQL extension) with Neo4j adapter
- **API Gateway**: FastAPI with OpenAPI contract enforcement
- **Observability**: Prometheus + Grafana + OpenTelemetry
- **Development**: Docker Compose with isolated V2 stack

### **Development Discipline**
- **DOCUMENT**: Update OpenAPI + architecture docs first
- **IMPLEMENT**: Code against documented contracts
- **TEST**: Contract tests + CI gates + SLO validation

---

## Breaking Changes from V1

### **Schema Changes**
- `rl_note` → `lens_rel.note`
- `sl_embedding` → `lens_sem.embedding`
- All tables now require `world_id UUID NOT NULL`

### **API Changes**
- Event envelope requires `world_id` and `by.agent`
- All endpoints scoped by tenancy
- GraphAdapter abstraction replaces direct Neo4j

### **Development Workflow**
- Documentation-first development mandatory
- CI gates enforce determinism and idempotency
- V1 compatibility removed (use Archivist migrator)

---

## Migration Guide

### **For V1 Users**
1. **Reference V1**: All V1 code available in `archive-v1/`
2. **Migration Path**: Use Archivist migrator (Phase C1) when available
3. **Development**: Follow V2 roadmap for new features

### **For New Developers**
1. **Quick Start**: Follow `docs/v2_roadmap.md` Phase A setup
2. **Development**: Read `docs/development-workflow.md`
3. **Architecture**: Study `docs/architecture.md` for V2 patterns

---

*All changes follow semantic versioning. V2 represents a major architectural evolution with comprehensive tenancy and pluggable graph engines.*
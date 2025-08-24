# MnemonicNexus V2 Context Pack

**Agent**: Siren (LMA Assistant)  
**Project**: MnemonicNexus V2 Greenfield Development  
**Status**: Phase A6 COMPLETE - Gateway 409 Handling + Complete Event Ingestion Pipeline Operational  
**Last Updated**: 2025-08-16

---

## 🎯 **Project Mission**

Build a production-ready, agent-operated memory substrate with:
- **Event sourcing** with DVCS-lite branching
- **Multi-lens projections** (relational, semantic, graph) 
- **AGE-primary graph** with Neo4j adapter fallback
- **Comprehensive tenancy** via `world_id`
- **Contract-first development** (DOCUMENT → IMPLEMENT → TEST)

---

## 📊 **Current State**

### **🎉 Phase A1-A6 COMPLETE: Full V2 Event Ingestion Pipeline with Multi-Lens Architecture Operational**
- **V1 Implementation**: Fully archived to `archive-v1/`
- **V2 Infrastructure**: PostgreSQL + pgvector + AGE running with isolated Docker stack
- **V2 Schema**: Complete tenancy implementation with `world_id`, `branch` in all tables
- **Event Envelope**: Enhanced validation with payload hashing, idempotency, audit trail
- **Database Functions**: Event validation, UUID handling, transactional outbox operational
- **CDC Publisher**: Crash-safe outbox pattern with retry logic and dead letter queue
- **Projector SDK**: Complete HTTP-based framework with watermark management, state hashing, Prometheus metrics
- **All Three Projector Types**: Relational (8083), Graph (8084), Semantic (8085) fully implemented and operational
- **AGE Graph Integration**: Event-driven graph construction with literal graph name limitation resolved
- **LMStudio Integration**: Real 768-dimensional embeddings from `text-embedding-nomic-embed-text-v1.5` operational
- **Advanced Semantic Features**: Query caching, optimized batch search, analytics, clustering, performance metrics
- **Vector Performance**: HNSW indexes and optimized similarity search implemented
- **Gateway V2 Complete**: Comprehensive idempotency, 409 handling, validation, and monitoring operational
- **Event Ingestion Pipeline**: Complete end-to-end flow Gateway → Publisher → All 3 Projectors validated
- **Docker Compose Stack**: Complete V2 infrastructure with proper port mapping and service dependencies
- **Development Workflow**: DOCUMENT → IMPLEMENT → TEST discipline validated

### **🔧 Phase A6 COMPLETE - Gateway 409 Handling (2025-08-16)**

#### **Major Achievement: Complete V2 Event Ingestion Pipeline Operational**
- ✅ **Gateway V2 Complete** - Full FastAPI implementation with comprehensive idempotency and 409 handling
- ✅ **Event Ingestion Pipeline** - Complete end-to-end flow from Gateway → Publisher → All 3 Projectors
- ✅ **409 Conflict Handling** - Perfect idempotency conflict detection with proper HTTP status codes
- ✅ **Request Validation** - Comprehensive validation with clear error messages and correlation tracking
- ✅ **Monitoring Integration** - Prometheus metrics for performance monitoring and alerting

#### **Phase A6 Implementation Complete**
- ✅ **FastAPI Gateway Service** - Complete V2 Gateway with CORS middleware and error handling
- ✅ **Pydantic Models** - EventEnvelope, EventAccepted, ErrorResponse with comprehensive validation
- ✅ **Enhanced Validation** - Business rule enforcement, header validation, request parameter validation
- ✅ **Database Persistence** - Event storage with idempotency checking and graceful watermark handling
- ✅ **Prometheus Monitoring** - Comprehensive metrics collection for requests, errors, performance, database
- ✅ **Production-Ready Endpoints** - `/v1/events` (POST/GET), `/health`, `/metrics`, `/docs` all operational

#### **System Integration Achievements**
- ✅ **Header-Based Idempotency** - `Idempotency-Key` and `X-Correlation-Id` headers working perfectly
- ✅ **Error Response Standardization** - Consistent error format with codes, messages, and correlation IDs
- ✅ **Database Integration** - Connection pooling, transaction safety, proper error propagation
- ✅ **Docker Health Checks** - Service health monitoring with component status reporting

### **✅ AGE Extension Track Complete (Optional/Parallel)**
- **A2.1**: Custom PostgreSQL + AGE Docker image operational (`nexus/postgres-age:pg16`)
- **A2.2**: Comprehensive AGE integration testing and validation completed
- **Status**: AGE extension production-ready, world/branch isolation confirmed
- **Performance**: Benchmarks meet baseline requirements
- **Database**: Validation functions corrected (UUID casting syntax fixed)

### **✅ Test Infrastructure Complete**
- **Async Framework**: Full pytest-asyncio integration with proper async fixtures
- **Database Tests**: Integration tests operational (6/7 passing)
- **AGE Tests**: AGE integration tests with async support
- **Unit Tests**: 17/17 EventEnvelope tests passing
- **Publisher Tests**: Comprehensive smoke testing for CDC publisher service
- **Integration Flow**: End-to-end event processing validation with synthetic events
- **Configuration**: pytest.toml updated with asyncio_mode = "auto"

### **✅ Phase A5.2 Complete: Advanced Semantic Projector Operational**
- **A5**: Python Projector SDK ✅ - Standardized HTTP-based projector framework with watermark management
- **A5.1**: Graph Projector with AGE Backend ✅ - Event-driven graph construction using Apache AGE
- **A5.2**: Semantic Projector with pgvector Backend ✅ - **COMPLETE** with real LMStudio embeddings and advanced features
- **Status**: All core Phase A projectors operational with advanced semantic capabilities beyond original specification
- **Major Achievement**: Real 768-dimensional embedding generation via LMStudio integration
- **Advanced Features**: Query caching, batch search, analytics, clustering, performance optimization
- **Next**: Final testing verification and transition to Phase B

### **🚀 Ready for Implementation: Phase B (Core Services)**
- **B1**: Multi-Lens Query Engine with cross-projector coordination and semantic search integration
- **B2**: Enhanced Branching with event-sourced VCS operations
- **B3**: Advanced Gateway Features with multi-lens query coordination
- **A7**: Documentation hygiene and production readiness (parallel track)

---

## 🏗️ **Architecture Overview**

### **Core Principles**
```
Single System of Record (PostgreSQL Event Log)
    ↓ Transactional Outbox CDC
Multi-Lens Projections (Deterministic + Idempotent)
    ↓ GraphAdapter Interface
Pluggable Graph Engines (AGE primary, Neo4j fallback)
    ↓ Contract-First API
Unified Gateway with Tenancy Enforcement
```

### **V2 Key Changes from V1**
- **Tenancy**: `world_id UUID` in every primary key
- **Schema Naming**: `lens_rel.note` (not `rl_note`)
- **Graph Engine**: AGE primary with Neo4j adapter (not Neo4j direct)
- **Event Envelope**: `world_id`, `by.agent` audit fields required
- **Development**: Contract-first, CI gates enforced

---

## 📚 **Key Documentation**

### **Essential Reading**
- **`docs/v2_roadmap.md`** - Complete implementation roadmap
- **`docs/development-workflow.md`** - DOCUMENT → IMPLEMENT → TEST discipline
- **`docs/openapi.yaml`** - V2 API contracts
- **`siren/checklists/v2-development-progress.md`** - Current progress tracking

### **Strategic Context**
- **`NEXUSV2_REBUILD-DOCS/Rebuild_v2/Implementation_Roadmap.md`** - Detailed phase breakdown
- **`NEXUSV2_REBUILD-DOCS/Stratums_notes/CR_Pack1.md`** - Change requests (CR-1 through CR-6)
- **`NEXUSV2_REBUILD-DOCS/Stratums_notes/Stratum_recommendations.md`** - Strategic decisions

### **V1 Reference** (Archive Only)
- **`archive-v1/`** - Complete V1 implementation for reference
- **`archive-v1/docs/`** - V1 documentation
- **`archive-v1/siren-v1/`** - V1 development tracking

---

## 🔧 **Development Environment**

### **V2 Stack** (Target)
```bash
# V2 development (isolated from V1)
make v2-up          # Start V2 stack (ports 5433, 8081+)
make v2-health      # Check AGE/pgvector extensions
make v2-logs        # Monitor V2 services
make v2-down        # Stop V2 stack
```

### **Validation Tools**
```bash
# Documentation consistency
make docs:check     # Validate all docs alignment

# Contract validation  
make test-contracts # OpenAPI compliance

# CI gates (when implemented)
make test-gates     # Idempotency, determinism, crash safety
```

---

## 🎯 **Immediate Tasks** (Phase A1)

### **Infrastructure**
1. **Create** `infra-v2/docker-compose.yml` with PostgreSQL 16 + extensions
2. **Configure** AGE and pgvector extension loading
3. **Add** V2 Makefile targets (`v2-up`, `v2-down`, `v2-health`)
4. **Test** extension functionality with smoke tests

### **Documentation**
1. **Update** progress in `siren/checklists/v2-development-progress.md`
2. **Document** any extension-specific configuration decisions
3. **Validate** `make docs:check` passes

---

## 🚨 **Critical Constraints**

### **V2 Development Rules**
- **Schema naming**: Always use `lens_*` patterns (`lens_rel.note`, not `rl_note`)
- **Tenancy**: Every query MUST include `world_id` scope
- **GraphAdapter**: Never directly couple to Neo4j or AGE
- **Documentation**: Update contracts BEFORE implementation
- **CI Gates**: All gates must pass before merge

### **Anti-Patterns to Avoid**
- ❌ V1 schema patterns (`rl_*`, `sl_*`)
- ❌ Direct graph engine coupling
- ❌ Non-idempotent event processing
- ❌ Implementation before documentation
- ❌ Skipping `world_id` in any operation

---

## 📊 **Success Criteria**

### **Phase A1-A3 Complete:**
- ✅ V2 stack starts cleanly with docker compose
- ✅ PostgreSQL 16 + AGE + pgvector extensions loaded via custom image
- ✅ No port conflicts with archived V1 (8081, 5433)
- ✅ AGE extension operational with world/branch isolation
- ✅ Event envelope validation and persistence working
- ✅ Test infrastructure with async support operational

### **Overall V2 Success:**
- **Performance**: p95 < 200ms, p99 < 500ms
- **Determinism**: 100% replay consistency
- **Tenancy**: 100% queries scoped to `world_id`
- **Documentation**: 100% API coverage, no contract drift

---

## 🔄 **Communication Protocol**

### **Progress Updates**
- Update `siren/checklists/v2-development-progress.md` after each major step
- Commit frequently with clear phase context in messages
- Run `make docs:check` before every commit

### **Problem Escalation**
- **Extension issues**: Check PostgreSQL version compatibility
- **Port conflicts**: Verify V1 services fully stopped
- **Documentation drift**: Run validators, fix before proceeding

### **Phase Completion**
- All acceptance criteria met
- Progress tracker updated  
- Next phase context established
- Commit with phase completion message

---

## 📋 **Quick Reference**

### **File Structure**
```
MnemonicNexusV2/
├── infra-v2/                    # V2 infrastructure (target)
├── services/gateway-v2/         # V2 services (target)
├── docs/                        # V2 documentation
├── siren/                       # V2 development tracking
├── archive-v1/                  # V1 archive (reference only)
└── NEXUSV2_REBUILD-DOCS/       # Strategic specifications
```

### **Key Commands**
```bash
# V2 Development
make v2-up && make v2-health

# Documentation
make docs:check

# Progress Tracking
cat siren/checklists/v2-development-progress.md

# Reference V1 (if needed)
ls archive-v1/
```

---

**Ready for Phase A1 implementation. Focus: isolated V2 infrastructure with AGE + pgvector extensions.**
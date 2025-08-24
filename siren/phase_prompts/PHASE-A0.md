# PHASE A0: Documentation-First V2 Foundation

**Objective**: Establish DOCUMENT → IMPLEMENT → TEST discipline and clean V2 documentation foundation

**Prerequisites**: Greenfield V2 rebuild decision made, strategic documents reviewed

---

## 🎯 **Goals**

### **Primary**
- Archive all V1 artifacts cleanly while preserving historical context
- Rebuild essential documentation as V2-native specifications
- Establish contract-first development discipline
- Create clean development foundation for Phase A1+ implementation

### **Non-Goals**
- Any code implementation (Phase A1+ scope)
- V1 system deprecation or shutdown
- Complete documentation coverage (iterative improvement)

---

## 📋 **Deliverables**

### **1. V1 Artifact Archive**
- Complete audit of repository for V1 artifacts
- Systematic archival to `archive-v1/` with metadata
- Clean separation between historical V1 and active V2

### **2. V2 Core Documentation**
```
docs/
├── architecture.md          # Complete V2 system design
├── api.md                   # V2 Gateway contracts & examples  
├── openapi.yaml             # V2 API specification
├── v2_roadmap.md            # Phase-by-phase implementation plan
├── development-workflow.md   # DOCUMENT → IMPLEMENT → TEST discipline
├── ci-gates.md              # V2 quality gates and acceptance criteria
└── DOCS_CHANGE_POLICY.md    # Documentation maintenance policy
```

### **3. Contract-First Tooling**
```makefile
# Documentation validation targets
docs:check     # Validate all documentation consistency
docs:scrub     # Check for V1 artifacts and broken links
docs:doclint   # CI-ready documentation lint gate

# Contract validation
test-contracts # Validate API examples against OpenAPI spec
openapi:validate # OpenAPI specification syntax validation
```

### **4. V2 Event Envelope Specification**
```json
{
  "world_id": "550e8400-e29b-41d4-a716-446655440000",
  "branch": "main",
  "kind": "note.created", 
  "payload": { "title": "Example" },
  "by": { "agent": "beacon-archivist" },
  "occurred_at": "2025-01-15T10:30:00.123Z",
  "version": 1,
  "causation_id": "event-123"
}
```

**Headers (Optional)**:
```
X-Correlation-Id: req-456     # Server correlation
Idempotency-Key: client-789   # Client idempotency  
```

---

## ✅ **Acceptance Criteria**

### **Archive Quality**
- [x] All V1 artifacts moved to `archive-v1/` with comprehensive metadata
- [x] Zero V1 references in active `docs/` directory
- [x] Historical context preserved with clear V1 → V2 mapping

### **Documentation Foundation**
- [x] `docs/architecture.md` defines complete V2 system design
- [x] `docs/api.md` has consistent examples with `world_id` tenancy
- [x] `docs/openapi.yaml` is syntactically valid and complete
- [x] All documentation follows V2 naming (`lens_rel.*`, not `rl_*`)

### **Contract Validation**
- [x] `make docs:check` passes all validation
- [x] `make test-contracts` validates API examples against OpenAPI
- [x] Event envelope examples comply with `siren/specs/event.schema.json`
- [x] No banned V1 phrases in documentation

### **Development Discipline**
- [x] `docs/development-workflow.md` mandates DOCUMENT → IMPLEMENT → TEST
- [x] `docs/ci-gates.md` defines hard acceptance criteria for each phase
- [x] Clear phase progression rules with no implementation shortcuts

---

## 🚧 **Implementation Steps**

### **Step 1: V1 Artifact Audit**
1. Systematic scan of entire repository for V1 artifacts
2. Identify files by V1 patterns (`rl_*`, `sl_*`, old phase numbering)
3. Create comprehensive archive plan with preservation metadata

### **Step 2: Clean Archive Process**
1. Move V1 files to `archive-v1/` with timestamped subdirectories
2. Create `ARCHIVE_INFO.md` files documenting what was archived and why
3. Verify complete removal of V1 references from active codebase

### **Step 3: V2 Documentation Rebuild**
1. Rebuild `docs/architecture.md` with V2 principles and tenancy
2. Update `docs/api.md` with V2 envelope structure and examples
3. Ensure `docs/openapi.yaml` reflects header-based idempotency
4. Document V2 phase roadmap with clear acceptance criteria

### **Step 4: Contract Validation Setup**
1. Fix `siren/validators/` to work with V2 structure
2. Create Makefile targets for documentation validation
3. Set up contract testing between OpenAPI and examples
4. Implement banned phrase detection for V1 artifacts

---

## 🔧 **Technical Decisions**

### **Archive Strategy**
- **Timestamped Archives**: `archive-v1/YYYY-MM-DD/` for clear versioning
- **Metadata Preservation**: Each archive includes context and migration notes
- **Complete Separation**: No references from V2 docs to archived content

### **Documentation Standards**
- **Tenancy First**: All examples include `world_id` and branch scoping
- **Header-Based**: Idempotency and correlation via HTTP headers
- **Schema Consistency**: `lens_rel.*`, `lens_sem.*`, `lens_graph.*` naming

### **Validation Discipline**
- **No Implementation Shortcuts**: Documentation must precede all code
- **Contract Testing**: API examples must validate against OpenAPI spec
- **Continuous Validation**: CI gates prevent documentation drift

---

## 🚨 **Risks & Mitigations**

### **Documentation Drift**
- **Risk**: V2 documentation becomes inconsistent or outdated
- **Mitigation**: Automated validation in CI, clear change policies

### **Archive Loss**
- **Risk**: Important V1 context lost during cleanup
- **Mitigation**: Comprehensive archival metadata, staged cleanup process

### **Development Impatience**
- **Risk**: Pressure to skip documentation-first discipline
- **Mitigation**: Hard CI gates, clear phase acceptance criteria

---

## 📊 **Success Metrics**

- **Documentation Coverage**: 100% of V2 contracts documented before implementation
- **Validation Success**: All `make docs:check` targets pass consistently
- **Archive Completeness**: Zero V1 artifacts in active codebase
- **Contract Compliance**: All API examples validate against OpenAPI specification

---

## 🔄 **Next Phase**

**Phase A1**: Fresh V2 Infrastructure Setup
- Docker Compose V2 stack with isolated ports
- PostgreSQL + AGE + pgvector extensions
- Basic service stubs and health checks

**Dependencies**: A0 documentation foundation enables confident A1 implementation

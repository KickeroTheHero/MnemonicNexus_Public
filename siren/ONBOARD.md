# MnemonicNexus V2 Development — Siren Onboarding

**Agent**: Siren (Cursor LMA)  
**Project**: MnemonicNexus V2 Greenfield Development  
**Current Phase**: A5.2  
**Development Model**: DOCUMENT → IMPLEMENT → TEST

---

## 🎯 **Quick Start**

### **Immediate Action**
**Start Phase A5.2**: Implement Semantic Projector with pgvector backend for vector embeddings

### **Essential Reading** (in order)
1. **`siren/context_pack.md`** - Current status and V2 architecture overview
2. **`siren/phase_prompts/PHASE-A5.2.md`** - Semantic projector implementation instructions  
3. **`docs/development-workflow.md`** - DOCUMENT → IMPLEMENT → TEST discipline

### **Progress Tracking**
- **Current Status**: `siren/checklists/v2-development-progress.md`
- **Documentation Validation**: `siren/checklists/docs_parity_checklist.md`

---

## 🏗️ **V2 Development Discipline**

### **Mandatory Workflow: DOCUMENT → IMPLEMENT → TEST**
1. **DOCUMENT**: Update OpenAPI + architecture docs before any implementation
2. **IMPLEMENT**: Code against documented contracts  
3. **TEST**: Contract tests + CI gates + SLO validation

### **Core Development Rules**
- **Contract-First**: OpenAPI drives implementation, never the reverse
- **Tenancy-Aware**: Every operation must include `world_id` scope
- **GraphAdapter**: Never couple directly to Neo4j or AGE - always use adapter interface
- **V2-Native**: All patterns use `lens_*` schemas, V2 event envelope, comprehensive tenancy

### **Critical Patterns**
- **Event Envelope**: `world_id`, `by.agent` required in all events
- **Schema Naming**: `lens_rel.*`, `lens_sem.*`, `lens_graph.*` (never `rl_*`, `sl_*`)
- **Primary Keys**: `(world_id, branch, ...)` in every table
- **GraphAdapter**: Interface abstraction (AGE primary, Neo4j fallback)

---

## 🚨 **CI Gates (Hard Blockers)**

These **MUST PASS** before any PR merges:
- **Idempotency**: Duplicate event → 409 response
- **Determinism**: Full replay → identical determinism hash  
- **Crash Safety**: Publisher crash during load → no event loss
- **GraphAdapter Parity**: Swap adapters → identical query results
- **SLO Compliance**: p95 query performance targets

---

## 🎯 **Current Focus: Phase A5.2**

### **Goal**: Semantic Projector with pgvector backend for vector embeddings and similarity search

### **Deliverables**
- [ ] `projectors/semantic/` service with pgvector backend
- [ ] Multi-model embedding support (OpenAI, Sentence Transformers)
- [ ] Vector storage for note titles, bodies, and tags with granular vectors
- [ ] Semantic similarity search interface with configurable thresholds
- [ ] Event-driven embedding generation pipeline

### **Acceptance Criteria**
- [ ] Embedding generation for all note content (< 2s p95 latency)
- [ ] Cosine similarity search with configurable thresholds
- [ ] Model versioning and embedding consistency
- [ ] Integration with existing lens_sem schema
- [ ] Tenant isolation with world_id/branch scoping

---

## 🚫 **Anti-Patterns (Rejected)**

### **Documentation Shortcuts**
- ❌ "Code is the documentation"
- ❌ Implementation before API design
- ❌ Updating docs after merging code

### **Schema Violations**
- ❌ V1 schema patterns (`rl_*`, `sl_*`)
- ❌ Direct database access without tenancy (`world_id`)
- ❌ Missing `by.agent` audit fields in events

### **Architecture Violations**
- ❌ Hardcoded graph engine (Neo4j/AGE) in Gateway
- ❌ Non-idempotent event processing
- ❌ Cross-branch data leaks

---

## 📚 **File Structure & Key References**

### **Development Context**
```
siren/
├── ONBOARD.md                     ← This file (start here)
├── context_pack.md                ← Project overview & current state
├── checklists/
│   ├── v2-development-progress.md ← Phase tracking
│   └── docs_parity_checklist.md   ← V2 validation rules
└── phase_prompts/
    └── PHASE-A1.md                ← Current phase instructions
```

### **V2 Architecture**
```
docs/
├── development-workflow.md        ← DOCUMENT → IMPLEMENT → TEST
├── openapi.yaml                   ← V2 API contracts
├── architecture.md                ← System design (to be rebuilt)
└── v2_roadmap.md                  ← Complete implementation plan
```

### **V1 Archive** (Reference Only)
```
archive-v1/                        ← Complete V1 preservation
├── docs/                          ← V1 documentation
├── services/                      ← V1 implementation
└── siren-v1/                      ← V1 development tracking
```

---

## 🔧 **Development Environment**

### **V2 Stack Commands** (Target)
```bash
# V2 development (isolated from V1)
make v2-up          # Start V2 stack (ports 5433, 8081+)
make v2-health      # Check AGE/pgvector extensions
make v2-logs        # Monitor V2 services
make v2-down        # Stop V2 stack
```

### **Validation Commands**
```bash
# Documentation consistency
make docs:check     # Validate all docs alignment

# Contract validation  
make test-contracts # OpenAPI compliance

# CI gates (when implemented)
make test-gates     # All hard blocker tests
```

---

## 🎯 **Success Metrics**

### **Phase A5.2 Complete When**
- [ ] Semantic projector service operational with pgvector backend
- [ ] Multi-model embedding pipeline processing all note events
- [ ] Vector similarity search responding within SLO (< 1s)
- [ ] Embedding consistency maintained across model versions
- [ ] Integration tests passing with tenant isolation

### **Overall V2 Success**
- **Performance**: p95 < 200ms, p99 < 500ms
- **Determinism**: 100% replay consistency
- **Tenancy**: 100% queries scoped to `world_id`
- **Documentation**: 100% API coverage, no contract drift

---

## 📞 **Communication Protocol**

### **Progress Updates**
- Update `siren/checklists/v2-development-progress.md` after each major step
- Commit frequently with clear phase context in messages
- Run `make docs:check` before every commit

### **Phase Completion**
- All acceptance criteria met
- Progress tracker updated  
- Next phase context established
- Commit with phase completion message

---

**🚀 Ready for Phase A5.2 implementation. Focus: Semantic Projector with pgvector backend for multi-model embeddings and vector similarity search.**

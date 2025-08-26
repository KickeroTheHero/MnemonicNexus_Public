_Archived from alpha/s0-migration on 2025-01-20; retained for historical context._

# Architecture Decision Records (ADRs)

## ADR-001: Single-MoE Controller Architecture

**Status**: Accepted
**Date**: 2024-01-15
**Context**: S0 Migration

### Context

We need to implement a controller architecture that supports:
- Structured JSON output validation
- Tool bus execution with timeouts/retries
- Deterministic decision recording
- Observable metrics and health checking

### Decision

Implement a Single Mixture-of-Experts (MoE) controller using LM Studio structured output.

**Architecture**:
```
mnx/inference/moe_controller/
├── controller.py          # Main controller logic
├── client_lmstudio.py     # LM Studio client
├── tool_bus.py           # Tool execution bus
├── validators.py         # JSON schema validation
├── event_emitter.py      # Decision record emission
└── prompts/             # Prompt templates
```

**Flow**:
1. Prompt model → `tool_intent.v1` (JSON only)
2. Tool bus executes across lenses/web
3. Prompt model with results → `brief.v1` (JSON only)
4. Build `decision_record.v1`, compute hash, POST to Gateway

### Options Considered

1. **Multi-MoE**: Multiple specialized models
   - ❌ Complex routing logic
   - ❌ Model management overhead

2. **Single-MoE**: One model with structured output
   - ✅ Simple architecture
   - ✅ Deterministic validation
   - ✅ LM Studio integration

3. **Rule-based**: No ML model
   - ❌ Limited adaptability
   - ❌ No natural language understanding

### Consequences

**Positive**:
- Simple deployment and debugging
- Deterministic output validation
- Clear tool bus abstraction
- Observable metrics

**Negative**:
- Single point of failure
- Model-dependent quality
- Limited parallelization

---

## ADR-002: Schema-First API Contracts

**Status**: Accepted
**Date**: 2024-01-15
**Context**: S0 Migration

### Context

Need standardized contracts for:
- Tool intentions from the model
- Brief outputs for decision making
- Decision records for audit trails

### Decision

Use JSON Schema contracts in `schemas/json/*.json` with strict validation.

**Contracts**:
- `tool_intent.v1.json` - Model's tool execution plan
- `brief.v1.json` - Structured decision brief
- `decision_record.v1.json` - Canonical decision record

**Validation Policy**: Retry once on invalid JSON, then degrade with `validation_failed=true`.

### Options Considered

1. **OpenAPI Only**: Single specification
   - ❌ Tool/brief schemas not REST APIs
   - ❌ Mixed concerns

2. **Embedded Schemas**: Inline in code
   - ❌ Not version controlled
   - ❌ Hard to validate externally

3. **Separate JSON Schemas**: Dedicated contract files
   - ✅ Version controlled
   - ✅ External validation
   - ✅ Clear contracts

### Consequences

**Positive**:
- Clear interface contracts
- External validation capability
- Version control of schemas
- Deterministic structure

**Negative**:
- Schema maintenance overhead
- Breaking changes require careful migration

---

## ADR-003: Main-First Development Strategy

**Status**: Accepted
**Date**: 2024-01-15
**Context**: S0 Migration

### Context

Need development strategy that:
- Minimizes merge conflicts
- Enables rapid iteration
- Maintains stable main branch
- Supports small team collaboration

### Decision

Use "Main-First" development with short-lived PRs directly to `main`.

**Guidelines**:
- All PRs target `main` (no long-lived branches)
- Keep PRs small (≤200 LOC where possible)
- Delete feature branches immediately after merge
- Use `git mv` for renames, track in `docs/rename_ledger.csv`

### Options Considered

1. **GitFlow**: Feature/develop/release branches
   - ❌ Too complex for small team
   - ❌ Long-lived branches cause conflicts

2. **GitHub Flow**: Feature branches to main
   - ❌ Long-lived feature branches
   - ❌ Merge conflicts on large changes

3. **Main-First**: Direct PRs to main
   - ✅ Simple workflow
   - ✅ Rapid iteration
   - ✅ Stable main branch

### Consequences

**Positive**:
- Simple workflow
- Reduced merge conflicts
- Fast feedback loop
- Always deployable main

**Negative**:
- Requires discipline for small PRs
- Less isolation of experimental features
- Requires robust CI to protect main

---

## ADR-004: LM Studio Integration

**Status**: Accepted
**Date**: 2024-01-15
**Context**: S0 Migration

### Context

Need reliable ML inference that supports:
- Structured JSON output
- Local development
- Deterministic responses
- Model flexibility

### Decision

Use LM Studio as the inference backend with Mixtral-8x7B-Instruct model.

**Configuration**:
- Model: `Mixtral-8x7B-Instruct-v0.1-GGUF/mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf`
- Endpoint: `http://localhost:1234`
- JSON Mode: Structured output enforced

### Options Considered

1. **OpenAI API**: Cloud service
   - ❌ External dependency
   - ❌ Cost implications
   - ❌ Data privacy concerns

2. **Ollama**: Local inference
   - ❌ Less stable structured output
   - ❌ Model management complexity

3. **LM Studio**: Local GUI + API
   - ✅ Reliable structured output
   - ✅ Easy model management
   - ✅ Local development friendly

### Consequences

**Positive**:
- Local development
- No external API costs
- Reliable structured output
- Easy model switching

**Negative**:
- Development dependency
- Hardware requirements
- Single inference backend

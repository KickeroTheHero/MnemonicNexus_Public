_Archived from alpha/s0-migration on 2025-01-20; retained for historical context._

# MNX Alpha S0 Migration Roadmap

## Overview

This roadmap outlines the S0 migration to implement a Single-MoE controller with deterministic goldens and comprehensive observability.

## Phase: S0 Migration (Current)

### Goals
- Activate thin MoE controller with LM Studio structured output
- Normalize contracts & docs
- Wire CI gates
- Add deterministic goldens
- Implement baseline evidence collection

### Key Components
1. **Single-MoE Controller** (`mnx/inference/moe_controller/`)
2. **Schema Contracts** (`schemas/json/*.json`)
3. **Tool Bus** with timeout/retry semantics
4. **Golden Test Suite** with replay capability
5. **Observability** with Prometheus metrics

## PR Sequence

### ✅ PR-1: Docs & Gates
- Documentation structure
- CI workflows
- Pre-commit hooks
- Scripts scaffolding

### 🔄 PR-2: Schemas & Controller Skeleton
- Schema contracts in `schemas/json/`
- MoE controller structure
- Validation framework
- Unit tests

### ⏳ PR-3: Tool Bus & Timeouts
- Tool execution (relational/pgvector/AGE/web)
- Timeout and row cap enforcement
- Retry and degradation logic
- Peer hooks (disabled by default)

### ⏳ PR-4: Compose/Make/Quickstart
- Docker composition
- Make targets
- Development workflow
- Quickstart documentation

### ⏳ PR-5: Goldens & Replay
- Six golden test scenarios
- Replay harness
- Deterministic hash validation
- Citation enforcement

## Acceptance Criteria

- [ ] `schemas/json/*.json` present with passing tests
- [ ] `mnx/inference/moe_controller/*` implemented with unit tests
- [ ] Goldens added with stable replay (`decision_hash` unchanged with fixed seed)
- [ ] `docs/api.md` generated from `schemas/openapi.yaml`
- [ ] All workflows green (docs-chain, repo-gates, schemas-validate, golden-replay)
- [ ] Rename ledger updated for all moves
- [ ] RAG calls degrade cleanly when `RAG_ENABLE=0`
- [ ] Tag `alpha-s0` created

## Post-S0 Roadmap

### S1: Hybrid Search
- Search fusion implementation
- Rank version tracking
- Performance optimization

### S2: Multi-Tenant Scale
- Enhanced tenancy isolation
- Performance benchmarks
- Production hardening

### S3: Advanced Features
- Peer cohabitation
- Advanced RAG
- Custom tool extensions

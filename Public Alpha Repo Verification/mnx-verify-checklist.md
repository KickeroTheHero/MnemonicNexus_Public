# MNX A6 / S0 Completion Checklist & Success Metrics

**Purpose**: Define what it means for Phase A6 (Alpha Baseline) / Stage S0 to be complete. This checklist, test suite outline, and observability list ensures both private and public repos can be validated consistently.

---

## ✅ Completion Criteria

### Event Ingest & Gateway

* [x] Duplicate events return **409 Conflict** (idempotency enforced).
* [x] Correlation IDs propagate end-to-end (Gateway → Event Log → Projectors).
* [ ] Sustained ingest throughput ≥ **1000 events/sec** in test harness.
* [x] Transactional outbox ensures crash safety (no event loss on restart).
* [x] Gateway enforces tenancy (world_id required on every request).

### Determinism & Replay

* [x] Replay from genesis yields **identical state** across all lenses.
* [x] State hashes remain **stable across rollouts/restarts**.
* [x] Golden fixture replays pass in CI.
* [ ] Branch create/merge/rollback replays to the same checksums.

### Projectors

* [x] **Relational Projector**: Base tables + MVs refresh deterministically.
* [x] **Semantic Projector**: LMStudio embeddings (768‑dim vectors) operational; HNSW index responds < 1s @ top‑k=50.
* [x] **Graph Projector**: AGE queries scoped to `(world_id, branch)`; branch isolation verified.
* [x] Projectors emit watermarks and expose lag/staleness metrics.

### Multi‑Tenancy

* [x] All queries scoped by `world_id` UUID.
* [x] Branch heads independent; merge/replay safe.
* [x] RLS policies block cross‑tenant leakage.
* [x] Separate AGE graphs created per `(world_id, branch)`.

### Observability & Ops

* [x] Prometheus exports: ingest rate, projector lag, MV staleness, replay hash parity.
* [x] Each service exposes `/health` endpoint.
* [x] Operator can run `make health-check` → determinism & lag checks.
* [x] Logs show correlation IDs, ingest confirmations, replay parity messages.
* [x] Tracing correlation IDs propagate across Gateway, Publisher, and Projectors.

### CI & Developer Workflow

* [x] Lint and type checks enforced (ruff, mypy or equivalent).
* [x] Tests directory includes **unit**, **integration**, and **golden** fixtures.
* [x] PRs fail on schema drift in OpenAPI/JSON contracts.
* [x] Baseline snapshot (`baseline.sha`) generated and verified in CI.

---

## 🧪 Test Suite Outline

### Unit Tests

* Envelope validation (tenancy, schema, idempotency).
* Commit hash determinism.
* CDC publisher retry logic.
* RLS enforcement at DB layer.

### Integration Tests

* **Ingest loop**: POST → Event Log → Outbox → Projectors → verify rows written.
* **Duplicate events**: second POST returns 409; no duplicate rows.
* **Replay parity**: snapshot DB → replay genesis → verify hash equality.
* **Branch isolation**: events in branch A never surface in branch B queries.
* **Observability endpoints**: /health and /metrics return valid responses.

### Performance Tests

* Ingest stress test: 1000 events/sec sustained.
* Semantic query latency p95 < 200ms for top‑k=50.
* Graph traversal latency p95 < 300ms with 1k nodes.
* Projector lag < 100ms under burst load.

### Observability Tests

* Projector lag < 100ms under load.
* MV staleness export visible.
* Health checks return 200 OK across all components.
* Replay hash mismatches trigger alerts.

---

## 👀 What to Observe (Operator Checklist)

* **Gateway logs**: correlation IDs consistent, 409 conflicts on duplicates.
* **DB state**: `world_id` scoping visible; replay hashes stable.
* **Prometheus dashboard**: ingest throughput, projector lag, MV staleness metrics.
* **Semantic queries**: embedding search returns relevant top‑k with sub‑second response.
* **Graph queries**: AGE isolation by branch verified.
* **make health-check**: reports green for all services.
* **CI pipeline**: passes contracts validation, replay parity, determinism checks, lint/tests.

---

## 🔎 Additional Items Often Missed (Add to your checks)

### Security & Policy

* [ ] **DB roles least‑privilege** (separate app, projector, admin roles; RLS validated with negative tests).
* [ ] **Authn/Authz gate** on Gateway (even if simple token) + **rate limits** to prevent abuse.
* [ ] **PII posture** documented (even if “none expected”); redaction path stubbed for S4.

### Build, Versions, Supply Chain

* [ ] **Model/version pins** recorded (LMStudio model name + checksum); embeddings determinism noted.
* [ ] **Dependency lockfiles** present; **SBOM** (e.g., `syft`) artifact published in CI.
* [ ] **Image digests** pinned in `docker-compose` (not floating `:latest`).

### Data Integrity & Ops

* [ ] **Backups** (event log + lenses) scheduled; **restore drill** documented and tested.
* [ ] **CDC DLQ** present; replay of dead letters tested.
* [ ] **Watermarks/backpressure**: visible metrics + alert thresholds defined.
* [ ] **MV refresh policy** documented (intervals) + **staleness thresholds** with alerts.
* [ ] **Disk growth** monitors for vectors/AGE; VACUUM/REINDEX/ANALYZE maintenance plan.

### Determinism Hardening

* [ ] **Fixed RNG seeds** + **stable time sources** in tests (no `now()` without control).
* [ ] **Golden dataset management** (fixtures versioned, rebuild script deterministic).
* [ ] **Concurrent ingest** test proving idempotency under race.
* [ ] **Cold‑start determinism**: fresh cluster + replay → same hashes.

### Performance & Resilience

* [ ] **Embedding service backpressure** and queue sizing validated.
* [ ] **HNSW index build time** measured; rebuild doesn’t violate SLOs.
* [ ] **AGE checksum** (node/edge counts + hash) per world/branch after replay.
* [ ] **Health restart policy** (container auto‑restart/backoff) configured.
* [ ] **Chaos micro‑drills**: kill projector during load; ensure recovery without gaps.

### Repo & CI Hygiene

* [x] **Make targets**: `up`, `down`, `test`, `baseline`, `health` exist and pass locally/CI.
* [ ] **Branch protection** enabled; required checks enforced.
* [x] **Issue/PR templates** include determinism/idempotency checklist.
* [x] **Badges** (CI, coverage) visible in README; link to `docs/baseline.md`.
* [x] **Docs versioning**: roadmap and baseline carry a date/commit hash.

---

## 🎯 Exit Definition

When all boxes above are checked, the **Alpha Baseline (A6/S0)** is considered reproducible, verifiable, and ready for extension into Stage S0.5 (SAAC Enablement) and Stage S1 (Hybrid Search Planner).

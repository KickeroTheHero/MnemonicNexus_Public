# ALPHA MNX Base Checklist (v1.2, EMO‑ready)

**Scope:** Baseline “Alpha Base” readiness for MNX with **EMO support restored** in an Alpha‑safe way. Keeps the thin **Memory Skeleton** for compatibility and introduces a **dual‑write shim** to `emo.*` so we can validate identity/lineage and determinism now without compaction. Includes rigorous minimum‑ops tests (relational, semantic, graph), hybrid search contracts, and optional MoE controller checks.

---

## Gate 0 — Baseline Freeze & Evidence

* Per `world_id/branch`: snapshot each lens + compute determinism state hashes.
* CI proof of idempotency: duplicate event → single row + `409`.
* Metrics: projector lag watermarks + MV staleness with alert thresholds.

## Gate 1 — Architecture Invariants

* Single write path: **Gateway → Event Log → Outbox → Projectors → Lenses** (no direct lens writes).
* Tenancy + branch isolation end‑to‑end (RLS, per‑tenant watermarks, per‑branch graph namespaces).
* Deterministic replay: same inputs → identical state hashes across all lenses.

---

## Minimum Operations Test Matrix (rigorous)

### A) Gateway & Envelope

* POST `/v1/events` accepts only valid V2 envelopes (tenant/world/branch required).
* Duplicate submit of the same envelope returns `409`; only one row exists.
* Correlation IDs propagate across logs/traces for full E2E observability.

### B) CDC Outbox / Delivery

* Crash/retry safety: outbox replays; projector handlers must be idempotent.
* Health/metrics endpoints report **lag** and **watermarks** for each projector.

### C) Relational Projector

* Base tables + MVs build; MV staleness exported; reads fall back to base when stale.
* Replay from genesis yields identical sorted‑row hash for “current” views.

### D) Semantic Projector (embeddings)

* Embedding generation OK (record `model_id`, `embed_dim`, `model_version`).
* ANN indexing: HNSW (or IVF/HNSW) built; neighbors stable on a fixed corpus.
* Batch search + latency sampling; cache warms without correctness drift.
* Determinism guard: include model/index/template versions in state hash.

### E) Graph Projector (AGE)

* Per `(world_id, branch)` namespace; canonical traversals return expected node/edge counts.
* Replay parity: graph checksum matches after backfill from genesis.

### F) Hybrid Search (contracts‑first smoke)

* `/v1/search/hybrid` supports: `relational_only`, `vector_only`, `hybrid`, `hybrid+graph_expansion`.
* Response carries `rank_version`, fusion method, weights, tie‑break policy.
* Order stable on golden fixtures; p95 ≤ 250ms @ k=50 on the baseline corpus.

### G) EMO Base & Memory Skeleton (Alpha‑safe)

**Goal:** Keep current `memory.*` public contract while enabling EMO identity/lineage now via a translator. **No compaction in Alpha.**

**Public events (unchanged):**

* `memory.item.upserted`  (create/update a memory item)
* `memory.item.deleted`   (tombstone/hide)
* `memory.embed.generated` (optional audit for vectorization jobs)

**Translator (dual‑write shim) responsibilities:**

* On `memory.item.upserted`: emit `emo.created` when new, otherwise `emo.updated` (incrementing version).
* On `memory.item.deleted`: emit `emo.deleted`.
* Optional: infer `parents` from `source.uri` or request context for `emo.linked`.

**EMO event surface (additive):**

* `emo.created`  (first materialization, `emo_version=1`)
* `emo.updated`  (content/metadata change, `emo_version++`)
* `emo.linked`   (optional: lineage/annotation/attachment links)
* `emo.snapshot.compacted` (S2 only)
* `emo.deleted`  (tombstone; MVs exclude)

**EMO base envelope (crew‑neutral):**

```json
{
  "emo_id": "uuid",
  "emo_type": "note|fact|doc|artifact|profile",
  "emo_version": 1,
  "tenant_id": "uuid",
  "world_id": "uuid",
  "branch": "string",
  "source": {"kind":"user|agent|ingest","uri":"optional"},
  "mime_type": "text/markdown",
  "content": "string or null",
  "tags": ["optional", "strings"],
  "parents": [{"emo_id": "uuid", "rel": "derived|supersedes|merges"}],
  "links": [{"kind": "uri|emo", "ref": "..."}],
  "vector_meta": {
    "model_id": "lmstudio:all-MiniLM",
    "embed_dim": 768,
    "model_version": "x.y.z",
    "template_id": "optional"
  },
  "schema_version": 1
}
```

**Relational lens (tables):**

* `emo_current(emo_id, emo_type, emo_version, tenant_id, world_id, branch, mime_type, content, tags[], updated_at, deleted)`
* `emo_history(emo_id, emo_version, diff, content_hash, updated_at)`
* `emo_links(emo_id, rel, target_emo_id, target_uri)`
* `emo_embeddings(emo_id, emo_version, model_id, embed_dim, embedding_vector)`

**Semantic lens:**

* Store 1 vector per **current** version (or per facet if needed later).
* Determinism hash includes `(model_id, model_version, template_id)`.

**Graph lens:**

* Nodes: `(:EMO {emo_id, type})`
* Edges: `(:EMO)-[:DERIVES_FROM]->(:EMO)`, `(:EMO)-[:LINKS_TO]->(:URI)`

**EMO‑focused tests:**

* **Idempotency:** duplicate `emo.updated` does not create a new version.
* **Replay Parity:** from genesis → identical `emo_current` rows and lineage edge counts.
* **Vector Stability:** fixed corpus → stable ANN neighbors across replay.
* **Lineage Integrity:** merges create correct `DERIVES_FROM` fan‑in; no orphans.
* **Delete Semantics:** tombstone excludes EMO from all read modes; history preserved.
* **Shim Equivalence:** `memory.item.upserted` → translator → `emo.created/updated` equals direct EMO events on fixtures.

---

## Optional MoE Controller (if used now)

* Fixed `rng_seed` → identical expert route and tool‑call order.
* Persist decision trace (brief/tool\_intent + weights); pin prompt/weights versions.
* Guardrails: max expert calls per turn; graceful degrade path.
* JSON‑only tool I/O; duplicate effects yield `409` at the effect boundary.

---

## Observability & SLOs

* Expose: projector lag, MV staleness, embed QPS/error, hybrid p95/p99.
* Current SLOs: vector p95 sub‑second; hybrid p95 ≤ 200–250ms @ k=50.

## CI Jobs (copy/paste names)

1. `ci:s0:snapshot-and-hash` — lens snapshots + state hashes per branch/tenant.
2. `ci:s0:dupe-409-golden` — golden envelopes; assert 1 row + `409`.
3. `ci:s0:lag-staleness-probe` — induce lag; verify metrics/alerts.
4. `ci:s1:hybrid-fixtures` — all modes; verify `rank_version`, stable order, p95 SLO.
5. `ci:semantic:embed-and-ann` — embed corpus; build HNSW; neighbor stability.
6. `ci:memory:ingest-upsert-delete` — lifecycle for `memory.*` events end‑to‑end.
7. `ci:emo:translator-parity` — shim emits `emo.*`; direct vs translated EMO fixtures match.
8. `ci:emo:lineage-integrity` — parents/links produce correct graph edges; determinism hash stable.
9. `ci:graph:checksum-replay` — backfill; checksum parity.

## Exit Criteria (“Alpha Base Ready”)

* S0 evidence artifacts are green (snapshots + hashes + 409 proof).
* Minimum‑ops green across relational/semantic/graph; lag/staleness visible.
* `/v1/search/hybrid` contract + fixtures pass with recorded `rank_version`.
* **EMO base active via translator**; identity, versioning, and lineage verified; replay parity holds without compaction.

---

## Schemas & Stubs to add now (repo pointers)

* `schemas/emo.base.v1.json`
* `projectors/translator_memory_to_emo.py` (dual‑write shim)
* SQL migrations: `sql/relational/emo_tables.sql`, `sql/graph/emo_schema.cypher`
* Test fixtures: `tests/fixtures/emo/*.json`, `tests/fixtures/search/*.json`

**Outcome:** EMO‑ready foundation without blocking Alpha; zero‑drama evolution when systems want richer memory objects later.

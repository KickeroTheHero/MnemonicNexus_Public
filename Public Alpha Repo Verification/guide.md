# Public Alpha Repo Verification Guide (A6/S0)

**Purpose**: One-page, practical checklist to confirm the **public repo** matches the planned Alpha (A6/S0) state — lean docs, contracts‑first, deterministic baseline, idempotent ingest, and operational observability. Use this before/after each cleanup or refactor to ensure nothing drifted.

---

## 0) Quick Result

* ✅ If all checks pass below and CI is green, the public repo is **as planned** for A6/S0.
* 🟡 If any check fails, open a `chore: baseline fix` issue and link to the failing section.

---

## 1) Repo Surface (Layout & Files)

**Expect** a single main branch with minimal docs and contracts‑first structure.

```
/ (main)
  README.md                       # ≤ 200 lines
  README_DEPLOYMENT.md            # quick start
  Makefile                        # up/down/test/baseline/health
  .github/workflows/*.yml         # lint, tests, schemas, baseline
  schemas/                        # OpenAPI + JSON Schemas (source of truth)
  services/
    gateway/
    publisher/
  projectors/
    sdk/
    relational/
    semantic/
    graph/
  migrations/
  infra/                          # docker compose, env, images pinned by digest
  tests/
    unit/
    integration/
    golden/
  docs/
    baseline.md
    observability.md
    ROADMAP_S.md
  scripts/
```

**Verify**

* [ ] The above directories exist; no long‑form planning/diary docs remain.
* [ ] `docs/ROADMAP_S.md` is a single page (S0→S7, 3–5 bullets/stage).
* [ ] `docs/baseline.md` explains how baseline evidence is captured and read.

---

## 2) Contracts & CI Gates

**Verify**

* [ ] `schemas/` contains OpenAPI + JSON Schemas; `make schemas-validate` passes.
* [ ] CI workflow enforces: schema validation, unit/integration tests, baseline replay, and idempotency.
* [ ] PRs failing contracts/tests are blocked (branch protection enabled).

**Commands**

```bash
make test            # unit + integration
make baseline        # produces baseline.sha and artifact
```

---

## 3) Services Up & Health

**Verify**

* [ ] `docker compose up -d` succeeds with pinned image digests (no `:latest`).
* [ ] Health endpoints return 200.
* [ ] Prometheus metrics exposed.

**Commands**

```bash
make up
make health          # wraps ./scripts/health_check.sh
curl -fsS localhost:8081/health   # gateway
curl -fsS localhost:8082/health   # publisher
curl -fsS localhost:8083/health   # relational proj
curl -fsS localhost:8084/health   # graph proj
curl -fsS localhost:8085/health   # semantic proj
```

---

## 4) Determinism & Replay Evidence

**Verify**

* [ ] Golden replay from genesis yields same state hashes.
* [ ] `baseline.sha` produced and checked in CI; matches previous run.
* [ ] Replay logs show correlation IDs and “parity OK” message.

**Commands**

```bash
make baseline
# Inspect artifact and compare
cat artifacts/baseline.sha
```

---

## 5) Idempotency & Ingest Fidelity

**Verify** duplicate event → `409 Conflict` and no duplicate rows.

**Commands**

```bash
# Sample envelope
ENV=$(cat tests/golden/envelopes/sample.json)
# First post should 200/202
curl -s -o /dev/null -w "%{http_code}\n" -XPOST localhost:8081/v1/events -H 'Content-Type: application/json' -d "$ENV"
# Second identical post must 409
curl -s -o /dev/null -w "%{http_code}\n" -XPOST localhost:8081/v1/events -H 'Content-Type: application/json' -d "$ENV"
```

---

## 6) Semantic Path (LMStudio + pgvector)

**Verify**

* [ ] Embeddings generated (768‑dim) and inserted.
* [ ] HNSW indexes present; `top‑k=50` returns in < 1s locally.

**Commands**

```bash
psql -U nexus -d nexus_v2 -c "\d+ semantic_embeddings"   # table + index
curl -s localhost:8085/search?query=hello | jq '.results | length'
```

---

## 7) Graph Path (AGE)

**Verify**

* [ ] Separate graphs per `(world_id, branch)`; no cross‑leakage.
* [ ] Basic traversal queries succeed.

**Commands**

```sql
-- in psql
LOAD 'age'; SET search_path = ag_catalog, "$user", public;
SELECT * FROM create_graph('world_main');
-- Sample traversal (adjust to schema):
SELECT * FROM cypher('world_main', $$ MATCH (n)-[r]->(m) RETURN count(r) $$) as (count int);
```

---

## 8) Observability (Metrics, Staleness, Watermarks)

**Verify**

* [ ] Projector lag < 100ms under light load.
* [ ] MV staleness exported; fallback path documented.
* [ ] Correlation IDs visible in logs.

**Commands**

```bash
curl -s localhost:8083/metrics | grep projector_lag_ms | head
curl -s localhost:8083/metrics | grep mv_staleness_seconds | head
```

---

## 9) Security & Policy (Minimum for Public Alpha)

**Verify**

* [ ] Gateway authn token (even simple) enabled for write endpoints.
* [ ] DB roles least‑privilege; RLS rules enforced with a negative test.
* [ ] No PII expected; note redaction path stub for future stage.

---

## 10) Makefile Targets & Scripts

**Verify** these targets exist and pass locally and in CI:

* [ ] `up`, `down`, `test`, `baseline`, `health`.

---

## 11) GitHub Settings

**Verify**

* [ ] Branch protection on `main` requires CI checks.
* [ ] Issue/PR templates include determinism/idempotency reminders.
* [ ] README shows CI/coverage badges and links to `docs/baseline.md`.

---

## 12) SAAC Status (Pre‑S1 Planning)

**Verify**

* [ ] SAAC is **conceptual only** in public repo (no migrations yet).
* [ ] Roadmap includes **S0.5 SAAC Enablement** note for future insertion.

---

## 13) Go / No‑Go Summary

* ✅ **Go** if all sections 1–11 pass and CI is green.
* 🟡 **Conditional Go** if minor docs/badges missing (open chores).
* 🔴 **No‑Go** if determinism, idempotency, or health checks fail.

---

### Notes

* Keep this doc under `docs/` and reference it in the README as “Public Alpha Verification.”
* Re‑run it after significant merges, dependency bumps, or infra changes.

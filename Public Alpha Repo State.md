Got it. If the public repo is meant to be a clean, single‑branch surface with minimal planning noise and just enough direction for your coding assistants, here’s a tight, actionable cutover plan you can run now.

Target state (public)

Branching model: single persistent branch main. Temporary PR branches allowed; no long‑lived “plans” branches.

Docs posture: minimal, operational, stage‑based (S0→S7), not phase‑heavy. Deep plans live elsewhere (private or a migration tag).

Baseline: S0 evidence stays (so we can detect regressions), but explained in one short doc.

Signals for assistants: one concise “Siren Onboard” + “Dev Workflow” doc; everything else comes from code/contracts.


Keep → Remove (public surface)

Keep (short, operational):

README.md (what MNX is; how to run; links to API/specs)

README_DEPLOYMENT.md (quick start; prod notes if needed)

docs/baseline.md (S0 evidence & how CI captures it)

docs/observability.md (health, metrics, correlation IDs)

docs/ROADMAP_S.md (S0–S7 one‑pager, <2 screens)

siren/ONBOARD.md (assistant usage; tasks; Do/Don’t)

schemas/ (OpenAPI + JSON Schemas—source of truth)

Makefile (dev up/down, test, lint, baseline)

tests/ (unit/integration/goldens)

.github/ (workflows + lean issue/PR templates)


Remove (from public main) or relocate to a tag/archived branch:

Detailed planning, diary‑style progress logs, long ADR sets, alternate roadmaps, speculative design notes, multi‑page strategy docs.

Keep a single “Archive tag” that preserves all of it for provenance.


Repo layout (lean)

/ (main)
  README.md
  README_DEPLOYMENT.md
  Makefile
  .github/workflows/*.yml
  schemas/            # OpenAPI + JSON Schemas (contracts-first)
  services/
    gateway/
    publisher/
  projectors/
    sdk/
    relational/
    semantic/
    graph/
  migrations/
  infra/              # docker compose, env, images
  tests/
    unit/
    integration/
    golden/
  docs/
    baseline.md       # S0: snapshot + hash + staleness
    observability.md  # /health, /metrics, corr-ID rules
    ROADMAP_S.md      # S0–S7 one-pager (tight)
  scripts/

Minimal docs content (templates)

README.md (≤ 200 lines)

What MNX is (memory substrate; three lenses; single source of record).

Quick start (docker compose; make up / make baseline / make test).

Endpoints list with links to OpenAPI in schemas/.

Pointers: docs/ROADMAP_S.md, docs/baseline.md, docs/observability.md.


docs/ROADMAP_S.md

One section per stage S0..S7, 3–5 bullets each (objective, key contracts, exit).

No prose histories, no alternatives, no digressions.


siren/ONBOARD.md

Inputs: contracts in schemas/, tasks from issues, acceptance criteria from tests.

Rules: never write lenses directly; emit events; validate against schemas; keep determinism (no time‑dependent randomness in tests).

Common tasks: add an event type → update schema → projector handler → tests → golden replay.


CI gates (keep them, make them visible)

Contracts: OpenAPI + JSON schemas validate; PR fails on drift.

Determinism: Golden replays produce same baseline.sha.

Idempotency: Duplicate envelope → 409; CI asserts.

Health & Metrics: smoke hits /health; scrapes /metrics.

Lint/Type/Tests: fast fail; publish coverage badge.


Cutover steps (one session)

1. Create an archival tag to preserve the full, verbose history:

git checkout main
git pull
git tag -a archive-pre-clean-$(date +%Y%m%d) -m "Pre-clean doc archive"
git push --tags


2. Make a pruning branch:

git checkout -b chore/public-slim


3. Delete/move verbose docs (keep only the minimal set above). If you still want them in‑repo but out of sight, move to docs/archive/ and put a one‑line index; otherwise delete.


4. Add/trim minimal docs using the templates above (especially docs/ROADMAP_S.md + siren/ONBOARD.md).


5. Ensure CI passes (schemas validate, baseline capture runs).


6. Squash‑merge to main with a crisp message:

> feat(repo): public surface slimming — single-branch, contracts-first; S0 baseline retained; moved deep plans to archive tag




7. Lock policy:

Protect main (require status checks).

PR template reminds: “Do not add planning prose—point to private doc or the archive tag.”




Example Makefile targets (short)

up:        docker compose up -d
down:      docker compose down
test:      pytest -q
lint:      ruff check . && mypy .
baseline:  bash scripts/baseline.sh
health:    ./scripts/health_check.sh

Issue/PR templates (lean)

Issue: type (bug/feature/refactor), scope, exit criteria, tests to touch.

PR: what changed, contracts touched (schemas paths), tests added/updated, determinism risk, rollback note.


Risks & mitigations

Scope creep via docs: enforce PR template + codeowners on /docs/*.

Loss of context for new contributors: siren/ONBOARD.md gives the how; ROADMAP_S.md gives the why/when at 1 page.

Accidental deletion of needed specs: preserved by the archive tag; reference it once in README under “Provenance”.



---

If you want, I can draft:

a drop‑in docs/ROADMAP_S.md (S0–S7 one‑pager),

a 100‑line siren/ONBOARD.md,

and a PR description you can paste for the squash merge.


Say the word and I’ll produce those files ready to commit.


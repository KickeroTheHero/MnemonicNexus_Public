# S0 Baseline Evidence

## Overview

The S0 baseline provides a frozen, reproducible snapshot to detect regressions in S1+ phases. It captures materialized lens states, determinism hashes, and materialized view staleness visibility.

## Baseline Components

### 1. Snapshot Scope

The baseline captures CSV dumps for:

- **Relational lens**: `lens_rel/*` materialized tables or views
- **Semantic lens**: `lens_sem/*` tables — **IDs and metadata only** (not HNSW index internals)
- **Graph lens**: `lens_graph/*` tables — vertices + edges with labels/types
- **Gateway**: minimal readonly tables needed to validate end-to-end decisions

### 2. Baseline Script

Run via `make baseline` or directly: `bash scripts/baseline.sh`

The script:
1. Creates CSV dumps of lens materialized views
2. Generates SHA-256 hashes for each CSV
3. Creates a manifest with all hashes
4. Derives an overall baseline hash for quick comparison
5. Captures staleness information for materialized views

### 3. Output Structure

```
artifacts/baseline/<git-sha>/
├── csv/
│   ├── lens_rel.events_mv.csv
│   ├── lens_sem.embeddings.csv
│   ├── lens_graph.vertices.csv
│   └── lens_graph.edges.csv
├── hashes/
│   ├── manifest.json
│   └── baseline.sha
└── staleness.txt
```

### 4. Staleness Visibility

The `staleness.txt` file contains entries showing MV freshness:

```
MV lens_rel.events_mv: fresh (lag 0s)
MV lens_graph.edges : stale (lag 12s)
```

This provides visibility into potential inconsistencies during baseline capture.

## Usage

### Prerequisites

- `psql` configured with database connection
- `jq` for JSON processing
- Write access to `artifacts/` directory

### Running Baseline

```bash
# Via make target (recommended)
make baseline

# Direct execution
bash scripts/baseline.sh
```

### CI Integration

The baseline is automatically captured on every push/PR via `.github/workflows/baseline.yml` and artifacts are uploaded for comparison.

## Baseline Hash Computation

The overall baseline hash is computed from the sorted, canonical JSON representation of all CSV hashes, providing a single fingerprint for the entire baseline state.

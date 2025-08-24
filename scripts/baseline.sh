#!/usr/bin/env bash
set -euo pipefail

# S0 Baseline Evidence Generation Script
# Produces CSV snapshots of lenses + hash manifest and overall baseline hash

OUT="artifacts/baseline/$(git rev-parse --short HEAD)"
mkdir -p "$OUT/csv" "$OUT/hashes"

echo "📊 Creating S0 baseline snapshots in $OUT"

# CSV dumps (requires psql configured via environment)
echo "🔍 Exporting lens data..."

psql -v ON_ERROR_STOP=1 -c "\copy (SELECT * FROM lens_rel.events_mv ORDER BY id) TO '$OUT/csv/lens_rel.events_mv.csv' CSV" || echo "⚠️ Relational lens export failed"
psql -v ON_ERROR_STOP=1 -c "\copy (SELECT id, embedding_dim, created_at FROM lens_sem.embeddings ORDER BY id) TO '$OUT/csv/lens_sem.embeddings.csv' CSV" || echo "⚠️ Semantic lens export failed"
psql -v ON_ERROR_STOP=1 -c "\copy (SELECT * FROM lens_graph.vertices ORDER BY id) TO '$OUT/csv/lens_graph.vertices.csv' CSV" || echo "⚠️ Graph vertices export failed"
psql -v ON_ERROR_STOP=1 -c "\copy (SELECT * FROM lens_graph.edges ORDER BY id) TO '$OUT/csv/lens_graph.edges.csv' CSV" || echo "⚠️ Graph edges export failed"

echo "🔐 Computing hashes..."

# Generate hash manifest
{
  echo '{'
  first=1
  for f in $(ls $OUT/csv/*.csv 2>/dev/null || true); do
    if [ -f "$f" ]; then
      h=$(sha256sum "$f" | awk '{print $1}')
      b=$(basename "$f")
      if [ $first -eq 0 ]; then echo ','; fi
      first=0
      printf '  "%s": {"sha256":"%s"}' "$b" "$h"
    fi
  done
  echo
  echo '}'
} > "$OUT/hashes/manifest.json"

# Overall baseline hash
if [ -f "$OUT/hashes/manifest.json" ]; then
  jq -cS '.' "$OUT/hashes/manifest.json" | sha256sum | awk '{print $1}' > "$OUT/hashes/baseline.sha"
  echo "✅ Baseline hash: $(cat "$OUT/hashes/baseline.sha")"
fi

# Staleness snapshot (placeholder - implement based on MV lag monitoring)
{
  echo "# S0 Baseline Staleness Report - $(date)"
  echo "MV lens_rel.events_mv: check pending (implement MV lag monitoring)"
  echo "MV lens_sem.embeddings: check pending (implement MV lag monitoring)"  
  echo "MV lens_graph.vertices: check pending (implement MV lag monitoring)"
  echo "MV lens_graph.edges: check pending (implement MV lag monitoring)"
} > "$OUT/staleness.txt"

echo "📋 Baseline complete:"
echo "   CSV files: $OUT/csv/"
echo "   Hashes: $OUT/hashes/"
echo "   Staleness: $OUT/staleness.txt"

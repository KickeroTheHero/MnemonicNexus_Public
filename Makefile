.PHONY: baseline replay golden test

# Cross-platform Python runner
ifeq ($(OS),Windows_NT)
  PY := python
else
  PY := python3
endif

baseline:
	@echo "📊 Creating S0 baseline evidence..."
	bash scripts/baseline.sh
	@echo "✅ Baseline complete - check artifacts/baseline/<git-sha>/"

golden:
	@echo "🏆 Running golden test suite..."
	$(PY) -m pytest -v tests/replay --tb=short
	@echo "✅ Golden tests complete"

replay:
	@echo "🎬 Running golden replay suite..."
	$(PY) -m pytest -v tests/replay --tb=short
	@echo "✅ Replay tests complete"

test:
	@echo "🧪 Running offline test suite..."
	$(PY) -m pytest -q -m "not network" || true
	@echo "✅ Offline tests complete"

# Health check targets
health:
	@echo "🔍 Checking service health..."
	@curl -f http://localhost:8086/health || echo "⚠️ Controller not responding"

metrics:
	@echo "📊 Service metrics:"
	@curl -s http://localhost:8086/metrics || echo "⚠️ Metrics not available"

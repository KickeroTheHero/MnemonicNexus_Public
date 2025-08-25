.PHONY: up down baseline replay golden test lint type-check schemas-validate health metrics clean

# Cross-platform Python runner
ifeq ($(OS),Windows_NT)
  PY := python
else
  PY := python3
endif

# Development setup
up:
	@echo "🚀 Starting MNX services..."
	cp env.example .env
	docker compose -f infra/docker-compose.yml up -d
	@echo "✅ Services started - check http://localhost:8081/health"

down:
	@echo "🛑 Stopping MNX services..."
	docker compose -f infra/docker-compose.yml down
	@echo "✅ Services stopped"

# Testing targets
test:
	@echo "🧪 Running test suite..."
	$(PY) -m pytest tests/ -v --tb=short
	@echo "✅ Tests complete"

test-unit:
	@echo "🧪 Running unit tests..."
	$(PY) -m pytest tests/ -v -m "not integration" --tb=short
	@echo "✅ Unit tests complete"

test-integration:
	@echo "🧪 Running integration tests..."
	$(PY) -m pytest tests/ -v -m "integration" --tb=short
	@echo "✅ Integration tests complete"

# Code quality
lint:
	@echo "🔍 Running linting..."
	$(PY) -m ruff check .
	@echo "✅ Linting complete"

format:
	@echo "🎨 Formatting code..."
	$(PY) -m black .
	$(PY) -m ruff format .
	@echo "✅ Formatting complete"

type-check:
	@echo "🔍 Running type checks..."
	$(PY) -m mypy .
	@echo "✅ Type checks complete"

schemas-validate:
	@echo "📋 Validating schemas..."
	$(PY) -m pytest siren/validators/ -v
	@echo "✅ Schema validation complete"

# Baseline and replay
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

# Health check targets
health:
	@echo "🔍 Running health checks..."
	@bash scripts/health_check.sh

metrics:
	@echo "📊 Service metrics:"
	@curl -s http://localhost:8081/metrics || echo "⚠️ Gateway metrics not available"
	@curl -s http://localhost:8082/metrics || echo "⚠️ Publisher metrics not available"

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	rm -rf artifacts/
	@echo "✅ Cleanup complete"

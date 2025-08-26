# MNX Testing Guide

## Overview

The MNX test suite has been reorganized to eliminate redundancy and provide clear separation of concerns. All tests are now organized under the `tests/` directory and can be run via pytest with the unified test runner.

## Test Directory Structure

```
tests/
├── unit/                    # Fast unit tests (no external dependencies)
├── integration/             # Integration tests (require running services)
├── performance/             # Performance tests and benchmarks
├── ci/                      # CI-specific tests for Alpha Base validation
├── validation/              # System and schema validation tests
├── e2e/                     # End-to-end comprehensive test suites
├── golden/                  # Golden test YAML files for determinism validation
├── replay/                  # Golden replay harness for S0 compliance
├── fixtures/                # Test fixtures and sample data
└── pytest.ini             # Pytest configuration
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Purpose**: Fast, isolated tests with no external dependencies
- **Requirements**: None (no services needed)
- **Run time**: < 30 seconds
- **Examples**: Schema validation, utility functions

### Integration Tests (`tests/integration/`)
- **Purpose**: Test service interactions and API endpoints
- **Requirements**: Running services (gateway, database)
- **Run time**: 1-5 minutes
- **Examples**: Gateway API tests, database connectivity

### Performance Tests (`tests/performance/`)
- **Purpose**: Performance benchmarks and load testing
- **Requirements**: Running services
- **Run time**: 2-10 minutes
- **Examples**: Throughput tests, latency measurements

### CI Tests (`tests/ci/`)
- **Purpose**: CI-specific validation for Alpha Base release
- **Requirements**: Full system running
- **Run time**: 5-15 minutes
- **Examples**: S0 snapshot validation, EMO lineage integrity

### Validation Tests (`tests/validation/`)
- **Purpose**: System readiness and schema validation
- **Requirements**: Services for system validation
- **Run time**: 30 seconds - 2 minutes
- **Examples**: EMO system health, schema compliance

### E2E Tests (`tests/e2e/`)
- **Purpose**: Comprehensive end-to-end scenarios
- **Requirements**: Full system running
- **Run time**: 10-30 minutes
- **Examples**: Complete EMO workflows, translator parity

### Golden/Replay Tests (`tests/golden/`, `tests/replay/`)
- **Purpose**: Deterministic replay and baseline validation
- **Requirements**: MoE controller and full system
- **Run time**: 5-20 minutes
- **Examples**: Golden test harness, hash stability

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all core tests (unit, integration, validation)
python scripts/run_tests.py

# Quick smoke test (fastest validation)
python scripts/run_tests.py --quick

# Specific test categories
python scripts/run_tests.py --unit
python scripts/run_tests.py --integration
python scripts/run_tests.py --performance
python scripts/run_tests.py --ci
python scripts/run_tests.py --validation
python scripts/run_tests.py --e2e
python scripts/run_tests.py --golden
```

### Advanced Options

```bash
# Verbose output
python scripts/run_tests.py --verbose

# With coverage reporting
python scripts/run_tests.py --coverage --unit

# Parallel execution (faster)
python scripts/run_tests.py --parallel

# Direct pytest usage
pytest tests/unit/ -v
pytest tests/integration/ -m "not network"
pytest tests/performance/ -m performance
```

### CI/CD Usage

```bash
# CI pipeline validation
python scripts/run_tests.py --ci --verbose

# PR validation (fast feedback)
python scripts/run_tests.py --quick --unit --integration

# Full release validation
python scripts/run_tests.py --ci --performance --e2e
```

## Test Markers

Tests are marked with pytest markers for selective execution:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.ci` - CI-specific tests
- `@pytest.mark.validation` - Validation tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.golden` - Golden replay tests
- `@pytest.mark.network` - Tests requiring network access
- `@pytest.mark.smoke` - Basic smoke tests

## Scripts Directory

The `scripts/` directory now contains only operational utilities:

```
scripts/
├── run_tests.py           # Unified test runner
├── health_check.py        # System health monitoring
├── baseline.sh            # Baseline generation
├── generate_sbom.py       # Security bill of materials
├── pin_image_digests.py   # Security tooling
└── validate_schemas.py    # Schema validation utility
```

## Test Development Guidelines

### Writing New Tests

1. **Choose the right category**: Place tests in the appropriate directory
2. **Use proper markers**: Mark tests with relevant pytest markers
3. **Follow naming**: Test files should start with `test_`
4. **Add documentation**: Include docstrings explaining test purpose

### Test Structure

```python
import pytest

@pytest.mark.unit
def test_something_unit():
    """Unit test example - no external dependencies"""
    pass

@pytest.mark.integration
async def test_something_integration():
    """Integration test example - requires services"""
    pass

@pytest.mark.performance
def test_something_performance():
    """Performance test example"""
    pass
```

### Performance Test Guidelines

- Set reasonable timeouts
- Use consistent test data
- Include performance assertions
- Document expected performance characteristics

## Common Issues

### Service Dependencies

Many tests require services to be running. Start services before running integration/e2e tests:

```bash
# Start required services
docker-compose up -d postgres gateway

# Then run tests
python scripts/run_tests.py --integration
```

### Test Isolation

Tests should be isolated and not depend on each other. Use fixtures for shared setup.

### Debugging Failed Tests

```bash
# Run with verbose output and stop on first failure
python scripts/run_tests.py --verbose -x

# Run specific failing test
pytest tests/integration/test_gateway.py::TestGatewayHealthChecks::test_gateway_health_endpoint -v -s
```

## Migration Notes

The following files were reorganized:

- **Moved to tests/**: All `scripts/ci_*.py`, `scripts/test_*.py`, `scripts/*validation*.py`
- **Consolidated**: Multiple test runners replaced with `scripts/run_tests.py`
- **Removed**: Redundant performance tests and duplicate functionality

This provides cleaner separation between tests (in `tests/`) and operational utilities (in `scripts/`).

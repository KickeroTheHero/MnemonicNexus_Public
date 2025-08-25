# MNX (MneumonicNexus) - Alpha S0

[![CI](https://github.com/your-org/mneumonicnexus/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/mneumonicnexus/actions/workflows/ci.yml)
[![Baseline](https://github.com/your-org/mneumonicnexus/actions/workflows/baseline.yml/badge.svg)](https://github.com/your-org/mneumonicnexus/actions/workflows/baseline.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**MNX (MneumonicNexus)** is an event-sourced system with multi-lens projections for relational, semantic, and graph data. This repository contains the Alpha S0 baseline implementation.

## 🚀 Quickstart

```bash
# Clone and setup
git clone https://github.com/your-org/mneumonicnexus.git
cd mneumonicnexus

# Install dependencies
pip install -r requirements.txt

# Start services
make up

# Run baseline and tests
make baseline
make test
```

## 🏗️ Architecture

MNX provides a deterministic event-sourced architecture with:

- **Event Gateway**: Idempotent event ingestion with correlation ID propagation
- **Multi-Lens Projections**: Relational, semantic (vector), and graph (AGE) projections
- **Deterministic Replay**: Golden test fixtures ensure reproducible state
- **Multi-Tenancy**: World-based isolation with branch support

### Core Components

- **Gateway Service**: Event ingestion and validation
- **Publisher Service**: CDC-based event distribution
- **Relational Projector**: SQL tables and materialized views
- **Semantic Projector**: Vector embeddings with HNSW indexing
- **Graph Projector**: AGE graph database with branch isolation

## 🧪 Testing & Validation

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration

# Run golden replay tests
make golden

# Check service health
make health
```

## 📚 Documentation

- [**EMO Specification**](docs/EMO_SPECIFICATION.md) - Event family and API contracts
- [**Deployment Guide**](README_DEPLOYMENT.md) - Production deployment
- [**Implementation Guide**](README_EMO_IMPLEMENTATION.md) - Technical details
- [**Testing Guide**](docs/EMO_TESTING_GUIDE.md) - Comprehensive testing
- [**Verification Checklist**](mnx-verify-checklist.md) - S0 completion criteria
- [**Public Alpha Verification**](docs/PUBLIC_ALPHA_VERIFICATION_FINAL.md) - ✅ A6/S0 verification complete

## 🔧 Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16+ (with AGE extension)

### Development Workflow

```bash
# Start development environment
make up

# Run code quality checks
make lint
make type-check
make format

# Run tests
make test

# Clean up
make down
make clean
```

### Code Quality

- **Linting**: [Ruff](https://github.com/astral-sh/ruff) for fast Python linting
- **Formatting**: [Black](https://black.readthedocs.io/) for consistent code style
- **Type Checking**: [MyPy](https://mypy.readthedocs.io/) for static type analysis
- **Testing**: [Pytest](https://pytest.org/) with deterministic replay validation

## 📊 Monitoring

- **Health Endpoints**: `/health` on all services
- **Metrics**: Prometheus metrics on `/metrics` endpoints
- **Observability**: Correlation ID tracing across services

## 🚨 Production Readiness

⚠️ **Current Status**: Alpha S0 baseline with identified testing gaps

See [Testing Gaps Analysis](docs/TESTING_GAPS_ANALYSIS.md) for detailed assessment of production readiness blockers.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Determinism Requirements

All contributions must maintain:
- Replay determinism across all projections
- Stable baseline hashes
- Golden test fixture validity
- Multi-tenant isolation
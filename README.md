# MNX (MnemonicNexus) - Alpha S0

[![CI](https://github.com/your-org/mneumonicnexus/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/mneumonicnexus/actions/workflows/ci.yml)
[![Baseline](https://github.com/your-org/mneumonicnexus/actions/workflows/baseline.yml/badge.svg)](https://github.com/your-org/mneumonicnexus/actions/workflows/baseline.yml)
[![Security](https://img.shields.io/badge/security-scanned-green.svg)](docs/SECURITY.md)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](README_DEPLOYMENT.md)

**MNX (MnemonicNexus)** is an event-sourced system with multi-lens projections for relational, semantic, and graph data. This repository contains the Alpha S0 baseline implementation.

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

# Check health
make health
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
- **Search Service**: Hybrid search across multiple modalities
- **MoE Controller**: Decision-making inference engine
- **Projectors**:
  - **Relational**: SQL tables and materialized views
  - **Semantic**: Vector embeddings with HNSW indexing  
  - **Graph**: AGE graph database with branch isolation
  - **Translator**: Memory-to-EMO translation

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

- [**Deployment Guide**](README_DEPLOYMENT.md) - Docker compose quick start + health checks
- [**API Reference**](docs/api.md) - Complete endpoint documentation
- [**Security Guide**](docs/SECURITY.md) - Authentication, RLS policies, security testing
- [**Backup Guide**](docs/BACKUP.md) - Backup procedures and recovery strategies
- [**Baseline Documentation**](docs/baseline.md) - How baseline evidence is produced & compared
- [**Observability Guide**](docs/observability.md) - Health endpoints, key metrics, correlation IDs
- [**Roadmap**](docs/ROADMAP_S.md) - S0→S7 development stages

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
make schemas-validate

# Run tests
make test

# Generate baseline
make baseline

# Clean up
make down
```

### Schemas & Contracts

All API contracts are defined in `schemas/`:
- `schemas/openapi.json` - REST API specification
- `schemas/json/` - JSON Schema definitions for events

Run `make schemas-validate` to verify contract compliance.

## 📊 Monitoring

- **Health Endpoints**: `/health` on all services  
- **Metrics**: Prometheus metrics on `/metrics` endpoints
- **Observability**: Correlation ID tracing across services

See [observability.md](docs/observability.md) for complete monitoring setup.

## 🚨 Current Status

**Alpha S0 Baseline** - Core functionality operational with:
- ✅ Event ingestion with idempotency (409 on duplicates)
- ✅ Multi-lens projections (relational, semantic, graph)
- ✅ Deterministic replay validation
- ✅ Multi-tenant isolation with RLS policies
- ✅ Health checks and basic observability

See [baseline.md](docs/baseline.md) for detailed verification status and known gaps.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

### Determinism Requirements

All contributions must maintain:
- Replay determinism across all projections
- Stable baseline hashes  
- Golden test fixture validity
- Multi-tenant isolation

### Development Guidelines

- Use `make schemas-validate` before committing changes
- Ensure `make baseline` generates stable hashes
- Add tests for new functionality
- Update documentation for user-facing changes

---

For detailed deployment instructions, see [README_DEPLOYMENT.md](README_DEPLOYMENT.md).
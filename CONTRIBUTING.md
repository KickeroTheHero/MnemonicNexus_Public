# Contributing to MNX

Thank you for your interest in contributing to MNX! This document provides guidelines for contributing to the project.

## 🎯 Development Philosophy

MNX prioritizes **determinism** and **reproducibility** above all else. Every contribution must maintain:

- **Replay determinism**: Identical state across all projections after replay
- **Stable baseline hashes**: Consistent checksums across environments
- **Multi-tenant isolation**: No cross-world data leakage
- **Golden test validity**: All replay fixtures must pass

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16+ (with AGE extension)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/mneumonicnexus.git
cd mneumonicnexus

# Install dependencies
pip install -r requirements.txt

# Start services
make up

# Verify setup
make health
make test
```

## 🔧 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Follow these guidelines:

- **Code Style**: Use Black for formatting, Ruff for linting
- **Type Hints**: All functions must have type annotations
- **Documentation**: Update relevant docs for API changes
- **Tests**: Add tests for new functionality

### 3. Run Quality Checks

```bash
# Format code
make format

# Run linting
make lint

# Run type checking
make type-check

# Run tests
make test

# Run golden replay tests
make golden
```

### 4. Verify Determinism

```bash
# Create baseline
make baseline

# Run replay tests
make replay

# Verify baseline hashes are stable
git diff artifacts/baseline/*/hashes/
```

### 5. Submit Pull Request

- Use the provided PR template
- Ensure all CI checks pass
- Include tests for new functionality
- Update documentation as needed

## 🧪 Testing Requirements

### Unit Tests

- Test individual components in isolation
- Use deterministic fixtures
- Mock external dependencies

### Integration Tests

- Test component interactions
- Verify end-to-end workflows
- Test multi-tenant isolation

### Golden Replay Tests

- Ensure deterministic replay
- Validate baseline hashes
- Test branch isolation

### Performance Tests

- Measure projector lag
- Test ingest throughput
- Validate query latency

## 📋 Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Golden replay tests pass
- [ ] Baseline hashes remain stable
- [ ] Documentation is updated
- [ ] Type hints are complete
- [ ] No new warnings are introduced

## 🚨 Critical Requirements

### Determinism

- **No `now()` calls**: Use controlled time sources
- **Fixed RNG seeds**: Ensure reproducible randomness
- **Stable hashing**: Use deterministic hash functions
- **Ordered operations**: Maintain consistent ordering

### Multi-Tenancy

- **World isolation**: All queries scoped by `world_id`
- **Branch isolation**: Events don't leak between branches
- **RLS policies**: Database-level tenant isolation

### Testing

- **Golden fixtures**: Version-controlled test data
- **Replay validation**: Deterministic replay tests
- **Baseline snapshots**: Stable state hashes

## 🐛 Bug Reports

When reporting bugs:

1. Use the bug report template
2. Include reproduction steps
3. Specify environment details
4. Check if issue affects determinism
5. Include relevant logs

## 💡 Feature Requests

When requesting features:

1. Use the feature request template
2. Explain the problem being solved
3. Consider determinism impact
4. Propose test strategy
5. Assess multi-tenant implications

## 📞 Getting Help

- **Issues**: Use GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub discussions for questions
- **Documentation**: Check the docs/ directory

## 📄 Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code.

## 📝 License

By contributing to MNX, you agree that your contributions will be licensed under the MIT License.

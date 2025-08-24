# MNX (Alpha S0)

Primary branch for Alpha S0. Legacy docs/files remain on `alpha/s0-migration`.

## Quickstart

1. `cp .env.example .env`
2. `docker compose up -d` (or your run method)
3. `make baseline`
4. `make replay`

## Architecture

Single-MoE Controller with structured decision making:
- **Tool Bus**: Query lenses (relational/semantic/graph/web)
- **Golden Tests**: Deterministic replay validation
- **S0 Evidence**: Baseline snapshots and hash verification

## Development

- **Offline tests**: `tests/replay` and `tests/unit/*`
- **Archived docs**: Legacy documentation in `docs/archive/` with manifest
- **Migration record**: Complete history on `alpha/s0-migration` branch

## Resources

- Health: `http://localhost:8086/health`
- Metrics: `http://localhost:8086/metrics`
- Documentation: See `docs/` for S0 specifications

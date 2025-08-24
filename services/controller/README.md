# Controller (S0 Skeleton)

## Overview

Single-MoE Controller for structured decision making with S0 compliance.

## Endpoints

- **Health**: `GET /health` → Service status and component health
- **Metrics**: `GET /metrics` → Prometheus exposition format
- **Decisions**: `POST /v1/decisions` → Create decision record

## Observability

### Metrics (Prometheus)
- `mnx_controller_decisions_total{result}` - Decision outcomes
- `mnx_controller_decision_duration_seconds` - End-to-end latency
- `mnx_tool_calls_total{tool, outcome}` - Tool execution results
- `mnx_tool_call_duration_seconds{tool}` - Per-tool latency
- `mnx_validation_failures_total{schema}` - Schema validation failures

### Correlation Tracking
- Generate UUIDv4 `correlation_id` for each decision
- Propagate via `X-Correlation-ID` header to downstream services
- Include in all log entries and decision records

## S0 Requirements

- **Tenancy**: All decisions include `{world_id, branch, correlation_id}`
- **Determinism**: Reproducible hashes with fixed `rng_seed`
- **Validation**: Schema compliance with graceful degradation
- **Timeouts**: Tool calls timeout and retry, then degrade to safe summaries
- **Evidence**: Emit decision records to gateway for baseline verification

## Implementation

Full implementation available on `alpha/s0-migration` branch.
This skeleton serves as the S0 contract definition.

# Controller Observability Contract

## Overview

This document defines the minimal metrics, health endpoints, and trace/correlation propagation expectations for the MNX controller and tool bus.

## Health Endpoints

### `/health`

**Method**: GET
**Response**: JSON
**Status Codes**: 200 (healthy), 503 (degraded/unhealthy)

**Response Format**:
```json
{
  "status": "ok",
  "time": "2024-01-15T10:30:00Z",
  "version": "0.1.0",
  "deps": {
    "gateway": "ok|degraded|down"
  }
}
```

**Status Values**:
- `ok`: All systems operational
- `degraded`: Partial functionality (some dependencies down but core works)
- `down`: Critical failure

## Metrics (Prometheus Exposition)

### `/metrics`

**Method**: GET
**Response**: Prometheus exposition format

### Core Metrics

#### Controller Decision Metrics

- `mnx_controller_decisions_total{result}` (Counter)
  - Labels: `result=ok|validation_failed|timeout|error`
  - Total decisions processed by outcome

- `mnx_controller_decision_duration_seconds` (Histogram)
  - Decision end-to-end latency
  - Buckets: 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0

#### Tool Bus Metrics

- `mnx_tool_calls_total{tool, outcome}` (Counter)
  - Labels: `tool=<tool_name>`, `outcome=ok|timeout|rowcap|error`
  - Total tool calls by tool type and outcome

- `mnx_tool_call_duration_seconds{tool}` (Histogram)
  - Per-tool call latency
  - Labels: `tool=<tool_name>`
  - Buckets: 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0

#### Validation Metrics

- `mnx_validation_failures_total{schema}` (Counter)
  - Labels: `schema=<schema_name>`
  - Schema validation failures by schema type

## Trace and Correlation

### Correlation ID Generation

- Generate UUIDv4 `correlation_id` at decision start
- Propagate through all downstream calls
- Include in logs, decision records, and downstream headers

### Propagation Requirements

1. **Logs**: Include `correlation_id` in structured log entries
2. **Metrics**: Only include in logs, NOT as metric labels (cardinality risk)
3. **Headers**: Pass as `X-Correlation-ID` to downstream services
4. **Decision Records**: Include in `decision_record.v1` schema

### Example Header Propagation

```typescript
const headers = {
  'X-Correlation-ID': correlationId,
  'Content-Type': 'application/json'
};
```

## Implementation Requirements

### Metrics Collection

- Use Prometheus client libraries
- Expose metrics on `/metrics` endpoint
- Follow Prometheus naming conventions
- Avoid high-cardinality labels

### Health Check Implementation

- Check critical dependencies (database, gateway)
- Timeout dependency checks after 3 seconds
- Return appropriate status codes and details

### Error Handling

- Gracefully handle metrics collection failures
- Ensure health checks don't affect core functionality
- Log correlation IDs for troubleshooting

## Monitoring Integration

The observability contract supports:
- Prometheus scraping for metrics collection
- Health check integration with container orchestrators
- Distributed tracing correlation across services
- Performance monitoring and alerting

## Security Considerations

- Health endpoints may expose system information
- Metrics should not contain sensitive data
- Correlation IDs should not be predictable or contain sensitive information

"""
Prometheus metrics and monitoring for MnemonicNexus V2 Gateway

Comprehensive metrics collection for performance monitoring and alerting.
"""

import time

from prometheus_client import Counter, Gauge, Histogram, Info


class GatewayMetrics:
    """Prometheus metrics for Gateway monitoring"""

    def __init__(self):
        # Core event metrics
        self.events_created = Counter(
            "gateway_events_created_total",
            "Total events created successfully",
            ["world_id", "branch", "kind"],
        )

        self.idempotency_conflicts = Counter(
            "gateway_idempotency_conflicts_total",
            "Total idempotency conflicts (409 responses)",
            ["world_id", "branch"],
        )

        self.validation_errors = Counter(
            "gateway_validation_errors_total",
            "Total validation errors (400 responses)",
            ["world_id", "branch"],
        )

        self.internal_errors = Counter(
            "gateway_internal_errors_total",
            "Total internal server errors (500 responses)",
        )

        # Request performance metrics
        self.request_duration = Histogram(
            "gateway_request_duration_seconds",
            "Request processing duration",
            ["endpoint", "status_code"],
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ],
        )

        self.active_requests = Gauge(
            "gateway_active_requests",
            "Number of requests currently being processed",
            ["endpoint"],
        )

        # Database metrics
        self.database_connections = Gauge(
            "gateway_database_connections", "Current database connection pool usage"
        )

        self.database_query_duration = Histogram(
            "gateway_database_query_duration_seconds",
            "Database query execution time",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Event processing metrics
        self.event_size_bytes = Histogram(
            "gateway_event_size_bytes",
            "Size of event envelopes in bytes",
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
        )

        self.projector_lag = Gauge(
            "gateway_projector_lag_events",
            "Number of events behind latest for each projector",
            ["projector_name"],
        )

        # S0 Migration: Controller Decision Metrics
        self.controller_decisions = Counter(
            "mnx_controller_decisions_total",
            "Total controller decisions by outcome",
            ["result"],  # ok|validation_failed|timeout|error
        )

        self.controller_decision_duration = Histogram(
            "mnx_controller_decision_duration_seconds",
            "Controller decision end-to-end latency",
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        )

        # S0 Migration: Tool Bus Metrics
        self.tool_calls = Counter(
            "mnx_tool_calls_total",
            "Total tool calls by outcome",
            ["tool", "outcome"],  # outcome: ok|timeout|rowcap|error
        )

        self.tool_call_duration = Histogram(
            "mnx_tool_call_duration_seconds",
            "Per-tool call latency",
            ["tool"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0],
        )

        # S0 Migration: Validation Metrics
        self.validation_failures = Counter(
            "mnx_validation_failures_total",
            "Schema validation failures by schema type",
            ["schema"],
        )

        # Service info
        self.service_info = Info("gateway_service_info", "Gateway service information")

        # Initialize service info
        self.service_info.info(
            {"version": "2.0.0-s0", "phase": "S0", "service": "gateway-v2"}
        )

    def record_event_created(self, world_id: str, branch: str, kind: str):
        """Record successful event creation"""
        self.events_created.labels(world_id=world_id, branch=branch, kind=kind).inc()

    def record_idempotency_conflict(self, world_id: str, branch: str):
        """Record idempotency conflict"""
        self.idempotency_conflicts.labels(world_id=world_id, branch=branch).inc()

    def record_validation_error(self, world_id: str, branch: str):
        """Record validation error"""
        self.validation_errors.labels(world_id=world_id, branch=branch).inc()

    def record_internal_error(self):
        """Record internal server error"""
        self.internal_errors.inc()

    def record_request_duration(self, endpoint: str, status_code: int, duration: float):
        """Record request processing duration"""
        self.request_duration.labels(
            endpoint=endpoint, status_code=str(status_code)
        ).observe(duration)

    def record_event_size(self, size_bytes: int):
        """Record event envelope size"""
        self.event_size_bytes.observe(size_bytes)

    def update_database_connections(self, count: int):
        """Update database connection count"""
        self.database_connections.set(count)

    def record_database_query(self, operation: str, duration: float):
        """Record database query duration"""
        self.database_query_duration.labels(operation=operation).observe(duration)

    def update_projector_lag(self, projector_name: str, lag: int):
        """Update projector lag metric"""
        self.projector_lag.labels(projector_name=projector_name).set(lag)

    def request_in_progress(self, endpoint: str):
        """Context manager for tracking active requests"""
        return RequestTracker(self, endpoint)

    # S0 Migration: Controller Decision Tracking
    def record_controller_decision(self, result: str, duration: float):
        """Record controller decision outcome and duration"""
        self.controller_decisions.labels(result=result).inc()
        self.controller_decision_duration.observe(duration)

    def record_tool_call(self, tool: str, outcome: str, duration: float):
        """Record tool call outcome and duration"""
        self.tool_calls.labels(tool=tool, outcome=outcome).inc()
        self.tool_call_duration.labels(tool=tool).observe(duration)

    def record_schema_validation_failure(self, schema: str):
        """Record schema validation failure"""
        self.validation_failures.labels(schema=schema).inc()

    def controller_decision_in_progress(self):
        """Context manager for tracking controller decisions"""
        return ControllerDecisionTracker(self)


class RequestTracker:
    """Context manager for tracking request metrics"""

    def __init__(self, metrics: GatewayMetrics, endpoint: str):
        self.metrics = metrics
        self.endpoint = endpoint
        self.start_time = None
        self.status_code = 200

    def __enter__(self):
        self.start_time = time.time()
        self.metrics.active_requests.labels(endpoint=self.endpoint).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics.record_request_duration(
                self.endpoint, self.status_code, duration
            )
        self.metrics.active_requests.labels(endpoint=self.endpoint).dec()

    def set_status_code(self, status_code: int):
        """Set the response status code"""
        self.status_code = status_code


class ControllerDecisionTracker:
    """Context manager for tracking controller decision metrics"""

    def __init__(self, metrics: GatewayMetrics):
        self.metrics = metrics
        self.start_time = None
        self.result = "ok"

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            if exc_type:
                self.result = "error"
            self.metrics.record_controller_decision(self.result, duration)

    def set_result(self, result: str):
        """Set the decision result: ok|validation_failed|timeout|error"""
        self.result = result

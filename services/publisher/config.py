"""Publisher configuration module."""

import os
from typing import List


class PublisherConfig:
    """Publisher service configuration with environment variable support."""

    def __init__(self) -> None:
        # Database
        self.database_url: str = os.getenv(
            "CDC_DATABASE_URL",
            "postgresql://postgres:postgres@postgres-v2:5432/nexus_v2",
        )

        # Polling behavior
        self.poll_interval_ms: int = int(os.getenv("CDC_POLL_INTERVAL_MS", "100"))
        self.batch_size: int = int(os.getenv("CDC_BATCH_SIZE", "50"))

        # Projector communication
        self.projector_timeout_ms: int = int(os.getenv("CDC_PROJECTOR_TIMEOUT_MS", "5000"))
        endpoints_env = os.getenv(
            "CDC_PROJECTOR_ENDPOINTS",
            ",".join(
                [
                    "http://projector-rel-v2:8000/events",
                    # "http://projector-sem-v2:8000/events",  # semantic projector quarantined - vector format issue
                    # "http://projector-graph-v2:8000/events",  # graph projector quarantined - AGE connection issue
                ]
            ),
        )
        self.projector_endpoints: List[str] = [
            e.strip() for e in endpoints_env.split(",") if e.strip()
        ]

        # Reliability
        self.max_processing_attempts: int = int(os.getenv("CDC_MAX_PROCESSING_ATTEMPTS", "10"))
        self.dlq_enabled: bool = os.getenv("CDC_DLQ_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        # Health/metrics
        self.health_port: int = int(os.getenv("CDC_HEALTH_PORT", "8000"))
        self.metrics_port: int = int(os.getenv("CDC_METRICS_PORT", "9100"))

        # Service identity
        self.publisher_id: str = os.getenv("CDC_PUBLISHER_ID", "cdc-publisher-v2")

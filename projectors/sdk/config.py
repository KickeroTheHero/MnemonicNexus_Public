try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class ProjectorConfig(BaseSettings):
    """Base configuration for all projectors"""

    # Database
    database_url: str = "postgresql://postgres:postgres@postgres:5432/nexus"

    # HTTP Server
    port: int = 8000
    host: str = "0.0.0.0"

    # Health monitoring
    health_check_interval_s: int = 30

    # Reliability
    max_retry_attempts: int = 3
    error_backoff_seconds: int = 5

    # State management
    state_hash_interval_s: int = 300  # 5 minutes

    # Metrics
    metrics_update_interval_s: int = 30

    class Config:
        env_prefix = "PROJECTOR_"

#!/usr/bin/env python3
"""
Simple smoke test for Publisher V2 - Tests imports and basic functionality.
Does not require database connection.
"""
import logging
import sys
from pathlib import Path

# Add current directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("publisher_simple_smoke_test")


def test_imports() -> None:
    """Test that all modules can be imported."""
    logger.info("Testing imports...")

    try:
        from config import PublisherConfig

        logger.info("✅ config.PublisherConfig imported successfully")

        from monitoring import PublisherMetrics

        logger.info("✅ monitoring.PublisherMetrics imported successfully")

        from retry import DeadLetterQueue, RetryHandler  # type: ignore[import-untyped]

        logger.info("✅ retry.RetryHandler and DeadLetterQueue imported successfully")

        # Test config instantiation
        config = PublisherConfig()
        logger.info(
            "✅ PublisherConfig instantiated: database_url=%s", config.database_url
        )
        logger.info("   - poll_interval_ms: %d", config.poll_interval_ms)
        logger.info("   - batch_size: %d", config.batch_size)
        logger.info("   - projector_endpoints: %s", config.projector_endpoints)

        # Test metrics instantiation
        _metrics = PublisherMetrics()
        logger.info("✅ PublisherMetrics instantiated with counters and gauges")

        # Test retry logic
        next_retry = RetryHandler.calculate_next_retry(3)
        should_dlq = RetryHandler.should_move_to_dlq(15)
        logger.info(
            "✅ RetryHandler logic: next_retry=%s, should_dlq=%s",
            next_retry,
            should_dlq,
        )

        # Test DLQ
        dlq = DeadLetterQueue("test-publisher")
        logger.info(
            "✅ DeadLetterQueue instantiated with publisher_id=%s", dlq.publisher_id
        )

    except ImportError as e:
        logger.error("❌ Import failed: %s", e)
        raise
    except Exception as e:
        logger.error("❌ Unexpected error: %s", e)
        raise


def test_configuration() -> None:
    """Test configuration with environment variables."""
    import os

    logger.info("Testing configuration...")

    # Set some test environment variables
    os.environ["CDC_POLL_INTERVAL_MS"] = "200"
    os.environ["CDC_BATCH_SIZE"] = "25"
    os.environ["CDC_PUBLISHER_ID"] = "test-publisher-smoke"

    from config import PublisherConfig

    config = PublisherConfig()

    assert (
        config.poll_interval_ms == 200
    ), f"Expected 200, got {config.poll_interval_ms}"
    assert config.batch_size == 25, f"Expected 25, got {config.batch_size}"
    assert (
        config.publisher_id == "test-publisher-smoke"
    ), f"Expected test-publisher-smoke, got {config.publisher_id}"

    logger.info("✅ Configuration test passed")

    # Clean up
    del os.environ["CDC_POLL_INTERVAL_MS"]
    del os.environ["CDC_BATCH_SIZE"]
    del os.environ["CDC_PUBLISHER_ID"]


def main() -> None:
    """Run the simple smoke test."""
    logger.info("Starting Publisher V2 simple smoke test")

    try:
        test_imports()
        test_configuration()
        logger.info("✅ All simple smoke tests passed!")

    except Exception as e:
        logger.error("❌ Simple smoke test failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

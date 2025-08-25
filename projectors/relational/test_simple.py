#!/usr/bin/env python3
"""
Simple Phase A5 Projector test that validates imports and basic functionality
without requiring database connections.
"""
import asyncio
import logging
import os
import sys

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_projector_imports():
    """Test that all projector components can be imported successfully"""
    logger.info("🧪 Testing Phase A5 Projector imports...")

    try:
        # Test SDK imports
        from sdk.config import ProjectorConfig
        from sdk.monitoring import ProjectorMetrics
        from sdk.projector import EventPayload

        logger.info("✅ SDK imports successful")

        # Test relational projector import
        from projector import RelationalProjector

        logger.info("✅ RelationalProjector import successful")

        # Test basic configuration
        config = ProjectorConfig()
        logger.info(f"✅ Configuration loaded: database_url={config.database_url}")

        # Test projector instantiation (without database)
        projector = RelationalProjector(config.model_dump())
        logger.info(
            f"✅ Projector instantiated: name={projector.name}, lens={projector.lens}"
        )

        # Test FastAPI app creation
        assert hasattr(projector, "app"), "FastAPI app not created"
        assert projector.app.title == "Projector projector_rel"
        logger.info("✅ FastAPI app created successfully")

        # Test EventPayload model
        test_payload = EventPayload(
            global_seq=123,
            event_id="test-event-001",
            envelope={
                "world_id": "550e8400-e29b-41d4-a716-446655440000",
                "branch": "main",
                "kind": "note.created",
                "payload": {"id": "note:test", "title": "Test Note"},
                "by": {"agent": "test"},
            },
        )
        assert test_payload.global_seq == 123
        logger.info("✅ EventPayload model validation working")

        # Test metrics instantiation
        metrics = ProjectorMetrics("test_projector")
        assert hasattr(metrics, "events_processed")
        logger.info("✅ Prometheus metrics initialized")

        logger.info("🎉 All Phase A5 Projector component tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Projector test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_event_handlers():
    """Test event handler routing without database"""
    logger.info("🧪 Testing event handler routing...")

    try:
        from projector import RelationalProjector
        from sdk.config import ProjectorConfig

        config = ProjectorConfig()
        projector = RelationalProjector(config.model_dump())

        # Test that handlers exist for expected event types
        expected_handlers = [
            "_handle_note_created",
            "_handle_note_updated",
            "_handle_note_deleted",
            "_handle_tag_added",
            "_handle_tag_removed",
            "_handle_link_added",
            "_handle_link_removed",
        ]

        for handler_name in expected_handlers:
            assert hasattr(projector, handler_name), f"Missing handler: {handler_name}"

        logger.info(f"✅ All {len(expected_handlers)} event handlers found")

        # Test hash computation method exists
        assert hasattr(
            projector, "compute_state_hash"
        ), "Missing state hash computation"
        assert hasattr(
            projector, "_get_state_snapshot"
        ), "Missing state snapshot method"

        logger.info("✅ State management methods present")

        return True

    except Exception as e:
        logger.error(f"❌ Event handler test failed: {e}")
        return False


async def main():
    """Main test runner"""
    logger.info("🚀 Starting Phase A5 Projector Simple Tests")

    tests = [test_projector_imports, test_event_handlers]

    passed = 0
    for test in tests:
        if await test():
            passed += 1

    if passed == len(tests):
        logger.info(
            f"✅ All {len(tests)} tests passed! Phase A5 Projector ready for integration."
        )
        return 0
    else:
        logger.error(f"❌ {len(tests) - passed} out of {len(tests)} tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

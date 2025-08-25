import asyncio
import logging
import os
import sys

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import SemanticProjectorConfig
from projector import SemanticProjector


async def main():
    """Main entry point for semantic projector"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger("SemanticProjectorMain")
    logger.info("Starting Semantic Projector service")

    try:
        config = SemanticProjectorConfig()
        projector = SemanticProjector(config.model_dump())

        # Start projector HTTP server with integrated health/metrics
        await projector.start()

    except Exception as e:
        logger.error(f"Failed to start semantic projector: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import os
import sys

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from projector import GraphProjector

# Add parent directories to path for SDK imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdk.config import ProjectorConfig


async def main():
    """Main entry point for graph projector"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger("GraphProjectorMain")
    logger.info("Starting Graph Projector service")

    try:
        config = ProjectorConfig()
        projector = GraphProjector(config.model_dump())

        # Start projector HTTP server with integrated health/metrics
        await projector.start()

    except Exception as e:
        logger.error(f"Failed to start graph projector: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

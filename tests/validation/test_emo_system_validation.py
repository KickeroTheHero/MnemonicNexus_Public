#!/usr/bin/env python3
"""
Quick EMO System Validation

Fast validation script to check if EMO system is ready for comprehensive testing.
Verifies:
- Database connectivity and EMO schema
- Service endpoints availability
- Basic EMO event processing
- Multi-lens projection status

Usage:
    python scripts/quick_emo_validation.py
    python scripts/quick_emo_validation.py --verbose
"""

import asyncio
import asyncpg
import httpx
import json
import time
import uuid
import argparse
import logging
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QuickEMOValidator:
    """Fast EMO system validation"""

    def __init__(self):
        self.db_url = "postgresql://postgres:postgres@localhost:5432/nexus"
        self.gateway_url = "http://localhost:8086"
        self.search_url = "http://localhost:8090"

    async def run_all_validations(self) -> bool:
        """Run all quick validations"""
        logger.info("🔍 EMO System Quick Validation")
        logger.info("=" * 50)

        validations = [
            ("Database Connectivity", self.validate_database),
            ("EMO Schema Presence", self.validate_emo_schema),
            ("Gateway Service", self.validate_gateway_service),
            ("Search Service", self.validate_search_service),
            ("Basic Event Processing", self.validate_basic_event_processing),
            ("Multi-Lens Status", self.validate_multi_lens_status),
        ]

        results = []
        for name, validation_func in validations:
            try:
                result = await validation_func()
                status = "✅ PASS" if result else "❌ FAIL"
                logger.info(f"{status} {name}")
                results.append(result)
            except Exception as e:
                logger.error(f"❌ FAIL {name}: {e}")
                results.append(False)

        passed = sum(results)
        total = len(results)

        logger.info("=" * 50)
        logger.info(f"📊 Validation Summary: {passed}/{total} passed")

        if passed == total:
            logger.info("🎉 EMO system is ready for comprehensive testing!")
            return True
        else:
            logger.warning(
                f"⚠️ {total - passed} validation(s) failed - system may not be ready"
            )
            return False

    async def validate_database(self) -> bool:
        """Check database connectivity"""
        try:
            async with asyncpg.connect(self.db_url) as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.debug(f"Database error: {e}")
            return False

    async def validate_emo_schema(self) -> bool:
        """Check if EMO schema and tables exist"""
        try:
            async with asyncpg.connect(self.db_url) as conn:
                # Check if lens_emo schema exists
                schema_exists = await conn.fetchval(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'lens_emo'"
                )

                if not schema_exists:
                    return False

                # Check key EMO tables
                required_tables = ["emo_current", "emo_history", "emo_links"]
                for table in required_tables:
                    table_exists = await conn.fetchval(
                        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'lens_emo' AND table_name = $1",
                        table,
                    )
                    if not table_exists:
                        logger.debug(f"Table lens_emo.{table} not found")
                        return False

                return True

        except Exception as e:
            logger.debug(f"Schema validation error: {e}")
            return False

    async def validate_gateway_service(self) -> bool:
        """Check if Gateway service is running"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.gateway_url}/health", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Gateway service error: {e}")
            return False

    async def validate_search_service(self) -> bool:
        """Check if Search service is running (optional)"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.search_url}/health", timeout=5.0)
                return response.status_code == 200
        except Exception:
            # Search service is optional
            logger.debug("Search service not available (optional)")
            return True

    async def validate_basic_event_processing(self) -> bool:
        """Test basic EMO event submission and processing"""
        try:
            # Create simple test event
            test_event = {
                "world_id": str(uuid.uuid4()),
                "branch": "main",
                "kind": "emo.created",
                "event_id": str(uuid.uuid4()),
                "correlation_id": f"validation-{int(time.time())}",
                "occurred_at": "2025-01-21T15:00:00.000Z",
                "by": {"agent": "test:validation", "context": "Quick validation test"},
                "payload": {
                    "emo_id": str(uuid.uuid4()),
                    "emo_type": "note",
                    "emo_version": 1,
                    "tenant_id": "validation-tenant",
                    "world_id": str(uuid.uuid4()),
                    "branch": "main",
                    "content": "Quick validation test content",
                    "mime_type": "text/markdown",
                    "tags": ["validation"],
                    "source": {"kind": "user"},
                    "parents": [],
                    "links": [],
                    "idempotency_key": f"{str(uuid.uuid4())}:1:created",
                    "change_id": str(uuid.uuid4()),
                    "schema_version": 1,
                },
            }

            # Submit event to Gateway
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/events", json=test_event, timeout=10.0
                )

            # Check if event was accepted
            return response.status_code == 201

        except Exception as e:
            logger.debug(f"Event processing error: {e}")
            return False

    async def validate_multi_lens_status(self) -> bool:
        """Check if projectors are healthy"""
        try:
            projector_urls = [
                "http://localhost:8087",  # Relational projector
                "http://localhost:8088",  # Translator projector
                "http://localhost:8089",  # Graph projector
                "http://localhost:8091",  # Semantic projector
            ]

            healthy_count = 0

            for url in projector_urls:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{url}/health", timeout=3.0)
                        if response.status_code == 200:
                            healthy_count += 1
                except Exception:
                    continue

            # At least 2 projectors should be healthy for basic functionality
            return healthy_count >= 2

        except Exception as e:
            logger.debug(f"Multi-lens validation error: {e}")
            return False

    async def validate_with_details(self) -> Dict[str, Any]:
        """Run validations with detailed results"""
        details = {}

        # Database details
        try:
            async with asyncpg.connect(self.db_url) as conn:
                version = await conn.fetchval("SELECT version()")
                details["database"] = {
                    "connected": True,
                    "version": version.split(" ")[1] if version else "unknown",
                }

                # Check EMO table row counts
                if await self.validate_emo_schema():
                    emo_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM lens_emo.emo_current"
                    )
                    history_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM lens_emo.emo_history"
                    )

                    details["emo_data"] = {
                        "current_emos": emo_count,
                        "history_entries": history_count,
                    }

        except Exception as e:
            details["database"] = {"connected": False, "error": str(e)}

        # Service details
        services = {"gateway": self.gateway_url, "search": self.search_url}

        for service, url in services.items():
            try:
                async with httpx.AsyncClient() as client:
                    start_time = time.time()
                    response = await client.get(f"{url}/health", timeout=5.0)
                    duration = time.time() - start_time

                    details[f"{service}_service"] = {
                        "available": response.status_code == 200,
                        "response_time": round(duration * 1000, 2),  # ms
                        "url": url,
                    }
            except Exception as e:
                details[f"{service}_service"] = {
                    "available": False,
                    "error": str(e),
                    "url": url,
                }

        return details


async def main():
    parser = argparse.ArgumentParser(description="Quick EMO System Validation")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--details", action="store_true", help="Show detailed validation results"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    validator = QuickEMOValidator()

    try:
        if args.details:
            details = await validator.validate_with_details()
            logger.info("\n📋 Detailed Validation Results:")
            logger.info(json.dumps(details, indent=2))

        success = await validator.run_all_validations()

        if success:
            logger.info("\n🚀 Ready to run comprehensive tests:")
            logger.info("   python scripts/test_emo_capabilities.py --suite all")
            return 0
        else:
            logger.info("\n🔧 Fix the issues above before running comprehensive tests")
            return 1

    except KeyboardInterrupt:
        logger.info("\n⚠️ Validation interrupted")
        return 130
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))

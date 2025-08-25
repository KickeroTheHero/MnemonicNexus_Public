#!/usr/bin/env python3
"""
EMO System Complete Test Runner

Orchestrates full EMO system testing:
1. Quick validation to ensure system readiness
2. Comprehensive capability tests
3. Performance validation
4. Test report generation

Usage:
    python scripts/run_all_emo_tests.py
    python scripts/run_all_emo_tests.py --skip-validation
    python scripts/run_all_emo_tests.py --performance-only
"""

import asyncio
import argparse
import logging
import json
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EMOTestOrchestrator:
    """Orchestrates complete EMO system testing"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {}
        self.start_time = time.time()

    async def run_complete_test_suite(self) -> bool:
        """Run the complete EMO test suite"""
        logger.info("🧪 EMO SYSTEM COMPLETE TEST SUITE")
        logger.info("=" * 60)
        logger.info(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        success = True

        # Phase 1: Quick Validation (unless skipped)
        if not self.config.get("skip_validation", False):
            logger.info("\n📋 PHASE 1: System Readiness Validation")
            validation_success = await self.run_quick_validation()
            self.results["validation"] = validation_success

            if not validation_success:
                logger.error("❌ System validation failed - aborting test suite")
                return False

            logger.info("✅ System validation passed - proceeding with tests")

        # Phase 2: Core Capability Tests (unless performance-only)
        if not self.config.get("performance_only", False):
            logger.info("\n🧪 PHASE 2: Core Capability Testing")
            capability_success = await self.run_capability_tests()
            self.results["capabilities"] = capability_success
            success = success and capability_success

        # Phase 3: Performance Tests
        logger.info("\n⚡ PHASE 3: Performance Testing")
        performance_success = await self.run_performance_tests()
        self.results["performance"] = performance_success
        success = success and performance_success

        # Phase 4: Generate Final Report
        logger.info("\n📊 PHASE 4: Test Report Generation")
        await self.generate_final_report()

        return success

    async def run_quick_validation(self) -> bool:
        """Run quick system validation"""
        try:
            # Import and run quick validation
            from quick_emo_validation import QuickEMOValidator

            validator = QuickEMOValidator()
            return await validator.run_all_validations()

        except ImportError:
            # Fall back to subprocess
            try:
                result = subprocess.run(
                    [sys.executable, "scripts/quick_emo_validation.py"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                return result.returncode == 0

            except Exception as e:
                logger.error(f"Quick validation failed: {e}")
                return False

    async def run_capability_tests(self) -> bool:
        """Run comprehensive capability tests"""
        try:
            # Import and run capability tests
            from test_emo_capabilities import EMOTestRunner

            test_config = {
                "database_url": self.config.get(
                    "database_url",
                    "postgresql://postgres:postgres@localhost:5432/nexus",
                ),
                "gateway_url": self.config.get("gateway_url", "http://localhost:8086"),
                "search_url": self.config.get("search_url", "http://localhost:8090"),
            }

            runner = EMOTestRunner(test_config)
            results = await runner.run_all_tests()

            # Check if all tests passed
            failed_tests = [r for r in results if not r.success]
            success = len(failed_tests) == 0

            self.results["capability_details"] = {
                "total_tests": len(results),
                "passed_tests": len(results) - len(failed_tests),
                "failed_tests": len(failed_tests),
                "test_results": [
                    {
                        "name": r.test_name,
                        "success": r.success,
                        "duration": r.duration,
                        "error": r.error,
                    }
                    for r in results
                ],
            }

            return success

        except ImportError:
            # Fall back to subprocess
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/test_emo_capabilities.py",
                        "--suite",
                        "all",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                self.results["capability_details"] = {
                    "subprocess_output": result.stdout,
                    "subprocess_errors": result.stderr,
                }

                return result.returncode == 0

            except Exception as e:
                logger.error(f"Capability tests failed: {e}")
                return False

    async def run_performance_tests(self) -> bool:
        """Run performance-specific tests"""
        logger.info("Running basic performance validation...")

        try:
            # Import capability runner for performance tests
            from test_emo_capabilities import EMOTestRunner

            test_config = {
                "database_url": self.config.get(
                    "database_url",
                    "postgresql://postgres:postgres@localhost:5432/nexus",
                ),
                "gateway_url": self.config.get("gateway_url", "http://localhost:8086"),
                "search_url": self.config.get("search_url", "http://localhost:8090"),
            }

            runner = EMOTestRunner(test_config)

            # Run only performance tests
            await runner.run_performance_tests()

            # Check results
            perf_results = [
                r
                for r in runner.results
                if "throughput" in r.test_name or "performance" in r.test_name
            ]
            success = all(r.success for r in perf_results)

            self.results["performance_details"] = {
                "test_count": len(perf_results),
                "results": [
                    {
                        "name": r.test_name,
                        "success": r.success,
                        "duration": r.duration,
                        "details": r.details,
                    }
                    for r in perf_results
                ],
            }

            return success

        except Exception as e:
            logger.error(f"Performance tests failed: {e}")
            return False

    async def generate_final_report(self):
        """Generate comprehensive test report"""
        end_time = time.time()
        total_duration = end_time - self.start_time

        report = {
            "test_execution": {
                "start_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(self.start_time)
                ),
                "end_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(end_time)
                ),
                "total_duration_seconds": round(total_duration, 2),
                "total_duration_formatted": self.format_duration(total_duration),
            },
            "configuration": self.config,
            "results": self.results,
            "summary": self.generate_summary(),
        }

        # Save detailed report
        report_file = (
            Path("test_reports") / f"emo_test_report_{int(self.start_time)}.json"
        )
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        # Display summary
        logger.info("=" * 60)
        logger.info("📊 FINAL TEST SUMMARY")
        logger.info("=" * 60)

        for phase, result in self.results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status} {phase.title()}")

        overall_success = all(self.results.values())
        overall_status = "✅ SUCCESS" if overall_success else "❌ FAILURE"

        logger.info("=" * 60)
        logger.info(f"🎯 OVERALL RESULT: {overall_status}")
        logger.info(f"⏱️ Total Duration: {self.format_duration(total_duration)}")
        logger.info(f"📄 Detailed Report: {report_file}")
        logger.info("=" * 60)

        if overall_success:
            logger.info("🎉 EMO system is fully validated and ready for production!")
        else:
            logger.warning(
                "⚠️ Some tests failed - review results before production deployment"
            )

    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary statistics"""
        summary = {
            "overall_success": all(self.results.values()),
            "phases_completed": len(self.results),
            "phases_passed": sum(1 for r in self.results.values() if r),
            "phases_failed": sum(1 for r in self.results.values() if not r),
        }

        # Add detailed statistics if available
        if "capability_details" in self.results:
            cap_details = self.results["capability_details"]
            summary["capability_tests"] = {
                "total": cap_details.get("total_tests", 0),
                "passed": cap_details.get("passed_tests", 0),
                "failed": cap_details.get("failed_tests", 0),
            }

        if "performance_details" in self.results:
            perf_details = self.results["performance_details"]
            summary["performance_tests"] = {
                "total": perf_details.get("test_count", 0),
                "results": perf_details.get("results", []),
            }

        return summary

    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


async def main():
    parser = argparse.ArgumentParser(description="EMO System Complete Test Runner")
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip quick validation phase"
    )
    parser.add_argument(
        "--performance-only", action="store_true", help="Run only performance tests"
    )
    parser.add_argument(
        "--database-url",
        default="postgresql://postgres:postgres@localhost:5432/nexus",
        help="Database connection URL",
    )
    parser.add_argument(
        "--gateway-url", default="http://localhost:8086", help="Gateway service URL"
    )
    parser.add_argument(
        "--search-url", default="http://localhost:8090", help="Search service URL"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = {
        "skip_validation": args.skip_validation,
        "performance_only": args.performance_only,
        "database_url": args.database_url,
        "gateway_url": args.gateway_url,
        "search_url": args.search_url,
        "verbose": args.verbose,
    }

    orchestrator = EMOTestOrchestrator(config)

    try:
        success = await orchestrator.run_complete_test_suite()
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("\n⚠️ Test suite interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

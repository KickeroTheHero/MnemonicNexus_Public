#!/usr/bin/env python3
"""
MNX Unified Test Runner

Simplified test runner that uses pytest to execute organized test suites.
Replaces multiple redundant test runners with a single, clean interface.

Usage:
    python scripts/run_tests.py                    # Run all tests
    python scripts/run_tests.py --unit             # Unit tests only
    python scripts/run_tests.py --integration      # Integration tests only
    python scripts/run_tests.py --ci               # CI tests only
    python scripts/run_tests.py --performance      # Performance tests only
    python scripts/run_tests.py --e2e              # End-to-end tests only
    python scripts/run_tests.py --validation       # Validation tests only
    python scripts/run_tests.py --golden           # Golden replay tests only
    python scripts/run_tests.py --quick            # Quick smoke tests
    python scripts/run_tests.py --verbose          # Verbose output
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def run_pytest(test_paths: List[str], extra_args: List[str] = None) -> int:
    """Run pytest with given paths and arguments"""
    cmd = ["python", "-m", "pytest"] + test_paths
    
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"🧪 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="MNX Unified Test Runner")
    
    # Test suite selection
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--ci", action="store_true", help="Run CI tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests")
    parser.add_argument("--validation", action="store_true", help="Run validation tests")
    parser.add_argument("--golden", action="store_true", help="Run golden replay tests")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke tests")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    
    args = parser.parse_args()
    
    # Determine test paths based on arguments
    test_paths = []
    
    if args.unit:
        test_paths.append("tests/unit/")
    if args.integration:
        test_paths.append("tests/integration/")
    if args.ci:
        test_paths.append("tests/ci/")
    if args.performance:
        test_paths.append("tests/performance/")
    if args.e2e:
        test_paths.append("tests/e2e/")
    if args.validation:
        test_paths.append("tests/validation/")
    if args.golden:
        test_paths.append("tests/golden/")
        test_paths.append("tests/replay/")
    if args.quick:
        # Quick smoke tests - just basic validation and unit tests
        test_paths.extend(["tests/unit/", "tests/validation/test_emo_system_validation.py"])
    
    # If no specific tests selected, run appropriate defaults
    if not test_paths:
        print("🧪 No specific tests selected - running core test suites")
        test_paths = [
            "tests/unit/",
            "tests/integration/", 
            "tests/validation/",
            "tests/golden/",
            "tests/replay/"
        ]
    
    # Build pytest arguments
    pytest_args = []
    
    if args.verbose:
        pytest_args.extend(["-v", "-s"])
    
    if args.coverage:
        pytest_args.extend(["--cov=mnx", "--cov-report=html", "--cov-report=term"])
    
    if args.parallel:
        pytest_args.extend(["-n", "auto"])
    
    # Add common pytest options
    pytest_args.extend([
        "--tb=short",
        "--strict-markers",
        "-x"  # Stop on first failure for faster feedback
    ])
    
    print("🚀 MNX Unified Test Runner")
    print("=" * 50)
    print(f"Test paths: {', '.join(test_paths)}")
    print(f"Extra args: {' '.join(pytest_args)}")
    print("=" * 50)
    
    # Run the tests
    exit_code = run_pytest(test_paths, pytest_args)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

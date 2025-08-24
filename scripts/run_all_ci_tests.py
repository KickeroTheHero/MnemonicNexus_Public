#!/usr/bin/env python3
"""
MNX Alpha Base CI Test Runner

Runs all CI validation scripts from the checklist:
1. ci:s0:snapshot-and-hash
2. ci:s0:dupe-409-golden  
3. ci:emo:translator-parity
4. ci:emo:lineage-integrity

Provides comprehensive EMO readiness validation.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Tuple


CI_TESTS = [
    {
        "name": "ci:s0:snapshot-and-hash",
        "script": "ci_s0_snapshot_and_hash.py",
        "description": "Lens snapshots + state hashes per branch/tenant",
        "args": ["550e8400-e29b-41d4-a716-446655440001", "main"]
    },
    {
        "name": "ci:s0:dupe-409-golden",
        "script": "ci_s0_dupe_409_golden.py", 
        "description": "Golden envelopes; assert 1 row + 409",
        "args": []
    },
    {
        "name": "ci:emo:translator-parity",
        "script": "ci_emo_translator_parity.py",
        "description": "Shim emits emo.*; direct vs translated EMO fixtures match",
        "args": []
    },
    {
        "name": "ci:emo:lineage-integrity",
        "script": "ci_emo_lineage_integrity.py", 
        "description": "Parents/links produce correct graph edges; determinism hash stable",
        "args": []
    }
]


def run_ci_test(test: dict) -> Tuple[bool, str, float]:
    """Run a single CI test and return (success, output, duration)"""
    
    script_path = os.path.join(os.path.dirname(__file__), test["script"])
    
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}", 0.0
    
    print(f"🧪 Running {test['name']}")
    print(f"   {test['description']}")
    
    start_time = datetime.now()
    
    try:
        # Run the CI script
        cmd = ["python", script_path] + test["args"]
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        if success:
            print(f"   ✅ PASSED ({duration:.1f}s)")
        else:
            print(f"   ❌ FAILED ({duration:.1f}s)")
            print(f"   Return code: {result.returncode}")
        
        return success, output, duration
        
    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start_time).total_seconds()
        print(f"   ⏱️ TIMEOUT ({duration:.1f}s)")
        return False, "Test timed out after 2 minutes", duration
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        print(f"   💥 ERROR ({duration:.1f}s): {e}")
        return False, str(e), duration


def generate_test_report(results: List[dict]) -> str:
    """Generate comprehensive test report"""
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["success"])
    failed_tests = total_tests - passed_tests
    total_duration = sum(r["duration"] for r in results)
    
    report = []
    report.append("=" * 80)
    report.append("MNX ALPHA BASE CI TEST REPORT")
    report.append("=" * 80)
    report.append(f"Timestamp: {datetime.now().isoformat()}")
    report.append(f"Total Tests: {total_tests}")
    report.append(f"Passed: {passed_tests}")
    report.append(f"Failed: {failed_tests}")
    report.append(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    report.append(f"Total Duration: {total_duration:.1f}s")
    report.append("")
    
    # Individual test results
    report.append("INDIVIDUAL TEST RESULTS:")
    report.append("-" * 40)
    
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        report.append(f"{status} {result['name']} ({result['duration']:.1f}s)")
        report.append(f"     {result['description']}")
        
        if not result["success"]:
            # Show first few lines of error output
            lines = result["output"].split('\n')[:5]
            for line in lines:
                if line.strip():
                    report.append(f"     > {line}")
        report.append("")
    
    # Exit criteria check
    report.append("EXIT CRITERIA VALIDATION:")
    report.append("-" * 30)
    
    criteria_checks = [
        ("S0 evidence artifacts are green", "ci:s0:snapshot-and-hash" in [r["name"] for r in results if r["success"]]),
        ("409 idempotency proof verified", "ci:s0:dupe-409-golden" in [r["name"] for r in results if r["success"]]),
        ("EMO base active via translator", "ci:emo:translator-parity" in [r["name"] for r in results if r["success"]]),
        ("Identity, versioning, and lineage verified", "ci:emo:lineage-integrity" in [r["name"] for r in results if r["success"]])
    ]
    
    for criteria, met in criteria_checks:
        status = "✅" if met else "❌"
        report.append(f"{status} {criteria}")
    
    all_criteria_met = all(met for _, met in criteria_checks)
    
    report.append("")
    if all_criteria_met:
        report.append("🎉 ALPHA BASE READY - All exit criteria met!")
    else:
        report.append("❌ ALPHA BASE NOT READY - Some exit criteria not met")
    
    return "\n".join(report)


def main():
    """Main test runner function"""
    
    print("🚀 Starting MNX Alpha Base CI Test Suite")
    print(f"   Tests to run: {len(CI_TESTS)}")
    print(f"   Test directory: {os.path.dirname(__file__)}")
    print("")
    
    # Check environment
    required_env_vars = ["DATABASE_URL", "GATEWAY_URL"]
    missing_env = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_env.append(var)
    
    if missing_env:
        print(f"⚠️  Missing environment variables: {', '.join(missing_env)}")
        print("   Using default values (localhost services)")
        print("")
    
    # Run all tests
    results = []
    
    for test in CI_TESTS:
        success, output, duration = run_ci_test(test)
        
        results.append({
            "name": test["name"],
            "description": test["description"],
            "success": success,
            "output": output,
            "duration": duration
        })
        
        print("")  # Spacing between tests
    
    # Generate and display report
    report = generate_test_report(results)
    print(report)
    
    # Save report to file
    report_filename = f"ci_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Full report saved to: {report_filename}")
    
    # Exit with appropriate code
    all_passed = all(r["success"] for r in results)
    
    if all_passed:
        print("\n✅ All CI tests PASSED - MNX Alpha Base ready!")
        return 0
    else:
        print("\n❌ Some CI tests FAILED - MNX Alpha Base not ready")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

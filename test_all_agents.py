"""
Master test script that runs all agent tests in sequence.
Run this to test the complete system from start to finish.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def run_test(agent_name: str, test_script: Path) -> bool:
    """Run a test script and return True if successful."""
    print_header(f"Testing {agent_name}")
    
    if not test_script.exists():
        print(f"❌ Test script not found: {test_script}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=test_script.parent,
            capture_output=False,
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False


def main():
    """Run all agent tests in sequence."""
    print_header("Complete System Test Suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    root = Path(__file__).resolve().parent
    results = {}
    
    # Test each agent in order
    agents = [
        ("News Agent", root / "news-agent" / "test_agent.py"),
        ("Trend Agent", root / "trend-agent" / "test_agent.py"),
        ("Rules Agent", root / "rules-agent" / "test_agent.py"),
        ("Trade Agent", root / "trade-agent" / "test_agent.py"),
    ]
    
    for agent_name, test_script in agents:
        success = run_test(agent_name, test_script)
        results[agent_name] = success
        
        if not success:
            print(f"\n⚠️  {agent_name} test failed, but continuing...")
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for agent_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {agent_name}: {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "=" * 70)
        print("  🎉 ALL TESTS PASSED - System is ready for production!")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("  ⚠️  Some tests failed - Review output above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())


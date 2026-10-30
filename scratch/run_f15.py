import sys
import pytest

args = [
    "backend/tests/test_f15_natural_language_planning.py",
    "-v",
    "-s",
    "--tb=short",
]
print(f"Running pytest with args: {args}")
exit_code = pytest.main(args)
print(f"Pytest exited with code: {exit_code}")
sys.exit(exit_code)

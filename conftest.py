"""
Pytest configuration for backtest-runner tests.

This conftest.py is in the project root directory to ensure
the src module is importable from all test files.
"""
import sys
from pathlib import Path

# Add project root to Python path for src module imports
# This must be done at conftest load time, before test collection
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

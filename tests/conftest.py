"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest and makes fixtures
available to all test modules.
"""

import sys
from pathlib import Path

# Add project root to Python path so we can import src modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

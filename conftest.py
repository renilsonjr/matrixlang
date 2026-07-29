"""Pytest configuration to add src to the Python path."""

import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

"""Make `import bloxen` work when running pytest from the repo root.

The package lives in `server/` (see docs/ARCHITECTURE.md); several test modules add that
path themselves, but the end-to-end tests import `bloxen` directly. Doing it once here
keeps `.venv/bin/python -m pytest tests/ -q` working in a clean checkout without needing
`PYTHONPATH=server` or an editable install.
"""
from __future__ import annotations

import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

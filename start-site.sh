#!/bin/bash
# Bring the BLOXEN 2015 website up in one command.
#
#   ./start-site.sh          # web (8080) + compat (8081) + assets (8082) + game UDP (53640)
#
# Why this exists: this environment is re-created between sessions and the virtualenv
# (git-ignored, as virtualenvs should be) does not survive. Rather than rediscovering that
# every time, this script rebuilds it if needed and then starts the stack.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "[start-site] creating virtualenv…"
  python3 -m venv .venv
  .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
fi

# useful extras for the tooling (browser validation, client-asset conversion); optional
.venv/bin/python - <<'PY' 2>/dev/null || .venv/bin/pip install -q --disable-pip-version-check brotli websockets pillow numpy
import brotli, websockets, PIL, numpy  # noqa: F401
PY

if [ ! -d data ]; then
  echo "[start-site] no data/ directory — run the seed/import tools first"
  exit 1
fi

echo "[start-site] starting: web http://0.0.0.0:8080, compat :8081, assets :8082, UDP :53640"
exec env PYTHONPATH=server .venv/bin/python server/run_all.py

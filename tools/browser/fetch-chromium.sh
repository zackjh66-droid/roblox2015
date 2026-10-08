#!/bin/bash
# Fetch a headless Chromium for browser validation of the BLOXEN runtime.
#
# Why this script exists: the usual sources (playwright CDN, cdn.jsdelivr.net, unpkg,
# storage.googleapis.com) are unreachable from this environment, but the npm registry is
# not. @sparticuz/chromium ships a full headless Chromium *inside its own tarball*, so it
# can be fetched from registry.npmjs.org with nothing else available.
#
# Usage:  tools/browser/fetch-chromium.sh
# Then:   tools/browser/run-chromium.sh &
#         .venv/bin/python tools/browser/probe_client.py 1
#
# Everything lands in tools/browser/ (git-ignored: it is ~280 MB of downloaded binaries).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PKG_VERSION="${CHROMIUM_PKG_VERSION:-153.0.0}"
WORK="${CHROMIUM_WORK:-$HERE}"

mkdir -p "$WORK"
cd "$WORK"

if [ -x "$WORK/chromium" ]; then
  echo "chromium already present at $WORK/chromium ($(du -h "$WORK/chromium" | cut -f1))"
else
  echo "fetching @sparticuz/chromium@$PKG_VERSION from the npm registry…"
  curl -sL --retry 3 -o chromium.tgz \
    "https://registry.npmjs.org/@sparticuz/chromium/-/chromium-$PKG_VERSION.tgz"
  tar xzf chromium.tgz
  "$ROOT/.venv/bin/python" - <<'PY'
import brotli, pathlib
for name in ("chromium.br", "swiftshader.tar.br", "fonts.tar.br", "al2023.tar.br"):
    src = pathlib.Path("package/bin") / name
    out = pathlib.Path(name.replace(".br", ""))
    out.write_bytes(brotli.decompress(src.read_bytes()))
    print(f"  {name:20} -> {out.name:22} {out.stat().st_size / 1e6:8.1f} MB")
PY
  chmod +x chromium
fi

# The package also ships the AL2023 shared libraries headless Chromium links against
# (libnspr4, libnss3, …) and the SwiftShader software renderer for WebGL
[ -d "$WORK/libs" ] || { mkdir -p "$WORK/libs"; tar xf al2023.tar -C "$WORK/libs"; }

# SwiftShader (software WebGL) and the font set
[ -d "$WORK/swiftshader" ] || { mkdir -p "$WORK/swiftshader"; tar xf swiftshader.tar -C "$WORK/swiftshader"; }
[ -d "$WORK/fonts" ] || { mkdir -p "$WORK/fonts"; tar xf fonts.tar -C "$WORK/fonts"; }
[ -f "$WORK/vk_swiftshader_icd.json" ] || cat > "$WORK/vk_swiftshader_icd.json" <<JSON
{
  "file_format_version": "1.0.0",
  "ICD": {"library_path": "$WORK/swiftshader/libvk_swiftshader.so", "api_version": "1.0.0"}
}
JSON

echo "chromium ready: $WORK/chromium"
"$WORK/chromium" --version 2>/dev/null || echo "(version string needs the loader env from run-chromium.sh)"

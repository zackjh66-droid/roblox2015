#!/bin/bash
# Launch the headless Chromium used for browser validation of the BLOXEN runtime.
#
#   tools/browser/fetch-chromium.sh          # once: downloads the binary (git-ignored)
#   tools/browser/run-chromium.sh &          # CDP on 127.0.0.1:9222
#   .venv/bin/python tools/browser/probe_client.py 1        # one game
#   .venv/bin/python tools/browser/validate_all_games.py    # every game with a place
#
# Everything is resolved relative to this script: nothing depends on /tmp surviving, and
# the browser is configured with the package's own SwiftShader (software WebGL) and its
# own font set, because neither a GPU nor system fonts exist in this environment.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# the package ships its AL2023 libs (libnspr4, libnss3, …) that chromium links against
export LD_LIBRARY_PATH="$HERE/libs/lib:$HERE/swiftshader:${LD_LIBRARY_PATH:-}"
# SwiftShader's ICD file uses a path relative to itself, so it must be used as shipped
export VK_ICD_FILENAMES="$HERE/swiftshader/vk_swiftshader_icd.json"

# fontconfig: write a config that points at the fonts actually present here. Without this
# chromium aborts in SkFontMgr_FontConfigInterface ("Not implemented").
if [ ! -f "$HERE/fonts/fonts.conf.bloxen" ]; then
  mkdir -p "$HERE/fonts"
  cat > "$HERE/fonts/fonts.conf.bloxen" <<CONF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>$HERE/fonts/fonts</dir>
  <cachedir>/tmp/fonts-cache</cachedir>
  <config></config>
</fontconfig>
CONF
fi
export FONTCONFIG_PATH="$HERE/fonts"
export FONTCONFIG_FILE="$HERE/fonts/fonts.conf.bloxen"

export HOME="${HOME:-/tmp}"
mkdir -p /tmp/fonts-cache "$HOME"

exec "$HERE/chromium" \
  --headless \
  --no-sandbox --no-zygote --disable-crashpad --disable-dev-shm-usage \
  --use-angle=swiftshader --enable-unsafe-swiftshader \
  --disable-gpu-sandbox \
  --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
  "$@"

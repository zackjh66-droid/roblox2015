#!/bin/bash
export LD_LIBRARY_PATH=/home/user/roblox2015/tools/browser/libs/lib:/tmp
export VK_ICD_FILENAMES=/tmp/vk_swiftshader_icd.json
export FONTCONFIG_PATH=/tmp/fonts
export HOME=/tmp
exec /tmp/chromium --headless --no-sandbox --no-zygote --disable-crashpad --disable-dev-shm-usage --use-angle=swiftshader --enable-unsafe-swiftshader --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 about:blank "$@"

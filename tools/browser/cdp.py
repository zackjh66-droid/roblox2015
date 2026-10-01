#!/usr/bin/env python3
"""Minimal CDP driver for headless Chromium: screenshot + DOM + console capture.

Usage:
  python3 tools/browser/cdp.py screenshot <url> <out.png> [width] [height] [wait_ms]
  python3 tools/browser/cdp.py dom <url>
"""
import asyncio
import base64
import json
import sys
import urllib.request

import websockets

CDP_HTTP = "http://127.0.0.1:9222"


async def _new_target():
    req = urllib.request.Request(CDP_HTTP + "/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


async def run(url, action, out=None, width=1280, height=900, wait_ms=1500):
    t = await _new_target()
    ws_url = t["webSocketDebuggerUrl"]
    msg_id = 0

    async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            m = {"id": msg_id, "method": method}
            if params:
                m["params"] = params
            await ws.send(json.dumps(m))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == msg_id:
                    return resp.get("result", {})

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Network.enable")
        await send("Network.setCacheDisabled", {"cacheDisabled": True})
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        await send("Page.navigate", {"url": url})
        await asyncio.sleep(wait_ms / 1000.0)
        if action == "screenshot":
            res = await send("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(res["data"])
            with open(out, "wb") as f:
                f.write(data)
            print(f"saved {out} ({len(data)} bytes)")
        elif action == "dom":
            res = await send("Runtime.evaluate",
                             {"expression": "document.documentElement.outerHTML", "returnByValue": True})
            print(res.get("result", {}).get("value", ""))
        elif action == "pdf":
            res = await send("Page.printToPDF")
            data = base64.b64decode(res["data"])
            with open(out, "wb") as f:
                f.write(data)
            print(f"saved {out} ({len(data)} bytes)")


def main():
    action = sys.argv[1]
    url = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 1280
    height = int(sys.argv[5]) if len(sys.argv) > 5 else 900
    wait_ms = int(sys.argv[6]) if len(sys.argv) > 6 else 1500
    asyncio.run(run(url, action, out, width, height, wait_ms))


if __name__ == "__main__":
    main()

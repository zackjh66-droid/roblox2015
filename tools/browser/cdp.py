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
    # Reuse a single page target: captureScreenshot captures the visible browser
    # surface, so background targets would screenshot the wrong page. Close extras.
    with urllib.request.urlopen(CDP_HTTP + "/json/list", timeout=10) as r:
        pages = [p for p in json.load(r) if p.get("type") == "page"]
    for p in pages[1:]:
        try:
            urllib.request.urlopen(CDP_HTTP + "/json/close/" + p["id"], timeout=5)
        except Exception:
            pass
    if pages:
        return pages[0]
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

        async def pump(until, timeout=15.0):
            """Drain ws messages until `until(resp)` or timeout; return matching msg results."""
            end = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < end:
                try:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                except asyncio.TimeoutError:
                    continue
                if resp.get("id") == msg_id:
                    return resp.get("result", {})
                if until and until(resp):
                    return None
            return None

        # navigate and wait for the load event (fixes stale-content screenshots)
        await send("Page.bringToFront")          # make this target the visible surface
        msg_id += 1
        await ws.send(json.dumps({"id": msg_id, "method": "Page.navigate",
                                  "params": {"url": url}}))
        await pump(lambda r: r.get("method") == "Page.loadEventFired")
        await asyncio.sleep(wait_ms / 1000.0)
        res = await send("Runtime.evaluate",
                         {"expression": "location.href", "returnByValue": True})
        actual = res.get("result", {}).get("value", "")
        if actual and actual.rstrip("/") != url.rstrip("/"):
            print(f"note: landed on {actual} (requested {url})")
        if action == "screenshot":
            # captureScreenshot can capture the wrong surface when multiple pages
            # exist in the browser; screencast frames are strictly per-target.
            frame_future: asyncio.Future = asyncio.get_event_loop().create_future()
            await send("Page.startScreencast",
                       {"format": "png", "everyNthFrame": 1, "maxWidth": width,
                        "maxHeight": height})

            async def drain_frames(timeout=10.0):
                end = asyncio.get_event_loop().time() + timeout
                best = None
                while asyncio.get_event_loop().time() < end:
                    try:
                        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                    except asyncio.TimeoutError:
                        continue
                    if resp.get("id") == msg_id:
                        continue
                    if resp.get("method") == "Page.screencastFrame":
                        params = resp.get("params", {})
                        best = params.get("data")
                        await send("Page.screencastFrameAck",
                                   {"sessionId": params.get("sessionId", 0)})
                        if best:
                            return best
                return best

            data_b64 = await drain_frames()
            await send("Page.stopScreencast")
            data = base64.b64decode(data_b64 or "")
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

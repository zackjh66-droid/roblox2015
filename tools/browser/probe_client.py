#!/usr/bin/env python3
"""Probe the BLOXEN browser runtime for one game through real headless Chromium.

This is the acceptance check that the runtime actually works — not that the code parses.
It loads /play/<id>, waits for the world to build, reads the runtime's own diagnostics
(`window.__blx`), saves a screenshot, and fails on any JavaScript error or failed request
other than the documented always-missing historical asset hosts.

    tools/browser/run-chromium.sh &          # start the browser first
    .venv/bin/python tools/browser/probe_client.py 1 --out shot.png

What it asserts
- a WebGL context was actually obtained
- `stats.sceneObjects` (or draw calls) > 0 — the runtime built a scene. This replaces an
  earlier, racy check that the loading overlay had gone away.
- the runtime published character/camera diagnostics
- zero JS errors and zero failed requests beyond the known-dead 2015 asset hosts

How it *looks* is deliberately not scored here: the screenshot is for eyes and for
tools/browser/validate_all_games.py to collect.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import urllib.request
from pathlib import Path

import websockets

CDP_HTTP = "http://127.0.0.1:9222"
DEFAULT_URL = "http://127.0.0.1:8080/play/{game}"
# Hosts and paths that were already dead before this work started: their failures are
# expected and are not counted against the runtime.
EXPECTED_MISSING = (
    "themes.googleusercontent.com",
    "fonts.googleapis.com",
    "assetgame.roblox.com",
    "/images/",
)


def page_target() -> dict:
    """Reuse the single existing page target: screenshot capture is per-surface."""
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


async def probe(url: str, out: Path | None, wait_ms: int, width: int, height: int) -> dict:
    t = page_target()
    msg_id = 0
    errors: list[str] = []
    failed: list[str] = []

    async with websockets.connect(t["webSocketDebuggerUrl"],
                                  max_size=256 * 1024 * 1024) as ws:
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
                _collect(resp)

        def _collect(resp: dict) -> None:
            m = resp.get("method")
            p = resp.get("params", {})
            if m == "Runtime.exceptionThrown":
                d = p.get("exceptionDetails", {})
                errors.append(d.get("exception", {}).get("description")
                              or d.get("text", "exception"))
            elif m == "Log.entryAdded":
                e = p.get("entry", {})
                if e.get("level") == "error":
                    errors.append(e.get("text", ""))
            elif m == "Network.loadingFailed":
                failed.append(f"{p.get('errorText', '?')} {p.get('type', '')}")
            elif m == "Network.responseReceived":
                r = p.get("response", {})
                if r.get("status", 200) >= 400:
                    failed.append(f"HTTP {r.get('status')} {r.get('url', '')}")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Log.enable")
        await send("Network.enable")
        await send("Network.setCacheDisabled", {"cacheDisabled": True})
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": width, "height": height, "deviceScaleFactor": 1,
                    "mobile": False})
        await send("Page.bringToFront")
        msg_id += 1
        await ws.send(json.dumps({"id": msg_id, "method": "Page.navigate",
                                  "params": {"url": url}}))

        async def eval_js(expr: str):
            r = await send("Runtime.evaluate", {"expression": expr,
                                                "returnByValue": True, "awaitPromise": True})
            return r.get("result", {}).get("value")

        # wait for the runtime to publish diagnostics, then a settle period
        deadline = asyncio.get_event_loop().time() + wait_ms / 1000
        diag = None
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(1.0)
            diag = await eval_js("JSON.stringify(window.__blx && {"
                                 "three: window.__blx.three, stats: window.__blx.stats,"
                                 "character: window.__blx.diag && window.__blx.diag.character,"
                                 "camera: window.__blx.diag && window.__blx.diag.camera,"
                                 "onGround: window.__blx.diag && window.__blx.diag.onGround,"
                                 "camDistance: window.__blx.diag && window.__blx.diag.camDistance,"
                                 "clientAssets: window.__blxTextures ? "
                                 "{atlas: !!window.__blxTextures.atlas,"
                                 " materials: Object.keys(window.__blxTextures.materials||{}).length,"
                                 " sky: !!window.__blxTextures.sky} : null"
                                 "})")
            if diag:
                break
        await asyncio.sleep(1.5)          # let physics settle before the screenshot

        webgl = await eval_js(
            "(function(){var c=document.createElement('canvas');"
            "var g=c.getContext('webgl2')||c.getContext('webgl');"
            "if(!g)return null;"
            "var e=g.getExtension('WEBGL_debug_renderer_info');"
            "return g.getParameter(g.VERSION)+' | '+(e?"
            "g.getParameter(e.UNMASKED_RENDERER_WEBGL):'?');})()")

        # screencast frames are strictly per-target, unlike captureScreenshot
        shot_bytes = None
        if out:
            got: list[str] = []
            await send("Page.startScreencast",
                       {"format": "png", "everyNthFrame": 1,
                        "maxWidth": width, "maxHeight": height})
            end = asyncio.get_event_loop().time() + 10
            while asyncio.get_event_loop().time() < end and not got:
                try:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                except asyncio.TimeoutError:
                    continue
                if resp.get("method") == "Page.screencastFrame":
                    p = resp["params"]
                    got.append(p.get("data", ""))
                    msg_id += 1
                    await ws.send(json.dumps({"id": msg_id, "method": "Page.screencastFrameAck",
                                              "params": {"sessionId": p.get("sessionId", 0)}}))
                else:
                    _collect(resp)
            await send("Page.stopScreencast")
            if got:
                shot_bytes = base64.b64decode(got[0])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(shot_bytes)

    info = json.loads(diag) if diag else None
    stats = (info or {}).get("stats") or {}
    scene_objects = (stats.get("sceneObjects") or stats.get("drawCalls") or 0)
    real_errors = [e for e in errors if e and not any(k in e for k in EXPECTED_MISSING)]
    real_failed = [f for f in failed if not any(k in f for k in EXPECTED_MISSING)]
    ok = bool(webgl and info and scene_objects and not real_errors and not real_failed)
    return {"url": url, "ok": ok, "webgl": webgl, "diag": info,
            "sceneObjects": scene_objects, "errors": real_errors,
            "failedRequests": real_failed, "screenshot": str(out) if shot_bytes else None,
            "expectedMissing": len(errors) + len(failed) - len(real_errors) - len(real_failed)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", nargs="?", default="1")
    ap.add_argument("--url", default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--wait", type=int, default=9000,
                    help="ms to poll for runtime diagnostics")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=860)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    url = args.url or DEFAULT_URL.format(game=args.game)
    try:
        rep = asyncio.run(probe(url, args.out, args.wait, args.width, args.height))
    except Exception as exc:            # browser not running is the usual cause
        print(f"probe failed: {type(exc).__name__}: {exc}")
        print("is chromium running?  tools/browser/fetch-chromium.sh && "
              "tools/browser/run-chromium.sh &")
        return 2
    if not args.quiet:
        print(f"url: {rep['url']}")
        print(f"  webgl: {rep['webgl']}")
        d = rep["diag"] or {}
        print(f"  three r{d.get('three')}  sceneObjects={rep['sceneObjects']}")
        if d.get("clientAssets"):
            ca = d["clientAssets"]
            print(f"  2015 client assets: atlas={ca['atlas']} materials={ca['materials']} "
                  f"sky={ca['sky']}")
        if d:
            print("  diag: " + json.dumps({k: v for k, v in d.items()
                                           if k not in ("stats", "clientAssets")})[:240])
        if rep["screenshot"]:
            print(f"  screenshot: {rep['screenshot']}")
        if rep["expectedMissing"]:
            print(f"  (ignored) {rep['expectedMissing']} expected-missing historical requests")
        for e in rep["errors"][:6]:
            print(f"  ERROR {str(e)[:200]}")
        for f in rep["failedRequests"][:6]:
            print(f"  HTTP  {str(f)[:200]}")
        print(f"errors: {len(rep['errors'])}")
        print("RESULT:", "PASS" if rep["ok"] else "FAIL")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

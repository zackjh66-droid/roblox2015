#!/usr/bin/env python3
"""Validate every game with a place file in real headless Chromium, and collect shots.

    tools/browser/run-chromium.sh &
    .venv/bin/python tools/browser/validate_all_games.py \
        --out-dir checkpoints/screenshots --wait 9000

Prints PASS/FAIL per game and a summary line. Exit code is non-zero if any game fails, so
it works as a gate. Each game's screenshot is written to
<out-dir>/runtime-play-<id>.png and a JSON report next to it as
<out-dir>/runtime-validation.json.

This is the tool that produced the honesty-ladder rung BROWSER-TESTED: every game in the
library has been loaded by a real browser, its scene built from the real place file, and
its JavaScript run without errors.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from bloxen import config                                   # noqa: E402
from probe_client import probe                              # noqa: E402


def games_with_places() -> list[dict]:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, name, place_path, provenance_grade, compatibility_status "
        "FROM games WHERE place_path IS NOT NULL ORDER BY id").fetchall()
    con.close()
    out = []
    for r in rows:
        p = Path(r["place_path"])
        if not p.is_absolute():
            p = config.ROOT / p
        if p.exists():
            out.append({"id": r["id"], "name": r["name"],
                        "place": str(p), "size": p.stat().st_size})
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=9000)
    ap.add_argument("--out-dir", type=Path, default=Path("checkpoints/screenshots"))
    ap.add_argument("--only", type=int, action="append", default=[],
                    help="validate only these game ids (repeatable)")
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    args = ap.parse_args()

    games = games_with_places()
    if args.only:
        games = [g for g in games if g["id"] in args.only]
    if not games:
        print("no games with place files found")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    failed = 0
    started = time.time()
    for g in games:
        url = f"{args.base}/play/{g['id']}"
        shot = args.out_dir / f"runtime-play-{g['id']:02d}.png"
        print(f"=== [{g['id']}] {g['name']}")
        try:
            rep = await probe(url, shot, args.wait, 1280, 860)
        except Exception as exc:
            print(f"  probe error: {type(exc).__name__}: {exc}")
            rep = {"ok": False, "errors": [str(exc)], "diag": None, "sceneObjects": 0,
                   "failedRequests": [], "expectedMissing": 0, "webgl": None}
        d = rep.get("diag") or {}
        if d:
            print("  diag: " + json.dumps({k: v for k, v in d.items()
                                           if k not in ("stats", "clientAssets")})[:250])
            if d.get("clientAssets"):
                print(f"  2015 client assets: {json.dumps(d['clientAssets'])}")
            if d.get("stats"):
                s = d["stats"]
                print(f"  stats: {json.dumps({k: s[k] for k in list(s)[:8]})[:250]}")
        print(f"  sceneObjects: {rep.get('sceneObjects')}  "
              f"expected-missing requests ignored: {rep.get('expectedMissing', 0)}")
        for e in (rep.get("errors") or [])[:5]:
            print(f"  ERROR {str(e)[:200]}")
        for f in (rep.get("failedRequests") or [])[:5]:
            print(f"  HTTP  {str(f)[:200]}")
        print(f"errors: {len(rep.get('errors') or [])}")
        print("RESULT:", "PASS" if rep["ok"] else "FAIL")
        if not rep["ok"]:
            failed += 1
        report.append({"id": g["id"], "name": g["name"], "place": g["place"],
                       "place_bytes": g["size"], "url": url,
                       "ok": bool(rep["ok"]), "sceneObjects": rep.get("sceneObjects"),
                       "webgl": rep.get("webgl"), "diag": d,
                       "errors": rep.get("errors") or [],
                       "failedRequests": rep.get("failedRequests") or [],
                       "screenshot": str(shot) if shot.exists() else None})

    summary = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "browser": "chromium (headless, SwiftShader WebGL)",
               "games": len(games), "passed": len(games) - failed, "failed": failed,
               "seconds": round(time.time() - started, 1), "results": report}
    (args.out_dir / "runtime-validation.json").write_text(json.dumps(summary, indent=1))
    print(f"\nvalidated {len(games)} games, {failed} failed "
          f"({summary['seconds']}s) — report: {args.out_dir / 'runtime-validation.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

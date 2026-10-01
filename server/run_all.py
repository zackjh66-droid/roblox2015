"""Run the full BLOXEN stack: web, compat, assets, game server."""
from __future__ import annotations

import asyncio
import multiprocessing
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn                                       # noqa: E402
from bloxen import config                            # noqa: E402


def run_web():
    uvicorn.run("bloxen.app:app", host=config.WEB_HOST, port=config.WEB_PORT,
                log_level="warning")


def run_compat():
    uvicorn.run("bloxen.compat.app:app", host=config.COMPAT_HOST,
                port=config.COMPAT_PORT, log_level="warning")


def run_assets():
    uvicorn.run("bloxen.assetsvc.app:app", host=config.ASSET_HOST,
                port=config.ASSET_PORT, log_level="warning")


def run_gameserver():
    import bloxen.gameserver.server as gs
    asyncio.run(gs.main())


def main():
    procs = [
        multiprocessing.Process(target=run_web, name="web"),
        multiprocessing.Process(target=run_compat, name="compat"),
        multiprocessing.Process(target=run_assets, name="assets"),
        multiprocessing.Process(target=run_gameserver, name="gameserver"),
    ]
    for p in procs:
        p.start()
        print(f"[run_all] started {p.name} pid={p.pid}")
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()

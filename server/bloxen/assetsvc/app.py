"""BLOXEN asset service: local delivery of recovered historical assets.

Recovery state lives in the `assets` table. MISSING means MISSING — we never
fabricate replacements and call them preserved (docs/ASSETS.md).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .. import config


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


ASSET_ROOT = config.DATA / "assets"


def build_app() -> FastAPI:
    app = FastAPI(title="BLOXEN assets", docs_url=None, redoc_url=None, openapi_url=None)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)

    @app.get("/health")
    def health():
        return {"service": "bloxen-assets", "ok": True}

    @app.get("/v1/asset/{asset_id}")
    def get_asset(asset_id: int):
        con = get_db()
        row = con.execute("SELECT * FROM assets WHERE historical_asset_id = ?", (asset_id,)).fetchone()
        con.close()
        if not row or row["status"] != "RECOVERED" or not row["local_path"]:
            return JSONResponse({"id": asset_id, "status": "MISSING"}, status_code=404)
        p = Path(row["local_path"])
        if not p.exists():
            return JSONResponse({"id": asset_id, "status": "MISSING"}, status_code=404)
        return FileResponse(p)

    @app.get("/v1/asset/{asset_id}/meta")
    def asset_meta(asset_id: int):
        con = get_db()
        row = con.execute("SELECT * FROM assets WHERE historical_asset_id = ?", (asset_id,)).fetchone()
        con.close()
        return dict(row) if row else {"id": asset_id, "status": "MISSING"}

    @app.get("/v1/status")
    def status():
        con = get_db()
        rows = con.execute("SELECT status, COUNT(*) AS c FROM assets GROUP BY status").fetchall()
        con.close()
        return {"counts": {r["status"]: r["c"] for r in rows}}

    return app


app = build_app()

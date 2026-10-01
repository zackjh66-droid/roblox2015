"""BLOXEN compatibility HTTP service for the July-2015 Windows client.

Reconstructs the client's local HTTP bootstrap surface:
  Login/Negotiate, Login/RequestAuth, Game/Join, Game/PlaceLauncher, Game/Visit,
  Asset/CharacterFetch, Avatar/BodyColors, asset delivery, settings/presence.

Design rules:
- local/private by default (bind 127.0.0.1)
- every request is logged to the compat_requests table for later comparison
  against genuine-client captures
- unknown paths are logged and answered 404 — NEVER forwarded to live Roblox
  services (docs/PROTOCOL.md)
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .. import config, db as dbmod


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def log_request(con, method, path, query, body_preview, status, tag=None):
    con.execute(
        "INSERT INTO compat_requests (method, path, query, body_preview, response_status, client_tag)"
        " VALUES (?,?,?,?,?,?)",
        (method, path, query, (body_preview or "")[:500], status, tag))
    con.commit()


def build_app() -> FastAPI:
    app = FastAPI(title="BLOXEN compat", docs_url=None, redoc_url=None, openapi_url=None)

    def ok_response(request: Request, payload, status=200, tag=""):
        con = get_db()
        log_request(con, request.method, request.url.path, str(request.url.query),
                    json.dumps(payload)[:500] if not isinstance(payload, str) else payload,
                    status, tag)
        con.close()
        return payload

    @app.get("/health")
    def health():
        return {"service": "bloxen-compat", "ok": True,
                "target_build": config.TARGET_WINDOWS_PLAYER_GUID}

    # ------------------------------------------------------ login surface
    @app.get("/Login/Negotiate.ashx")
    @app.get("/Login/Negotiate.ashx/")
    def login_negotiate(request: Request):
        # 2015-era negotiate returned an auth ticket handshake blob.
        return ok_response(request, "BLOXEN-AUTH-TICKET", 200, "negotiate")

    @app.get("/Login/RequestAuth.ashx")
    def login_request_auth(request: Request):
        ticket = request.query_params.get("auth", "")
        return ok_response(request, f"OK {ticket[:24]}", 200, "request-auth")

    # --------------------------------------------------- visit / join flow
    def _game_ctx(request: Request):
        gid = int(request.query_params.get("gameId") or request.query_params.get("placeId") or 0)
        con = get_db()
        g = con.execute("SELECT * FROM games WHERE id = ? OR historical_place_id = ?", (gid, gid)).fetchone()
        con.close()
        return dict(g) if g else None

    @app.get("/Game/Visit.ashx")
    def visit(request: Request):
        """Start a visit: returns the historical join-script style payload."""
        game = _game_ctx(request)
        join_ip = config.GAMESERVER_HOST
        join_port = config.GAMESERVER_PORT
        join_script = (
            f"roblox-player:1"
            f"+launchmode:play"
            f"+gameinfo:{request.query_params.get('gameId', '')}"
            f"+placelauncherurl:http://127.0.0.1:{config.COMPAT_PORT}/Game/PlaceLauncher.ashx"
            f"+gamejoinurl:http://127.0.0.1:{config.COMPAT_PORT}/Game/Join.ashx"
        )
        payload = {
            "status": "Waiting",
            "joinScript": join_script,
            "authenticationUrl": f"http://127.0.0.1:{config.COMPAT_PORT}/Login/Negotiate.ashx",
            "authenticationTicket": "BLOXEN-AUTH-TICKET",
            "joinServerUrl": f"udp://{join_ip}:{join_port}",
        }
        return ok_response(request, JSONResponse(payload).body.decode(), 200, "visit")

    @app.get("/Game/PlaceLauncher.ashx")
    def place_launcher(request: Request):
        """PlaceLauncher status/join bridge. Job id state is kept in-process."""
        game = _game_ctx(request)
        if not game:
            return ok_response(request, JSONResponse(
                {"status": "Error", "message": "unknown place"}).body.decode(), 404, "pl-launcher")
        payload = {
            "status": "Joining",
            "joinScript": (
                f"roblox-player:1+launchmode:play"
                f"+gameinfo:{game.get('historical_place_id') or game['id']}"
            ),
            "jobId": f"BLOXEN-JOB-{game['id']}",
            "serverId": 0,
            "status": "Joining",
            "authenticationTicket": "BLOXEN-AUTH-TICKET",
        }
        return ok_response(request, JSONResponse(payload).body.decode(), 200, "pl-launcher")

    @app.get("/Game/Join.ashx")
    def game_join(request: Request):
        game = _game_ctx(request)
        payload = {
            "status": "Waiting",
            "joinScript": f"roblox-player:1+launchmode:play+gameinfo:{request.query_params.get('gameId','')}",
        }
        return ok_response(request, JSONResponse(payload).body.decode(), 200, "join")

    # ------------------------------------------------- avatar / character
    @app.get("/Asset/CharacterFetch.ashx")
    def character_fetch(request: Request):
        """Character appearance for the requested user id (BLOXEN account mapping)."""
        user_id = int(request.query_params.get("userId") or request.query_params.get("userid") or 0)
        con = get_db()
        prof = con.execute(
            """SELECT u.id, u.username, p.avatar_json FROM users u
               LEFT JOIN profiles p ON p.user_id = u.id WHERE u.id = ?""", (user_id,)).fetchone()
        avatar = json.loads(prof["avatar_json"]) if prof and prof["avatar_json"] else {}
        equipped = avatar.get("equipped", {})
        items = []
        for slot, item_id in equipped.items():
            it = con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if it:
                items.append({"slot": slot, "assetId": it["historical_asset_id"],
                              "name": it["name"], "type": it["item_type"]})
        con.close()
        payload = {
            "userId": user_id,
            "username": prof["username"] if prof else "Guest",
            "bodyColors": avatar.get("body_colors", {}),
            "equipped": items,
            "provenance": "avatar state served from BLOXEN DB; format is a compatibility reconstruction",
        }
        return ok_response(request, JSONResponse(payload).body.decode(), 200, "characterfetch")

    @app.get("/Avatar/BodyColors.ashx")
    def body_colors(request: Request):
        user_id = int(request.query_params.get("userId") or request.query_params.get("userid") or 0)
        con = get_db()
        prof = con.execute("SELECT avatar_json FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        con.close()
        avatar = json.loads(prof["avatar_json"]) if prof and prof["avatar_json"] else {}
        colors = avatar.get("body_colors", {})
        # Historically this endpoint answered with plain XML body-color fields.
        xml = "<roblox" + "".join(
            f'<{k.lower().replace(" ", "")}color>{v}</{k.lower().replace(" ", "")}color>'
            for k, v in colors.items()) + "</roblox>"
        return ok_response(request, xml, 200, "bodycolors")

    # ----------------------------------------------------- asset delivery
    @app.get("/asset/")
    @app.get("/asset")
    def asset(request: Request):
        asset_id = request.query_params.get("id", "")
        # hand off to the local asset service; MISSING stays MISSING
        return ok_response(request, JSONResponse(
            {"id": asset_id, "status": "MISSING",
             "note": "asset service owns recovery state; see docs/ASSETS.md"}).body.decode(),
            404, "asset")

    # ------------------------------------------------- settings / presence
    @app.get("/Setting/Values")
    @app.get("/Setting/Values/")
    def setting_values(request: Request):
        settings = {
            "ClientVersion": config.TARGET_WINDOWS_PLAYER_VERSION,
            "VersionGuid": config.TARGET_WINDOWS_PLAYER_GUID,
            "BaseUrl": f"http://127.0.0.1:{config.COMPAT_PORT}/",
            "GameJoin": f"http://127.0.0.1:{config.COMPAT_PORT}/Game/Join.ashx",
            "PlaceLauncher": f"http://127.0.0.1:{config.COMPAT_PORT}/Game/PlaceLauncher.ashx",
            "ProtocolVersion": config.PROTOCOL_VERSION,
        }
        return ok_response(request, JSONResponse(settings).body.decode(), 200, "settings")

    @app.get("/presence/ping")
    def presence_ping(request: Request):
        return ok_response(request, JSONResponse(
            {"status": "Online", "userId": request.query_params.get("userId")}).body.decode(),
            200, "presence")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT"])
    def fallback(request: Request, full_path: str):
        # Never proxy unknown paths to live Roblox services.
        con = get_db()
        log_request(con, request.method, "/" + full_path, str(request.url.query),
                    "UNKNOWN-ENDPOINT", 404, "fallback")
        con.close()
        return JSONResponse({"error": "unknown endpoint (logged, not forwarded)",
                             "path": "/" + full_path}, status_code=404)

    return app


app = build_app()

"""BLOXEN launcher — `bloxen-player:` URI handling and launch orchestration.

Flow (docs/PROTOCOL.md):
  website Play -> single-use scoped ticket -> `bloxen-player:` URI ->
  launcher validates request -> validates client package (SHA-256 allowlist) ->
  launches the reviewed client against BLOXEN services.

Windows-specific bits (protocol registration, process launch of
RobloxPlayerBeta.exe) are marked AWAITING WINDOWS VALIDATION. All non-Windows
logic is implemented and tested here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config

URI_SCHEME = config.PLAYER_URI_SCHEME

# Reviewed client allowlist (hash-verified packages only).
# The genuine 0.205.0.61876 package is registered with its claimed SHA-256;
# verification is enforced when the package is present (quarantine/).
CLIENT_ALLOWLIST = {
    config.TARGET_WINDOWS_PLAYER_VERSION: {
        "guid": config.TARGET_WINDOWS_PLAYER_GUID,
        "sha256": config.TARGET_WINDOWS_PLAYER_SHA256_CLAIMED,
        "file": "RobloxPlayerBeta.exe",
        "status": "AWAITING-PACKAGE",
    }
}


class LaunchError(Exception):
    pass


@dataclass
class LaunchRequest:
    action: str
    ticket: str = ""
    game_id: int = 0
    server_id: str = ""
    extra: dict = field(default_factory=dict)


def parse_launch_uri(uri: str) -> LaunchRequest:
    """Strict parser for bloxen-player: URIs.

    Accepted forms:
      bloxen-player:play?ticket=...&game=123[&server=...]
      bloxen-player:launch?ticket=...&game=123
    Everything else is rejected.
    """
    if not isinstance(uri, str) or len(uri) > 2048:
        raise LaunchError("uri too long or not a string")
    if not uri.startswith(URI_SCHEME + ":"):
        raise LaunchError(f"wrong scheme (expected {URI_SCHEME}:)")
    rest = uri[len(URI_SCHEME) + 1:]
    if "?" in rest:
        action, qs = rest.split("?", 1)
    else:
        action, qs = rest, ""
    action = action.strip().lower()
    if action not in ("play", "launch"):
        raise LaunchError(f"unknown action {action!r}")
    params = parse_qs(qs, keep_blank_values=True)
    flat = {k: v[0] for k, v in params.items()}
    ticket = flat.get("ticket", "")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,64}", ticket or ""):
        raise LaunchError("malformed ticket")
    game_raw = flat.get("game", "")
    if not re.fullmatch(r"\d{1,12}", game_raw or ""):
        raise LaunchError("malformed game id")
    server_id = flat.get("server", "")
    if server_id and not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", server_id):
        raise LaunchError("malformed server id")
    extra = {k: v for k, v in flat.items() if k not in ("ticket", "game", "server")}
    for k in extra:
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,48}", k):
            raise LaunchError("malformed parameter name")
    return LaunchRequest(action=action, ticket=ticket, game_id=int(game_raw),
                         server_id=server_id, extra=extra)


def validate_ticket(web_base: str, req: LaunchRequest, user_id: int = 0) -> dict:
    """Server-side ticket validation (single-use, TTL, user+game scoped)."""
    payload = {"ticket": req.ticket, "game_id": req.game_id}
    if user_id:
        payload["user_id"] = user_id
    r = urllib.request.Request(f"{web_base}/api/play/validate",
                               data=json.dumps(payload).encode(),
                               headers={"content-type": "application/json"},
                               method="POST")
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read())


def validate_client_package(version: str = config.TARGET_WINDOWS_PLAYER_VERSION) -> dict:
    """Hash-check the reviewed client package. Never executes anything here."""
    entry = CLIENT_ALLOWLIST.get(version)
    if not entry:
        raise LaunchError(f"client version {version} not in allowlist")
    pkg_dir = config.QUARANTINE / "client" / version
    exe = pkg_dir / entry["file"]
    if not exe.exists():
        return {"status": "AWAITING-PACKAGE", "expected_sha256": entry["sha256"],
                "guid": entry["guid"],
                "note": "genuine package not present in this environment"}
    h = hashlib.sha256()
    with open(exe, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != entry["sha256"]:
        return {"status": "HASH-MISMATCH", "actual_sha256": digest,
                "expected_sha256": entry["sha256"]}
    return {"status": "VERIFIED", "sha256": digest, "guid": entry["guid"]}


def build_launch_contract(ticket: str, game_id: int, server_id: str = "") -> dict:
    """The website hands this to the OS/browser for the bloxen-player: handler."""
    uri = f"{URI_SCHEME}:play?ticket={ticket}&game={game_id}"
    if server_id:
        uri += f"&server={server_id}"
    return {"uri": uri, "ticket_ttl_seconds": config.TICKET_TTL_SECONDS,
            "single_use": True}


def launch_plan(req: LaunchRequest, validated_ticket: dict, client_state: dict) -> dict:
    """Compose the launch plan (command argv) — process launch itself is
    AWAITING WINDOWS VALIDATION on non-Windows environments."""
    if client_state.get("status") != "VERIFIED":
        exec_status = "AWAITING WINDOWS VALIDATION"
    else:
        exec_status = "AWAITING WINDOWS VALIDATION"
    game = validated_ticket.get("game") or {}
    argv = [
        str(config.QUARANTINE / "client" / config.TARGET_WINDOWS_PLAYER_VERSION
            / CLIENT_ALLOWLIST[config.TARGET_WINDOWS_PLAYER_VERSION]["file"]),
        "--play",
        f"--gameId={game.get('historical_place_id') or req.game_id}",
        f"--ticket={req.ticket}",
        f"--base-url=http://127.0.0.1:{config.COMPAT_PORT}/",
        f"--server={config.GAMESERVER_HOST}:{config.GAMESERVER_PORT}",
    ]
    return {
        "argv": argv,
        "user": validated_ticket.get("user"),
        "game": game,
        "client": client_state,
        "execution_status": exec_status,
        "windows_protocol_registration": {
            "scheme": URI_SCHEME,
            "status": "AWAITING WINDOWS VALIDATION",
            "design": f"HKCU\\Software\\Classes\\{URI_SCHEME} -> launcher.exe \"%1\"",
        },
    }

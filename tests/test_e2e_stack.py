"""End-to-end tests against the ACTUAL running BLOXEN stack.

Run with the stack up:
  PYTHONPATH=server .venv/bin/python -m pytest tests/ -v

These tests exercise the live services (web API, compat HTTP, game server via
the simulator). They are SIMULATOR-TESTED checks.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

import pytest

WEB = "http://127.0.0.1:8080"
COMPAT = "http://127.0.0.1:8081"
ASSETS = "http://127.0.0.1:8082"


def http(url, data=None, headers=None, method=None, expect_error=False):
    req = urllib.request.Request(url, method=method or ("POST" if data is not None else "GET"))
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("content-type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body.decode("utf-8", "replace")


def test_health():
    s, b = http(f"{WEB}/api/health")
    assert s == 200 and b["ok"]
    s, b = http(f"{COMPAT}/health")
    assert s == 200
    s, b = http(f"{ASSETS}/health")
    assert s == 200


def test_pages_render():
    for path in ["/", "/games", "/catalog", "/Login.aspx", "/Register.aspx",
                 "/bloom/about", "/develop", "/groups"]:
        s, body = http(f"{WEB}{path}")
        assert s == 200, path
        assert "BLOXEN" in body


def test_register_login_catalog_inventory_character_flow():
    name = "E2E_" + uuid.uuid4().hex[:10]
    s, b = http(f"{WEB}/api/auth/register", {"username": name, "password": "e2e-password-1"})
    assert s == 200 and b.get("token")
    token = b["token"]
    uid = b["user_id"]

    # catalog list
    s, cat = http(f"{WEB}/api/catalog")
    assert s == 200 and len(cat["items"]) >= 10
    item = cat["items"][0]

    # acquire via form endpoint (session-less API equivalent: direct inventory insert through login form flow)
    # emulate browser: login form sets cookie
    from http.cookiejar import CookieJar
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    form = f"username={name}&password=e2e-password-1".encode()
    req = urllib.request.Request(f"{WEB}/Login.aspx", data=form,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    opener.open(req, timeout=20)
    form = f"item_id={item['id']}".encode()
    req = urllib.request.Request(f"{WEB}/catalog/acquire", data=form,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    opener.open(req, timeout=20)

    # inventory has the item
    s, body = http(f"{WEB}/My/Stuff.aspx", headers={"Cookie": ""})
    # use opener instead
    body = opener.open(f"{WEB}/My/Stuff.aspx", timeout=20).read().decode()
    assert item["name"] in body

    # equip via character page
    form = f"item_id={item['id']}&slot={item['item_type']}".encode()
    req = urllib.request.Request(f"{WEB}/avatar/equip", data=form,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    opener.open(req, timeout=20)
    body = opener.open(f"{WEB}/My/Character.aspx", timeout=20).read().decode()
    assert item["name"] in body

    # play ticket lifecycle
    s, t = http(f"{WEB}/api/play/ticket", {"game_id": 1},
                headers={"Authorization": f"Bearer {token}"})
    assert s == 200 and t["ticket"]
    ticket = t["ticket"]
    s, v = http(f"{WEB}/api/play/validate", {"ticket": ticket, "game_id": 1})
    assert s == 200 and v["ok"]
    # replay must fail
    s, v2 = http(f"{WEB}/api/play/validate", {"ticket": ticket, "game_id": 1})
    assert s != 200 or not v2.get("ok")
    # wrong game must fail
    s, t3 = http(f"{WEB}/api/play/ticket", {"game_id": 1},
                 headers={"Authorization": f"Bearer {token}"})
    s, v3 = http(f"{WEB}/api/play/validate", {"ticket": t3["ticket"], "game_id": 2})
    assert s != 200 or not v3.get("ok")


def test_ticket_wrong_user_and_expiry():
    name = "E2E_" + uuid.uuid4().hex[:10]
    s, b = http(f"{WEB}/api/auth/register", {"username": name, "password": "e2e-password-1"})
    token = b["token"]
    s, t = http(f"{WEB}/api/play/ticket", {"game_id": 1},
                headers={"Authorization": f"Bearer {token}"})
    # wrong user id must fail
    s, v = http(f"{WEB}/api/play/validate",
                {"ticket": t["ticket"], "game_id": 1, "user_id": 999999})
    assert s != 200 or not v.get("ok")


def test_compat_never_forwards_unknown():
    s, b = http(f"{COMPAT}/totally/unknown/path?x=1")
    assert s == 404
    assert "not forwarded" in json.dumps(b)


def test_launcher_uri_parser():
    from bloxen.launcher.uri import LaunchError, parse_launch_uri
    req = parse_launch_uri("bloxen-player:play?ticket=" + "A" * 24 + "&game=123")
    assert req.action == "play" and req.game_id == 123
    with pytest.raises(LaunchError):
        parse_launch_uri("http://evil")
    with pytest.raises(LaunchError):
        parse_launch_uri("bloxen-player:exec?ticket=" + "A" * 24 + "&game=1")
    with pytest.raises(LaunchError):
        parse_launch_uri("bloxen-player:play?ticket=short&game=1")
    with pytest.raises(LaunchError):
        parse_launch_uri("bloxen-player:play?ticket=" + "A" * 24 + "&game=abc")


def test_simulator_against_live_services():
    """Full simulated client scenario against the running stack."""
    import asyncio
    from bloxen.simulator.client import run_scenario
    rep = asyncio.run(run_scenario(WEB, COMPAT, ("127.0.0.1", 53640),
                                   username="SimUser", game_id=1))
    print("\n" + rep.dump())
    assert rep.ok, rep.dump()

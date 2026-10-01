"""BLOXEN simulated historical client (SIMULATOR-TESTED harness).

Exercises the ACTUAL running services end to end:
  compat HTTP bootstrap -> RakNet -> descriptor sync -> SET_GLOBALS ->
  server ID_DATA -> Workspace -> place hierarchy -> Player/character.

Results are labeled SIMULATOR-TESTED — never REAL-CLIENT-TESTED.
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
from dataclasses import dataclass, field

from ..gameserver.bitstream import BitReader, BitWriter
from ..gameserver.descriptors import (MSG_DESCRIPTOR_BEGIN, MSG_DESCRIPTOR_END,
                                      MSG_ID_DATA, MSG_SET_GLOBALS)
from ..gameserver.raknet import RakNetClient
from ..gameserver.replicator import (FIRST_CONTAINER_CLASS_ID, TOP_CONTAINER_COUNT,
                                     WORKSPACE_PREAMBLE_BITS)

MSG_HELLO = 0xF0
MSG_HELLO_REPLY = 0xF1
MSG_REQUEST_DESCRIPTORS = 0xF2
MSG_PLAYER_INIT = 0xF3


@dataclass
class SimResult:
    step: str
    ok: bool
    detail: str = ""


@dataclass
class SimReport:
    results: list = field(default_factory=list)

    def add(self, step, ok, detail=""):
        self.results.append(SimResult(step, ok, detail))
        return ok

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def dump(self) -> str:
        lines = []
        for r in self.results:
            lines.append(f"[{'PASS' if r.ok else 'FAIL'}] {r.step}: {r.detail}")
        return "\n".join(lines)


def http_json(url: str, data: dict | None = None, headers=None) -> dict | str:
    req = urllib.request.Request(url, method="POST" if data is not None else "GET")
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("content-type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
        try:
            return json.loads(body)
        except Exception:
            return body.decode("utf-8", "replace")


async def run_scenario(web_base: str, compat_base: str, gs_addr: tuple,
                       username: str = "SimUser", password: str = "sim-password-1",
                       game_id: int = 1) -> SimReport:
    rep = SimReport()
    try:
        # 1. register + login through the real web API
        try:
            reg = http_json(f"{web_base}/api/auth/register",
                            {"username": username, "password": password})
            token = reg.get("token")
            rep.add("register", bool(token), f"user_id={reg.get('user_id')}")
        except Exception as e:
            if "409" in str(e):
                login = http_json(f"{web_base}/api/auth/login",
                                  {"username": username, "password": password})
                token = login.get("token")
                rep.add("register", True, "existing account, logged in instead")
            else:
                rep.add("register", False, str(e))
                return rep
        if not token:
            return rep

        # 2. Play -> ticket
        t = http_json(f"{web_base}/api/play/ticket", {"game_id": game_id},
                      headers={"Authorization": f"Bearer {token}"})
        ticket = t.get("ticket")
        rep.add("play-ticket", bool(ticket), f"ttl={t.get('expires_in')} uri={t.get('launch_uri')}")

        # 3. ticket validate (as the launcher would)
        v = http_json(f"{web_base}/api/play/validate",
                      {"ticket": ticket, "game_id": game_id})
        rep.add("ticket-validate", bool(v.get("ok")), f"game={v.get('game', {}).get('name') if v.get('game') else None}")

        # 4. compat bootstrap endpoints (actual compat service)
        try:
            neg = http_json(f"{compat_base}/Login/Negotiate.ashx")
            rep.add("compat-negotiate", bool(neg), str(neg)[:60])
            visit = http_json(f"{compat_base}/Game/Visit.ashx?gameId={game_id}")
            rep.add("compat-visit", "joinScript" in json.dumps(visit), str(visit)[:80])
            pl = http_json(f"{compat_base}/Game/PlaceLauncher.ashx?gameId={game_id}")
            rep.add("compat-placelauncher", "Joining" in json.dumps(pl), str(pl)[:80])
            cf = http_json(f"{compat_base}/Asset/CharacterFetch.ashx?userId=1")
            rep.add("compat-characterfetch", "userId" in json.dumps(cf), str(cf)[:80])
        except Exception as e:
            rep.add("compat-bootstrap", False, str(e))
            return rep

        # 5. RakNet connect to the REAL game server
        client = RakNetClient(gs_addr)
        try:
            await client.open()
            rep.add("raknet-handshake", True, f"connected to {gs_addr}")
        except Exception as e:
            rep.add("raknet-handshake", False, str(e))
            return rep

        # 6. hello / protocol version
        w = BitWriter()
        w.write_byte(MSG_HELLO)
        w.write_u32(31)
        await client.send_reliable(w.to_bytes())
        try:
            reply = await asyncio.wait_for(client.received.get(), timeout=5)
            r = BitReader(reply)
            msg = r.read_byte()
            proto = r.read_u32()
            guid = r.read_string().decode()
            rep.add("protocol-version", msg == MSG_HELLO_REPLY and proto == 31,
                    f"proto={proto} guid={guid}")
        except Exception as e:
            rep.add("protocol-version", False, str(e))
            return rep

        # 7. descriptor synchronization
        w = BitWriter()
        w.write_byte(MSG_REQUEST_DESCRIPTORS)
        await client.send_reliable(w.to_bytes())
        try:
            desc = bytearray()
            while True:
                chunk = await asyncio.wait_for(client.received.get(), timeout=5)
                desc += chunk
                if desc and desc[0] == MSG_DESCRIPTOR_BEGIN:
                    rr = BitReader(bytes(desc))
                    rr.read_byte()
                    classes = rr.read_u32()
                    props = rr.read_u32()
                    events = rr.read_u32()
                    types = rr.read_u32()
                    rep.add("descriptor-sync", classes == 332,
                            f"classes={classes} properties={props} events={events} types={types}")
                    break
                if bytes(desc).find(bytes([MSG_DESCRIPTOR_BEGIN])) < 0 and len(desc) > 200000:
                    rep.add("descriptor-sync", False, "no descriptor begin marker")
                    break
        except Exception as e:
            rep.add("descriptor-sync", False, str(e))
            return rep

        # 8. player init -> SET_GLOBALS + ID_DATA
        w = BitWriter()
        w.write_byte(MSG_PLAYER_INIT)
        w.write_u32(1)
        w.write_string(username)
        await client.send_reliable(w.to_bytes())

        set_globals = id_data = None
        try:
            for _ in range(4):
                pkt = await asyncio.wait_for(client.received.get(), timeout=20)
                rr = BitReader(pkt)
                m = rr.read_byte()
                if m == MSG_SET_GLOBALS:
                    set_globals = pkt
                elif m == MSG_ID_DATA:
                    id_data = pkt
                if set_globals and id_data:
                    break
        except Exception as e:
            rep.add("set-globals/id-data", False, f"timeout: {e}")
            return rep

        # 9. validate SET_GLOBALS layout against genuine-client observations
        if set_globals:
            rr = BitReader(set_globals)
            rr.read_byte()
            preamble_start = rr.pos
            first_class = rr.read_bits(16)
            top_count = rr.read_bits(8)
            preamble_bits = rr.pos - preamble_start
            # remaining preamble padding consumed below
            rr.read_bits(WORKSPACE_PREAMBLE_BITS - preamble_bits)
            ok = (first_class == FIRST_CONTAINER_CLASS_ID
                  and top_count == TOP_CONTAINER_COUNT
                  and WORKSPACE_PREAMBLE_BITS == 121)
            rep.add("set-globals", ok,
                    f"preamble={WORKSPACE_PREAMBLE_BITS}b first_class={first_class} "
                    f"(expect 231 ReplicatedFirst) top_containers={top_count} (expect 22)")
        else:
            rep.add("set-globals", False, "not received")

        # 10. validate ID_DATA (authoritative server -> client)
        if id_data:
            rr = BitReader(id_data)
            rr.read_byte()
            count = rr.read_u32()
            names = []
            for _ in range(min(count, 2000)):
                ref = rr.read_u32()
                cid = rr.read_u32()
                names.append(rr.read_string().decode("utf-8", "replace"))
                rr.read_u32()
                nprops = rr.read_u32()
                for _p in range(nprops):
                    rr.read_string()
                    t = rr.read_byte()
                    if t == 2:
                        rr.read_byte()
                    elif t == 3:
                        rr.read_u32()
                    else:
                        rr.read_string()
            interesting = [n for n in names if n in ("Humanoid", "Torso", "Head", "Players", "BodyColors")]
            rep.add("id-data", count > 0,
                    f"instances={count} player-tree={interesting}")
        else:
            rep.add("id-data", False, "not received")

    finally:
        try:
            client.transport.close()
        except Exception:
            pass
    return rep


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://127.0.0.1:8080")
    ap.add_argument("--compat", default="http://127.0.0.1:8081")
    ap.add_argument("--gs-host", default="127.0.0.1")
    ap.add_argument("--gs-port", type=int, default=53640)
    ap.add_argument("--username", default="SimUser")
    ap.add_argument("--game", type=int, default=1)
    args = ap.parse_args()
    rep = asyncio.run(run_scenario(args.web, args.compat, (args.gs_host, args.gs_port),
                                   username=args.username, game_id=args.game))
    print(rep.dump())
    print("SIMULATOR RESULT:", "PASS" if rep.ok else "FAIL")


if __name__ == "__main__":
    main()

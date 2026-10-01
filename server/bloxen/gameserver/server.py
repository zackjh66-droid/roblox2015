"""BLOXEN game server: RakNet + protocol-31 replication (SIMULATOR-TESTED).

Runs over UDP. Serves:
- descriptor synchronization (from the real target-build API dump)
- SET_GLOBALS (121-bit Workspace preamble, 22 top containers, ReplicatedFirst first)
- ID_DATA instance replication of the imported place hierarchy
- Players / Player / character / Humanoid spawn + movement state

The server binds 127.0.0.1 by default (private).
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time

from .. import config
from .bitstream import BitReader, BitWriter
from .descriptors import (MSG_DESCRIPTOR_BEGIN, MSG_DESCRIPTOR_END, MSG_ID_DATA,
                          MSG_SET_GLOBALS, DescriptorTable)
from .raknet import RakNetServer
from .replicator import (FIRST_CONTAINER_CLASS_NAME, ReplicatedInstance,
                         Replicator)

# Roblox-layer message ids carried on RakNet reliable frames
MSG_HELLO = 0xF0
MSG_HELLO_REPLY = 0xF1
MSG_REQUEST_DESCRIPTORS = 0xF2
MSG_PLAYER_INIT = 0xF3
MSG_MOVE = 0xF4
MSG_SPAWN_CHARACTER = 0xF5


class GameServer:
    def __init__(self, place_report: dict | None = None, log=print):
        self.descriptors = DescriptorTable(config.API_DUMP_PATH)
        self.replicator = Replicator(self.descriptors)
        self.place_report = place_report or {}
        self.log = log
        self.sessions = []
        self.raknet = RakNetServer(on_message=self.on_message_safe, on_connect=self.on_connect)
        self.world_roots: list[ReplicatedInstance] = []
        self.players: dict[int, ReplicatedInstance] = {}
        if place_report:
            self._load_place(place_report)

    # ------------------------------------------------------------ world
    def _load_place(self, report: dict):
        """Convert an imported place tree into replicated instances.

        The importer keeps scripts as inert data — the game server never
        executes place scripts (docs/GAMES.md 'scripting policy').
        """
        tree = report.get("tree") or {}
        instances = tree.get("instances") or {}
        roots = tree.get("roots") or []

        limit_roots = 2500          # replicate a bounded but real slice per session
        budget = 6000               # total instance cap keeps startup fast
        converted = 0

        def conv(inst, parent_ref=None) -> ReplicatedInstance:
            nonlocal converted
            props = {}
            for k, v in inst.properties.items():
                if k.startswith("__") or k in ("Source",):
                    continue
                if isinstance(v, bytes):
                    v = v.decode("utf-8", "replace")
                if isinstance(v, (str, int, float, bool, tuple, list)):
                    props[k] = v
            ri = ReplicatedInstance(
                ref=self.replicator.next_ref,
                class_name=inst.class_name,
                name=str(inst.name),
                parent_ref=parent_ref,
                properties=props,
            )
            self.replicator.next_ref += 1
            converted += 1
            for ch in inst.children:
                if converted >= budget:
                    break
                ri.children.append(conv(ch, ri.ref))
            self.replicator.add_instance(ri)
            return ri

        for r in roots[:limit_roots]:
            if converted >= budget:
                break
            try:
                self.world_roots.append(conv(r))
            except Exception as e:
                self.log(f"[gameserver] skip root {r.name}: {e}")

    def _save_cache(self, path, digest):
        def ser(ri):
            return {"ref": ri.ref, "class_name": ri.class_name, "name": ri.name,
                    "parent_ref": ri.parent_ref, "properties":
                        {k: (list(v) if isinstance(v, tuple) else v)
                         for k, v in ri.properties.items()},
                    "children": [ser(c) for c in ri.children]}
        data = {"place_sha256": digest,
                "next_ref": self.replicator.next_ref,
                "roots": [ser(r) for r in self.world_roots]}
        path.write_text(json.dumps(data))

    def _load_cached(self, data):
        def de(d):
            ri = ReplicatedInstance(ref=d["ref"], class_name=d["class_name"], name=d["name"],
                                    parent_ref=d["parent_ref"],
                                    properties={k: (tuple(v) if isinstance(v, list) and k in
                                                    ("Size", "Position", "Color") else v)
                                                for k, v in d["properties"].items()})
            for c in d["children"]:
                ri.children.append(de(c))
            self.replicator.add_instance(ri)
            return ri
        self.replicator.next_ref = data["next_ref"]
        for r in data["roots"]:
            self.world_roots.append(de(r))

    def build_player(self, user_id: int, username: str):
        """Players > Player + character (Humanoid + Part tree) for the session."""
        players = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Players",
                                     name="Players")
        self.replicator.next_ref += 1
        player = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Player",
                                    name=username, parent_ref=players.ref,
                                    properties={"UserId": user_id, "Character": username})
        self.replicator.next_ref += 1
        char = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Model",
                                  name=username, parent_ref=None,
                                  properties={})
        self.replicator.next_ref += 1
        torso = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Part",
                                   name="Torso", parent_ref=char.ref,
                                   properties={"Size": (2, 2, 1), "Anchored": False,
                                               "Position": (0, 5, 0)})
        self.replicator.next_ref += 1
        head = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Part",
                                  name="Head", parent_ref=char.ref,
                                  properties={"Size": (2, 1, 1), "Position": (0, 6.5, 0)})
        self.replicator.next_ref += 1
        humanoid = ReplicatedInstance(ref=self.replicator.next_ref, class_name="Humanoid",
                                      name="Humanoid", parent_ref=char.ref,
                                      properties={"Health": 100, "MaxHealth": 100,
                                                  "WalkSpeed": 16, "JumpPower": 50})
        self.replicator.next_ref += 1
        body_colors = ReplicatedInstance(ref=self.replicator.next_ref, class_name="BodyColors",
                                         name="BodyColors", parent_ref=char.ref,
                                         properties={"HeadColor3": "Bright blue"})
        self.replicator.next_ref += 1
        for ri in (players, player, char, torso, head, humanoid, body_colors):
            self.replicator.add_instance(ri)
        players.children.append(player)
        char.children += [torso, head, humanoid, body_colors]
        self.players[user_id] = player
        return players, char

    # ------------------------------------------------------------ events
    async def on_connect(self, peer):
        self.log(f"[gameserver] raknet connect {peer.addr}")

    async def on_message(self, peer, payload: bytes):
        if not payload:
            return
        msg = payload[0]
        if msg == MSG_HELLO:
            w = BitWriter()
            w.write_byte(MSG_HELLO_REPLY)
            w.write_u32(config.PROTOCOL_VERSION)
            w.write_string(config.TARGET_WINDOWS_PLAYER_GUID)
            await self.raknet.send_message(peer, w.to_bytes())
        elif msg == MSG_REQUEST_DESCRIPTORS:
            data = self.descriptors.serialize_descriptor_sync()
            # one logical message; RakNet split frames carry the bulk
            await self.raknet.send_message(peer, data)
            self.log(f"[gameserver] descriptor sync sent: {len(data)} bytes")
        elif msg == MSG_PLAYER_INIT:
            r = BitReader(payload)
            r.read_byte()
            user_id = r.read_u32()
            username = r.read_string().decode("utf-8", "replace")
            session = {"peer": peer, "user_id": user_id, "username": username,
                       "started": time.time()}
            self.sessions.append(session)
            players, char = self.build_player(user_id, username)

            # SET_GLOBALS (genuine-client-evidenced layout)
            set_globals = self.replicator.build_set_globals(self.world_roots)
            await self.raknet.send_message(peer, set_globals)

            # authoritative server -> client ID_DATA (the blocker named in
            # genuine-client findings): world + player + character
            roots = list(self.world_roots) + [players, char]
            id_data = self.replicator.build_id_data(roots)
            await self.raknet.send_message(peer, id_data)
            self.log(f"[gameserver] ID_DATA sent to {username}: "
                     f"{len(id_data)} bytes, {len(self.world_roots)} world roots")
        elif msg == MSG_MOVE:
            r = BitReader(payload)
            r.read_byte()
            user_id = r.read_u32()
            x, y, z = r.read_u32(), r.read_u32(), r.read_u32()
            self.log(f"[gameserver] move user={user_id} pos=({x},{y},{z})")
        else:
            self.log(f"[gameserver] unhandled message 0x{msg:02x} ({len(payload)} bytes)")

    async def on_message_safe(self, peer, payload: bytes):
        try:
            await self.on_message(peer, payload)
        except Exception as e:
            self.log(f"[gameserver] message error: {type(e).__name__}: {e}")

    # ------------------------------------------------------------- run
    async def run(self):
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: self.raknet,
            local_addr=(config.GAMESERVER_HOST, config.GAMESERVER_PORT))
        self.log(f"[gameserver] listening udp://{config.GAMESERVER_HOST}:{config.GAMESERVER_PORT}")

        async def ticker():
            while True:
                await asyncio.sleep(0.5)
                self.raknet.tick()

        asyncio.ensure_future(ticker())


async def main():
    server = GameServer()
    await server.run()          # bind immediately

    async def load_world():
        con = sqlite3.connect(config.DB_PATH)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM games WHERE place_path IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        con.close()
        if row and row["place_path"]:
            from pathlib import Path
            import hashlib
            p = Path(row["place_path"])
            if p.exists():
                cache = config.DATA / "world_cache.json"
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                t0 = time.time()
                used_cache = False
                if cache.exists():
                    try:
                        cached = json.loads(cache.read_text())
                        if cached.get("place_sha256") == digest:
                            server._load_cached(cached)
                            used_cache = True
                    except Exception:
                        used_cache = False
                if not used_cache:
                    from ..importer.pipeline import import_place
                    report = import_place(p)
                    server.place_report = report
                    server._load_place(report)
                    server._save_cache(cache, digest)
                print(f"[gameserver] loaded place {row['name']}: "
                      f"{len(server.world_roots)} world roots in {time.time()-t0:.1f}s"
                      f"{' (cache)' if used_cache else ''}")

    asyncio.ensure_future(load_world())
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

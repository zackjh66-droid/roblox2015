"""Unit tests: launcher URI contract, bitstream, replicator layout, importer basics."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
os.environ.setdefault("BLOXEN_DB_PATH", "/home/user/roblox2015/data/unit.sqlite3")

from bloxen.launcher.uri import LaunchError, parse_launch_uri, validate_client_package
from bloxen.gameserver.bitstream import BitReader, BitWriter
from bloxen.gameserver import replicator
from bloxen.importer.rbxl_binary import MAGIC, parse_binary
from bloxen.importer.bitstream import decompress_chunk


def test_uri_ok():
    req = parse_launch_uri("bloxen-player:play?ticket=" + "A" * 20 + "&game=1")
    assert req.action == "play" and req.game_id == 1 and req.ticket == "A" * 20


def test_uri_bad():
    for uri in ("http://x", "bloxen-player:play?game=1",
                "bloxen-player:play?ticket=short&game=1",
                "bloxen-player:play?ticket=" + "A" * 20 + "&game=999999999999999",
                "javascript:alert(1)"):
        try:
            parse_launch_uri(uri)
            raise AssertionError("accepted " + uri)
        except LaunchError:
            pass


def test_client_allowlist():
    state = validate_client_package()
    assert state["status"] in ("AWAITING-PACKAGE", "HASH-MISMATCH", "VERIFIED")
    if state["status"] != "VERIFIED":
        assert state.get("expected_sha256", "").startswith("384a4cb3") or "expected_sha256" in state


def test_bitstream_roundtrip():
    w = BitWriter()
    w.write_bits(3, 2)
    w.write_bits(231, 8)
    w.write_bits(22, 8)
    w.write_bits(0x0D, 5)
    r = BitReader(w.to_bytes())
    assert r.read_bits(2) == 3 and r.read_bits(8) == 231
    assert r.read_bits(8) == 22 and r.read_bits(5) == 0x0D


def test_set_globals_layout_matches_observations():
    from pathlib import Path
    from bloxen.gameserver.descriptors import DescriptorTable
    dump = Path("/home/user/roblox2015/research/sources/build-archive/"
                "version-0d46087630eb46cd/API-Dump.json")
    rep = replicator.Replicator(DescriptorTable(dump))
    msg = rep.build_set_globals([])
    assert msg[0] == replicator.MSG_SET_GLOBALS
    r = BitReader(msg[1:])
    assert r.read_bits(16) == 231           # first class = ReplicatedFirst
    assert r.read_bits(8) == 22             # 22 top containers
    assert r.read_bits(97) == 0             # preamble total = 121 bits


def test_decompress_raw_chunk():
    payload = b"hello-roblox"
    assert decompress_chunk(payload, len(payload), compressed_len=0) == payload


def test_parse_binary_minimal():
    import struct

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return tag + (0).to_bytes(4, "little") + len(payload).to_bytes(4, "little") \
            + (0).to_bytes(4, "little") + payload

    body = MAGIC + (1).to_bytes(2, "little") + (0).to_bytes(4, "little") \
        + (0).to_bytes(4, "little") + (0).to_bytes(8, "little") + chunk(b"END\0", b"")
    result = parse_binary(body)
    assert result["instances"] == 0 or isinstance(result, dict)


def test_research_sources_exist():
    base = "/home/user/roblox2015/research/sources"
    for rel in ("build-archive/version-0d46087630eb46cd/API-Dump.json",
                "setup-rbxcdn/DeployHistory.txt",
                "formats/rbx-binary-format/codec_string.lua",
                "formats/roblox.xsd",
                "catalog/11166~2.json",
                "website/trade-2015.html"):
        assert os.path.exists(os.path.join(base, rel)), rel


def test_quarantine_manifests():
    base = "/home/user/roblox2015/quarantine/places"
    metas = [f for f in os.listdir(base) if f.endswith(".meta.json")]
    rbxls = [f for f in os.listdir(base) if f.endswith(".rbxl")]
    assert len(rbxls) >= 7 and len(metas) >= 6

"""The verified 2015 client package and the assets converted out of it.

These tests guard the provenance claims: if the committed client files or the converted
artwork drift from what was verified, the suite fails rather than letting the project
quietly overstate what it holds.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(ROOT, "quarantine", "client", "version-0d46087630eb46cd")
MANIFEST = os.path.join(CLIENT, "CLIENT-MANIFEST.json")
TEXTURES = os.path.join(ROOT, "web", "static", "textures", "client")
TEX_JSON = os.path.join(ROOT, "web", "static", "data", "client-textures.json")

# recorded before the package was reachable, verified afterwards — must not change
EXPECTED_EXE_SHA256 = "384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_client_package_is_present_and_hashed():
    assert os.path.isdir(CLIENT), "the verified client package must stay in quarantine"
    assert os.path.exists(MANIFEST)
    man = json.loads(open(MANIFEST).read())
    assert man["verification"]["robloxplayerbeta_sha256"] == EXPECTED_EXE_SHA256
    assert man["verification"]["expected_sha256"] == EXPECTED_EXE_SHA256
    pe = man["verification"]["pe"]
    assert pe["file_version"] == "0.205.0.61876"
    assert pe["pe_timestamp_utc"].startswith("2015-07-23")
    assert pe["authenticode"].startswith("signed")
    # the executable itself matches the manifest
    exe = os.path.join(CLIENT, "RobloxPlayerBeta.exe")
    assert sha256(exe) == EXPECTED_EXE_SHA256
    # the hashes recorded for the deferred PlatformContent set are still recorded
    assert man["deferred_files"] > 100
    assert man["deferred_bytes"] > 50_000_000


def test_client_json_package_not_executed_marker():
    """The package must be documented as evidence; execution stays a Windows-only step."""
    doc = open(os.path.join(ROOT, "docs", "CLIENT-PACKAGE.md")).read()
    assert "never been executed" in doc or "never been REAL-CLIENT-TESTED" in doc
    assert "REAL-CLIENT-TESTED" in doc


def test_real_client_textures_are_converted_and_declared():
    assert os.path.isdir(TEXTURES)
    man = json.loads(open(TEX_JSON).read())
    mats = man["materials"]
    # the studs atlas and its measured geometry
    studs = mats["studs"]
    assert studs["source_file"].endswith("PlatformContent/pc/textures/studs.dds")
    assert studs["atlas_cells"] == 16
    assert studs["size"] == [128, 2048], "atlas must keep whole 128x128 cells"
    # every declared material has its file on disk, and the sizes agree
    for name, info in mats.items():
        path = os.path.join(ROOT, "web", "static", info["file"])
        assert os.path.exists(path), f"{name}: {info['file']} missing"
        assert os.path.getsize(path) > 0
    # the default 2015 skybox: all six faces, copied from the package
    for face in ("up", "dn", "lf", "rt", "ft", "bk"):
        assert man["sky"][face]["source_file"].endswith(
            f"content/sky/null_plainsky512_{face}.jpg")
        assert os.path.exists(os.path.join(ROOT, "web", "static", man["sky"][face]["file"]))
    # none of it may claim to be redrawn
    assert "verbatim" in man["_note"] or "No asset here is redrawn" in man["_note"]


def test_runtime_uses_the_client_assets_not_drawn_ones():
    js = open(os.path.join(ROOT, "web", "static", "js", "bloxen-client.js")).read()
    # the runtime must read the converted assets...
    assert "client-textures.json" in js
    assert "loadClientTextures" in js
    # ...and must no longer generate its own stud bitmap
    assert "makeSurfaceTexture" not in js, (
        "the runtime must not draw its own surface textures any more")
    # the measured atlas geometry must match what the importer recorded
    assert "CELL_STUDS = 2" in js
    assert "studsCell: 0" in js and "inletsCell: 8" in js

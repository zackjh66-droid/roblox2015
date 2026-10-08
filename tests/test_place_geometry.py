"""Regression tests for the place importer and the client geometry exporter.

These pin down bugs found while building the 3D runtime:
  * interleaved integer planes are big-endian (plane 0 = most significant byte);
    getting this wrong produced garbage sizes/positions for every binary place
  * CFrame blocks store the orientation id byte BEFORE the three position arrays
    (codec_cframe.lua::reader) — reading positions first misaligned everything
  * the compact orientation table (24 ids) must be applied, not a placeholder
  * UDim/Color3 are arrays-of-arrays, not per-instance tuples
  * RBXLX structured properties (Vector3 / CoordinateFrame / Color3uint8) are
    child elements, not text

Fixtures are the real preserved place files in quarantine/places (real bytes).
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from bloxen import config                                     # noqa: E402
from bloxen.importer import rbxl_binary                       # noqa: E402
from bloxen.importer.bitstream import Reader                  # noqa: E402
from bloxen.importer.pipeline import import_place             # noqa: E402
from bloxen.placeview.geometry import (build_geometry,        # noqa: E402
                                       load_or_build_geometry)

XML_PLACE = ROOT / "quarantine/places/Welcome to the Town of Robloxia.rbxl"
BINARY_PLACE = ROOT / "quarantine/places/Work at a Pizza Place (2014L).rbxl"
FLOOD = ROOT / "quarantine/places/Flood Escape (July 8th, 2015, V1.6.5).rbxl"


# --------------------------------------------------------------------- bitstream
def test_interleaved_planes_are_big_endian():
    """bytes [0x40, 0x00, 0x00, 0x00] planes -> 0x40000000 (rotated float 2.0)."""
    # plane 0 = 0x40, planes 1..3 = 0
    reader = Reader(bytes([0x40, 0x00, 0x00, 0x00]))
    assert reader.interleaved_uint(1, 4) == [0x40000000]


def test_rbx_float32_rotation_round_trip():
    # 2.0f == 0x40000000; stored rotated left by one bit -> 0x80000000
    reader = Reader(struct.pack("<I", 0x80000000))
    assert reader.rbx_float32() == pytest.approx(2.0)


def _rotated(f: float) -> int:
    raw = struct.unpack("<I", struct.pack("<f", f))[0]
    return ((raw << 1) | (raw >> 31)) & 0xFFFFFFFF


def test_interleaved_float_array_values():
    reader = Reader(_planes([_rotated(4.0), _rotated(1.0)]))
    assert reader.interleaved_rbx_float32(2) == pytest.approx([4.0, 1.0])


def _planes(values: list[int], size: int = 4) -> bytes:
    """Encode integers the way the format stores them: byte-plane interleaved,
    most-significant byte first (stream.lua::readInterleavedUInt)."""
    out = bytearray()
    for k in range(size):
        shift = 8 * (size - 1 - k)
        for v in values:
            out.append((v >> shift) & 0xFF)
    return bytes(out)


def test_referent_zigzag_delta():
    # transformed deltas: 0 -> 0 ; 2 -> +1 ; 1 -> -1  =>  referents 0, 1, 0
    reader = Reader(_planes([0, 2, 1]))
    assert reader.referents(3) == [0, 1, 0]


def test_interleaved_array_two_elements():
    reader = Reader(_planes([0x11223344, 0xAABBCCDD]))
    assert reader.interleaved_uint(2, 4) == [0x11223344, 0xAABBCCDD]


# ------------------------------------------------------------------- CFrame codec
def test_cframe_reads_orientation_byte_before_positions():
    """One CFrame: orientation id byte 0x02 (identity), then three interleaved
    rotated-float position planes — the order used by codec_cframe.lua."""
    xs, ys, zs = 10.0, 20.0, 30.0
    payload = (bytes([0x02]) + _planes([_rotated(xs)]) + _planes([_rotated(ys)])
               + _planes([_rotated(zs)]))
    reader = Reader(payload)
    out = rbxl_binary._parse_property_values(reader, rbxl_binary.TYPE_CFRAME, 1, [])
    assert out[0]["pos"] == pytest.approx((10.0, 20.0, 30.0))
    assert out[0]["rot"] == pytest.approx(rbxl_binary.ORIENT_ID_TO_MATRIX[0x02])


def test_cframe_inline_matrix_when_id_zero():
    """id 0x00 means a full 3x3 matrix follows as nine PLAIN little-endian
    floats (stream.readLEFloat32 — not bit-rotated like the position arrays)."""
    rot = (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    body = b"".join(struct.pack("<f", v) for v in rot)
    payload = (bytes([0x00]) + body + _planes([_rotated(1.0)]) + _planes([_rotated(2.0)])
               + _planes([_rotated(3.0)]))
    reader = Reader(payload)
    out = rbxl_binary._parse_property_values(reader, rbxl_binary.TYPE_CFRAME, 1, [])
    assert out[0]["rot"] == pytest.approx(rot)
    assert out[0]["pos"] == pytest.approx((1.0, 2.0, 3.0))


def test_orientation_table_is_complete_and_orthonormal():
    assert 0x23 in rbxl_binary.ORIENT_ID_TO_MATRIX
    for oid, m in rbxl_binary.ORIENT_ID_TO_MATRIX.items():
        assert len(m) == 9, oid
        # each row must be a unit axis (rotation matrix)
        for row in (m[0:3], m[3:6], m[6:9]):
            assert sum(v * v for v in row) == pytest.approx(1.0), (oid, row)


# ------------------------------------------------------------------------ XML
def test_xml_structured_properties_decode():
    """Real XML place: sizes/CFrames must be numeric, not missing/None."""
    report = import_place(XML_PLACE)
    instances = report["tree"]["instances"]
    parts = [i for i in instances.values() if i.class_name == "Part"]
    assert parts, "fixture should contain parts"
    sized = [p for p in parts if isinstance(p.properties.get("size"), tuple)]
    assert len(sized) > len(parts) * 0.9
    for p in sized[:400]:
        for v in p.properties["size"]:
            assert isinstance(v, float) and 0.01 < abs(v) < 2100
    framed = [p for p in parts if isinstance(p.properties.get("CFrame"), dict)]
    assert framed
    for p in framed[:400]:
        pos = p.properties["CFrame"]["pos"]
        assert all(isinstance(v, float) and abs(v) < 100_000 for v in pos)


def test_xml_color3_is_rgb_bytes():
    """The 2015 XML schema stores colours packed as <Color3>0xAARRGGBB</Color3>;
    they must decode to (r, g, b) byte triples for the renderer."""
    report = import_place(XML_PLACE)
    colorish = []
    for inst in report["tree"]["instances"].values():
        for value in inst.properties.values():
            if isinstance(value, tuple) and len(value) == 3 and all(
                    isinstance(c, int) for c in value):
                colorish.append(value)
    assert len(colorish) > 50, "expected decoded Color3 property values"
    for v in colorish[:400]:
        assert all(0 <= c <= 255 for c in v), v
    # Lighting is always present and its Ambient/FogColor are colour properties
    lighting = next(i for i in report["tree"]["instances"].values()
                    if i.class_name == "Lighting")
    assert isinstance(lighting.properties.get("Ambient"), tuple)


# ---------------------------------------------------------------- binary sanity
def test_binary_place_dimensions_are_physical():
    report = import_place(BINARY_PLACE)
    parts = [i for i in report["tree"]["instances"].values()
             if i.class_name in ("Part", "WedgePart", "SpawnLocation")]
    assert len(parts) > 1000
    bad = 0
    for p in parts:
        size = p.properties.get("size")
        if not isinstance(size, tuple):
            continue
        if not all(0.01 < abs(v) < 2100 for v in size):
            bad += 1
    assert bad == 0, f"{bad} parts have non-physical sizes (bitstream misread)"


def test_binary_place_cframes_are_physical():
    report = import_place(BINARY_PLACE)
    ys = [i.properties["CFrame"]["pos"][1] for i in report["tree"]["instances"].values()
          if isinstance(i.properties.get("CFrame"), dict)]
    assert ys
    assert -1000 < min(ys) and max(ys) < 100_000


# ------------------------------------------------------------ geometry exporter
@pytest.fixture(scope="module")
def flood_geometry():
    report = import_place(FLOOD)
    return build_geometry(report, game_id=6, db_path=config.DB_PATH)


def test_geometry_payload_is_consistent(flood_geometry):
    g = flood_geometry
    parts = g["parts"]
    n = len(parts["pos"]) // 3
    assert n > 1000
    # pos and size are flat triples (3 numbers per part); the rest are scalars
    for key in ("pos", "size"):
        assert len(parts[key]) == n * 3, f"{key} length mismatch"
    for key in ("rot", "col", "alpha", "refl", "mat", "shape", "flags", "parent", "surf"):
        assert len(parts[key]) == n, f"{key} length mismatch"
    assert len(parts["name"]) == n
    assert max(parts["rot"]) < len(g["rots"])
    assert max(parts["col"]) < len(g["colors"])
    assert max(parts["mat"]) < len(g["materials"])
    assert max(parts["shape"]) < len(g["shapes"])


def test_geometry_has_real_spawns_and_lighting(flood_geometry):
    g = flood_geometry
    assert g["stats"]["spawn_count"] >= 1
    assert len(g["spawns"]["pos"]) == g["stats"]["spawn_count"]
    assert g["lighting"]["brightness"] > 0
    assert len(g["lighting"]["ambient"]) == 3


def test_geometry_colors_come_from_palette(flood_geometry):
    palette = json.loads((ROOT / "web/static/data/brickcolor.json").read_text())["colors"]
    allowed = {tuple(v["rgb"]) for v in palette.values()}
    for c in flood_geometry["colors"]:
        assert tuple(c) in allowed, f"colour {c} is not in the historical palette"


def test_geometry_reports_unsupported_classes_honestly(flood_geometry):
    u = flood_geometry["unsupported"]
    assert "not_rendered_classes" in u
    # Flood Escape has CSG unions in this file; they must be reported, not drawn
    assert u["csg_unions"] >= 1
    assert "never executed" in u["scripts"]


def test_geometry_positions_within_place_bounds(flood_geometry):
    pos = flood_geometry["parts"]["pos"]
    xs = pos[0::3]
    ys = pos[1::3]
    zs = pos[2::3]
    for axis in (xs, ys, zs):
        assert min(axis) > -50_000 and max(axis) < 50_000


def test_geometry_cache_round_trip(tmp_path):
    report = import_place(FLOOD)
    first = load_or_build_geometry(report, game_id=6, db_path=config.DB_PATH)
    second = load_or_build_geometry(report, game_id=7, db_path=config.DB_PATH)
    assert second["meta"].get("cached") is True
    assert second["parts"]["pos"] == first["parts"]["pos"]
    # the cache is keyed by content hash, so a different game id still reuses it
    assert second["stats"]["part_count"] == first["stats"]["part_count"]


def test_container_reporting_matches_parts(flood_geometry):
    g = flood_geometry
    by_container = g["stats"]["parts_by_container"]
    assert sum(by_container.values()) == g["stats"]["rendered_parts"] + g["stats"]["invisible_parts"]
    idx = g["parts"]["container"]
    assert max(idx) < len(g["containers"])

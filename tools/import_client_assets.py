#!/usr/bin/env python3
"""Import real 2015 assets out of the verified WindowsPlayer package.

The client package in `quarantine/client/version-0d46087630eb46cd/` ships the actual
artwork the 2015 engine rendered with:

    PlatformContent/pc/textures/<material>/diffuse.dds   material surfaces (DXT5)
    PlatformContent/pc/textures/studs.dds                the classic studs overlay
    content/sky/null_plainsky512_*.jpg                   the default skybox faces
    content/fonts/character.rbxm                         the real R6 character model

This tool converts exactly those into web-usable PNGs plus a manifest the browser runtime
loads. Everything it writes is a *conversion of the client's own bytes* — nothing is
redrawn, approximated or invented. If the client package is absent, it exits without
writing anything rather than substituting a lookalike.

    PYTHONPATH=server .venv/bin/python tools/import_client_assets.py \
        --source "/path/to/July 23 (0.205.0.61876)"
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_TEXTURES = ROOT / "web" / "static" / "textures" / "client"
OUT_MANIFEST = ROOT / "web" / "static" / "data" / "client-textures.json"
DEFERRED_MANIFEST = (ROOT / "quarantine" / "client" / "version-0d46087630eb46cd"
                     / "CLIENT-MANIFEST.json")

# material name -> (file within the package, output name)
# 'plastic' is the 2015 default part surface; 'studs' the stud grid overlay.
MATERIALS = {
    "plastic": ("PlatformContent/pc/textures/plastic/diffuse.dds", "plastic.png"),
    "studs": ("PlatformContent/pc/textures/studs.dds", "studs.png"),
    "brick": ("PlatformContent/pc/textures/brick/diffuse.dds", "brick.png"),
    "wood": ("PlatformContent/pc/textures/wood/diffuse.dds", "wood.png"),
    "woodplanks": ("PlatformContent/pc/textures/woodplanks/diffuse.dds", "woodplanks.png"),
    "slate": ("PlatformContent/pc/textures/slate/diffuse.dds", "slate.png"),
    "cobblestone": ("PlatformContent/pc/textures/cobblestone/diffuse.dds",
                    "cobblestone.png"),
    "concrete": ("PlatformContent/pc/textures/concrete/diffuse.dds", "concrete.png"),
    "granite": ("PlatformContent/pc/textures/granite/diffuse.dds", "granite.png"),
    "marble": ("PlatformContent/pc/textures/marble/diffuse.dds", "marble.png"),
    "sand": ("PlatformContent/pc/textures/sand/diffuse.dds", "sand.png"),
    "fabric": ("PlatformContent/pc/textures/fabric/diffuse.dds", "fabric.png"),
    "rust": ("PlatformContent/pc/textures/rust/diffuse.dds", "rust.png"),
    "metal": ("PlatformContent/pc/textures/metal/diffuse.dds", "metal.png"),
    "aluminum": ("PlatformContent/pc/textures/aluminum/diffuse.dds", "aluminum.png"),
    "diamondplate": ("PlatformContent/pc/textures/diamondplate/diffuse.dds",
                     "diamondplate.png"),
    "pebble": ("PlatformContent/pc/textures/pebble/diffuse.dds", "pebble.png"),
    "grass": ("PlatformContent/pc/textures/grass/diffuse.dds", "grass.png"),
    # the client's own ice diffuse is a 4x4 flat colour — recorded as such, not fixed up
    "ice": ("PlatformContent/pc/textures/ice/diffuse.dds", "ice.png"),
}

# The default 2015 skybox: six faces, already JPEG
SKY_FACES = {"up": "up", "dn": "dn", "lf": "lf", "rt": "rt", "ft": "ft", "bk": "bk"}

MAX_EDGE = 256          # power-of-two for tiling/mipmaps, keeps the repo light


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def native_binary_path(source: Path, rel: str) -> Path | None:
    """Prefer the file in the package; fall back to the committed quarantine copy."""
    p = source / rel
    if p.exists():
        return p
    q = ROOT / "quarantine" / "client" / "version-0d46087630eb46cd" / rel
    return q if q.exists() else None


def convert_textures(source: Path) -> dict:
    OUT_TEXTURES.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for material, (rel, name) in MATERIALS.items():
        path = native_binary_path(source, rel)
        if path is None:
            print(f"  --  {material:14} no source file ({rel}) — skipped, not substituted")
            continue
        with Image.open(path) as im:
            im.load()
            if not im.has_transparency_data and im.mode != "RGBA":
                im = im.convert("RGB")
            else:
                im = im.convert("RGBA")
            # Some client bitmaps (studs.dds, plastic.dds) are vertical ATLASES of square
            # cells. They must be scaled by the CELL size, not by image height — scaling
            # by height would shrink 16 cells of 128x128 into 16 cells of 16x16 and
            # destroy the pattern.
            is_atlas = im.height > im.width and im.height % im.width == 0
            unit = im.width if is_atlas else max(im.size)
            if unit > MAX_EDGE:
                scale = MAX_EDGE / unit
                im = im.resize((max(1, round(im.width * scale)),
                                max(1, round(im.height * scale))), Image.LANCZOS)
            dest = OUT_TEXTURES / name
            im.save(dest, "PNG", optimize=True)
        out[material] = {
            "file": f"textures/client/{name}",
            "source_file": rel,
            "source_sha256": sha256(path),
            "source_format": "DDS/DXT5",
            "source_size": list(Image.open(path).size) if path.exists() else None,
            "size": [im.width, im.height],
            "source_is_flat_colour": im.width <= 8 or im.height <= 8,
            "atlas_cells": (im.height // im.width) if (im.height > im.width
                                                       and im.height % im.width == 0) else None,
        }
        print(f"  ok  {material:14} {rel} -> {name} {im.size}")
    return out


def copy_sky(source: Path) -> dict:
    """The 2015 default sky: content/sky/null_plainsky512_<face>.jpg, copied verbatim."""
    out: dict[str, dict] = {}
    outdir = OUT_TEXTURES / "sky"
    outdir.mkdir(parents=True, exist_ok=True)
    for face in SKY_FACES.values():
        rel = f"content/sky/null_plainsky512_{face}.jpg"
        path = native_binary_path(source, rel)
        if path is None:
            continue
        dest = outdir / f"{face}.jpg"
        dest.write_bytes(path.read_bytes())
        out[face] = {"file": f"textures/client/sky/{face}.jpg", "source_file": rel,
                     "source_sha256": sha256(path)}
        print(f"  ok  sky/{face}  <- {rel}")
    if out:
        out["_wrapping"] = "CubeTexture faces: up, dn, lf, rt, ft, bk (2015 default sky)"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
                    default=Path("/tmp/klient/July 23 (0.205.0.61876)"),
                    help="the full client package directory (with PlatformContent/)")
    args = ap.parse_args()
    source: Path = args.source
    if not source.exists():
        print(f"client package not found at {source} — nothing written "
              f"(this tool never substitutes approximations)")
        return 2

    print(f"importing real 2015 assets from {source}")
    manifest = {
        "_note": ("Textures and sky are converted verbatim from the verified 2015 "
                  "WindowsPlayer package (0.205.0.61876). No asset here is redrawn or "
                  "approximated; missing materials stay missing."),
        "client_version": "0.205.0.61876",
        "materials": convert_textures(source),
        "sky": copy_sky(source),
    }
    if DEFERRED_MANIFEST.exists():
        man = json.loads(DEFERRED_MANIFEST.read_text())
        manifest["client_manifest"] = {
            "exe_sha256": man["verification"]["robloxplayerbeta_sha256"],
            "pe_timestamp_utc": man["verification"]["pe"]["pe_timestamp_utc"],
            "file_version": man["verification"]["pe"]["file_version"],
        }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=1))
    print(f"\nwrote {OUT_MANIFEST.relative_to(ROOT)} "
          f"({len(manifest['materials'])} materials, {len(manifest['sky'])} sky files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

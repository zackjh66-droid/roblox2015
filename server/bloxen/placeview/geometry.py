"""Geometry export: parsed place tree -> compact, render-ready JSON.

Everything emitted here comes from the preserved place file itself:
part world CFrame, size, shape, BrickColor/Color3, transparency, reflectance,
material, collision flags, SpawnLocations, Decal/Texture references and the
Lighting service values. Nothing is synthesized:

- classes we cannot yet render faithfully (CSG UnionOperations, meshes whose
  asset data is not recovered, terrain voxels) are NOT drawn and are reported
  in `unsupported` instead of being replaced by an invented approximation
- texture/mesh asset ids are listed with their recovery status; the client only
  draws the ones actually recovered (docs/ASSETS.md)

Coordinates are Roblox studs, handedness preserved: the client converts to its
own axes. Rotation matrices are stored exactly as decoded from the file.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config

# Enum values from the target build API dump (version-0d46087630eb46cd)
MATERIAL_NAMES = {
    256: "Plastic", 272: "SmoothPlastic", 288: "Neon", 512: "Wood", 528: "WoodPlanks",
    784: "Marble", 788: "Basalt", 800: "Slate", 804: "CrackedLava", 816: "Concrete",
    832: "Granite", 848: "Brick", 864: "Pebble", 880: "Cobblestone", 896: "Rock",
    912: "Sandstone", 1040: "CorrodedMetal", 1056: "DiamondPlate", 1072: "Foil",
    1088: "Metal", 1280: "Grass", 1296: "Sand", 1312: "Fabric", 1328: "Snow",
    1344: "Mud", 1360: "Ground", 1536: "Ice", 1552: "Glacier", 1792: "Air",
    2048: "Water",
}

SHAPE_FROM_ENUM = {0: "Ball", 1: "Block", 2: "Cylinder"}

# Classes that carry real geometry we can render from primitive data.
RENDERABLE_CLASSES = {
    "Part", "Platform", "Seat", "VehicleSeat", "SpawnLocation", "FlagStand",
    "WedgePart", "CornerWedgePart", "TrussPart", "SkateboardPlatform",
}
# Classes we know about but do not draw yet (reported, never faked).
KNOWN_UNRENDERED = {
    "UnionOperation", "NegateOperation", "MeshPart", "Terrain", "SpecialMesh",
    "PartOperation", "IntersectOperation", "Handles", "ArcHandles", "SelectionBox",
}

# Services that never contribute world geometry. Everything else in the file is
# shown, because the place's Lua is not executed here: maps that a place keeps in
# ServerStorage/ReplicatedStorage and clones into the Workspace at runtime would
# otherwise be invisible. The client labels which container each part came from.
EXCLUDED_SERVICES = {
    "Players", "StarterGui", "StarterPack", "StarterPlayer", "StarterCharacterScripts",
    "StarterPlayerScripts", "Teams", "Debris", "Selection", "SoundService", "Chat",
    "ContentProvider", "InsertService", "LocalizationService", "TestService",
    "PluginGuiService", "JointsService", "FriendService", "Mouse", "LoadLibrary",
    "Status", "Version", "Visit", "ControllerService", "ScriptInformationProvider",
    "TimerService", "CookiesService", "RenderHooksService", "AdService",
    "GeometryService", "Geometry",
}

FACES = {"Front": 0, "Bottom": 1, "Left": 2, "Back": 3, "Top": 4, "Right": 5}

_PALETTE_CACHE: dict | None = None


def brickcolor_palette() -> dict:
    """The historical BrickColor table (number -> rgb), used because 2015 place
    files store `BrickColor` palette indices rather than explicit Color3 values."""
    global _PALETTE_CACHE
    if _PALETTE_CACHE is None:
        p = config.WEB / "static" / "data" / "brickcolor.json"
        data = json.loads(p.read_text())
        _PALETTE_CACHE = {int(k): v["rgb"] for k, v in data["colors"].items()}
        _PALETTE_CACHE_NAMES = {int(k): v["name"] for k, v in data["colors"].items()}
    return _PALETTE_CACHE


def _brickcolor_names() -> dict:
    p = config.WEB / "static" / "data" / "brickcolor.json"
    data = json.loads(p.read_text())
    return {int(k): v["name"] for k, v in data["colors"].items()}


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _vec3(v, default=(0.0, 0.0, 0.0)):
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(
            isinstance(x, (int, float)) for x in v):
        return (float(v[0]), float(v[1]), float(v[2]))
    return default


def _cframe(props: dict):
    cf = props.get("CFrame")
    if isinstance(cf, dict) and "pos" in cf:
        pos = _vec3(cf.get("pos"))
        rot = cf.get("rot") if isinstance(cf.get("rot"), (list, tuple)) else None
        if rot and len(rot) == 9:
            return pos, tuple(float(x) for x in rot)
        return pos, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    pos = _vec3(props.get("Position"))
    return pos, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _part_color(props: dict, palette: dict):
    c3 = props.get("Color3uint8")
    if isinstance(c3, (list, tuple)) and len(c3) == 3:
        return (int(c3[0]) & 0xFF, int(c3[1]) & 0xFF, int(c3[2]) & 0xFF)
    bc = props.get("BrickColor")
    try:
        n = int(bc)
    except (TypeError, ValueError):
        n = 194                       # Medium stone grey (Roblox default)
    return tuple(palette.get(n, (163, 162, 165)))


def _shape_of(cls: str, props: dict) -> str:
    if cls == "WedgePart":
        return "Wedge"
    if cls == "CornerWedgePart":
        return "CornerWedge"
    if cls == "TrussPart":
        return "Truss"
    if cls in ("Seat", "VehicleSeat"):
        return "Block"
    sh = props.get("shape", props.get("Shape"))
    if isinstance(sh, str) and sh in ("Ball", "Block", "Cylinder"):
        return sh
    try:
        return SHAPE_FROM_ENUM.get(int(sh), "Block")
    except (TypeError, ValueError):
        return "Block"


def _lighting(props: dict) -> dict:
    def c3(v, default):
        if isinstance(v, (list, tuple)) and len(v) == 3 and all(
                isinstance(x, (int, float)) for x in v):
            vals = [float(x) for x in v]
            # Color3 may be serialized as 0-1 floats or 0-255 ints
            if max(vals) <= 1.0:
                vals = [x * 255.0 for x in vals]
            return [int(round(x)) for x in vals]
        return default
    return {
        "ambient": c3(props.get("Ambient"), [0, 0, 0]),
        "outdoor_ambient": c3(props.get("OutdoorAmbient"), [128, 128, 128]),
        "brightness": _num(props.get("Brightness"), 1.0),
        "clock_time": _num(props.get("TimeOfDay" if "TimeOfDay" in props else "ClockTime"), 14.0)
        if not isinstance(props.get("TimeOfDay"), str) else 14.0,
        "time_of_day": props.get("TimeOfDay") if isinstance(props.get("TimeOfDay"), str) else None,
        "fog_color": c3(props.get("FogColor"), [192, 192, 192]),
        "fog_start": _num(props.get("FogStart"), 0.0),
        "fog_end": _num(props.get("FogEnd"), 100000.0),
        "global_shadows": bool(props.get("GlobalShadows", False)),
        "geographic_latitude": _num(props.get("GeographicLatitude"), 41.733),
        "color_shift_top": c3(props.get("ColorShift_Top"), [0, 0, 0]),
        "color_shift_bottom": c3(props.get("ColorShift_Bottom"), [0, 0, 0]),
        "environment_diffuse_scale": _num(props.get("EnvironmentDiffuseScale"), 0.0),
    }


def _service_by_class(instances: dict, class_name: str):
    for inst in instances.values():
        if inst.class_name == class_name and inst.properties.get("__service__"):
            return inst
    for inst in instances.values():
        if inst.class_name == class_name:
            return inst
    return None


def _asset_status(con, asset_id: int) -> str:
    if con is None:
        return "UNKNOWN"
    row = con.execute("SELECT status FROM assets WHERE historical_asset_id = ?",
                      (asset_id,)).fetchone()
    if not row:
        return "UNTRACKED"
    return row["status"]


def _extract_asset_id(v) -> int | None:
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        import re
        m = re.search(r"(\d{3,})", v)
        if m:
            return int(m.group(1))
    return None


def build_geometry(report: dict, *, game_id: int | None = None, db_path: Path | None = None) -> dict:
    """Convert an importer report into the client's geometry payload."""
    tree = report["tree"] if "tree" in report else report
    meta_in = report.get("meta", {})
    instances = tree["instances"]
    palette = brickcolor_palette()

    rot_index: dict[tuple, int] = {}
    rots: list[list[float]] = []
    colors: dict[tuple, int] = {}
    color_list: list[list[int]] = []
    mats: dict[int, int] = {}
    mat_list: list[str] = []
    class_index: dict[str, int] = {}
    class_list: list[str] = []

    cls_arr: list[int] = []
    container_arr: list[int] = []
    container_names: list[str] = []
    container_index: dict[str, int] = {}
    pos: list[float] = []
    size: list[float] = []
    rot: list[int] = []
    col: list[int] = []
    alpha: list[int] = []
    refl: list[int] = []
    mat: list[int] = []
    shape: list[int] = []
    flags: list[int] = []
    parent: list[int] = []          # index of parent part geometry (-1 = root of chain)
    names: list[str] = []

    SHAPES = ["Block", "Ball", "Cylinder", "Wedge", "CornerWedge", "Truss"]
    shape_index = {s: i for i, s in enumerate(SHAPES)}

    spawns: list[list[float]] = []
    spawn_rot: list[int] = []
    surf: list[int] = []
    decor: list[dict] = []
    unsupported: dict[str, int] = {}

    # Map instance referent -> index in our geometry arrays (for decor parenting).
    ref_to_geo: dict = {}

    def add_part(inst, parent_geo: int, container: str):
        props = inst.properties
        p, r = _cframe(props)
        s = _vec3(props.get("size")) or _vec3(props.get("Size"), (1.0, 1.0, 1.0))
        if s == (0.0, 0.0, 0.0):
            s = (1.0, 1.0, 1.0)
        key = tuple(round(v, 4) for v in r)
        if key not in rot_index:
            rot_index[key] = len(rots)
            rots.append([round(v, 5) for v in r])
        ckey = _part_color(props, palette)
        if ckey not in colors:
            colors[ckey] = len(color_list)
            color_list.append(list(ckey))
        mtok = props.get("Material")
        try:
            mtok = int(mtok)
        except (TypeError, ValueError):
            mtok = 256
        if mtok not in mats:
            mats[mtok] = len(mat_list)
            mat_list.append(MATERIAL_NAMES.get(mtok, f"Material{mtok}"))
        cls = inst.class_name
        if cls not in class_index:
            class_index[cls] = len(class_list)
            class_list.append(cls)
        f = 0
        if props.get("CanCollide", True):
            f |= 1
        if props.get("Anchored", False):
            f |= 2
        trans = _num(props.get("Transparency"), 0.0)
        if trans >= 0.999:
            f |= 4                                   # fully invisible
        elif trans > 0.02:
            f |= 8                                   # partially transparent

        idx = len(pos) // 3
        cls_arr.append(class_index[cls])
        if container not in container_index:
            container_index[container] = len(container_names)
            container_names.append(container)
        container_arr.append(container_index[container])
        pos.extend([round(p[0], 3), round(p[1], 3), round(p[2], 3)])
        size.extend([round(s[0], 3), round(s[1], 3), round(s[2], 3)])
        rot.append(rot_index[key])
        col.append(colors[ckey])
        alpha.append(max(0, min(255, int(round((1.0 - trans) * 255)))))
        refl.append(max(0, min(255, int(round(_num(props.get("Reflectance"), 0.0) * 255)))))
        mat.append(mats[mtok])
        shape.append(shape_index[_shape_of(cls, props)])
        flags.append(f)
        parent.append(parent_geo)
        names.append(str(inst.name)[:64])
        ref_to_geo[inst.referent] = idx

        if cls == "SpawnLocation":
            spawns.append([round(p[0], 2), round(p[1], 2), round(p[2], 2)])
            spawn_rot.append(rot_index[key])
        # Surface types for all six faces, packed 4 bits each (see notebook-style
        # note above); the client draws the 2015 stud/inlet pattern from these.
        packed = 0
        for shift, key in ((0, "TopSurface"), (4, "BottomSurface"), (8, "LeftSurface"),
                           (12, "RightSurface"), (16, "FrontSurface"), (20, "BackSurface")):
            try:
                val = int(props.get(key, 0)) & 0xF
            except (TypeError, ValueError):
                val = 0
            packed |= val << shift
        surf.append(packed)
        return idx

    def walk(inst, parent_geo: int, container: str):
        if inst.class_name in RENDERABLE_CLASSES:
            parent_geo = add_part(inst, parent_geo, container)
        elif inst.class_name in KNOWN_UNRENDERED:
            unsupported[inst.class_name] = unsupported.get(inst.class_name, 0) + 1
        if inst.class_name in ("Decal", "Texture"):
            tex = _extract_asset_id(inst.properties.get("Texture") or inst.properties.get("TextureID"))
            face = FACES.get(str(inst.properties.get("Face")), 4)
            if tex:
                decor.append({"ref": inst.parent_ref, "kind": inst.class_name,
                              "asset": tex, "face": face,
                              "alpha": _num(inst.properties.get("Transparency"), 0.0)})
        for c in inst.children:
            walk(c, parent_geo, container)

    for root in tree["roots"]:
        if root.class_name in EXCLUDED_SERVICES:
            continue
        for c in root.children:
            walk(c, -1, root.class_name)

    # Attach decor to the geometry index of its parent part.
    decor_out = []
    for d in decor:
        gi = ref_to_geo.get(d["ref"])
        if gi is None:
            continue
        decor_out.append([gi, d["face"], d["asset"], int(round((1 - d["alpha"]) * 255)),
                          1 if d["kind"] == "Texture" else 0])

    # Lighting / sky
    lighting_inst = _service_by_class(instances, "Lighting")
    lighting = _lighting(lighting_inst.properties if lighting_inst else {})
    if lighting.get("time_of_day") is None:
        lighting["time_of_day"] = None
    sky_inst = None
    for inst in instances.values():
        if inst.class_name == "Sky":
            sky_inst = inst
            break
    sky = None
    if sky_inst:
        sky = {k: str(sky_inst.properties.get(k, "")) for k in
               ("SkyboxBk", "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp",
                "StarCount", "SunAnglesImage", "MoonAnglesImage")}
        sky = {k: v for k, v in sky.items() if v}

    # Asset recovery status for referenced meshes/textures/sounds
    con = None
    if db_path:
        import sqlite3
        try:
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
        except Exception:
            con = None
    asset_refs: dict[int, dict] = {}
    for inst in instances.values():
        for key in ("MeshId", "Texture", "TextureID", "SoundId", "Graphic", "Image"):
            v = inst.properties.get(key)
            aid = _extract_asset_id(v)
            if not aid:
                continue
            if aid not in asset_refs:
                asset_refs[aid] = {"id": aid, "kind": key,
                                   "status": _asset_status(con, aid),
                                   "uses": 0}
            asset_refs[aid]["uses"] += 1
    for d in decor_out:
        ref = asset_refs.get(d[2])
        if ref is None:
            asset_refs[d[2]] = {"id": d[2], "kind": "Texture", "status": _asset_status(con, d[2]),
                                "uses": 1}
    if con is not None:
        con.close()

    scripts = tree.get("scripts", [])
    lighting_ok = bool(lighting_inst)

    stats = {
        "instance_count": len(instances),
        "part_count": len(pos) // 3,
        "rendered_parts": sum(1 for f in flags if not (f & 4)),
        "invisible_parts": sum(1 for f in flags if f & 4),
        "collidable_parts": sum(1 for f in flags if f & 1),
        "unanchored_parts": sum(1 for f in flags if not (f & 2)),
        "spawn_count": len(spawns),
        "decor_count": len(decor_out),
        "script_count": len(scripts),
        "assets_referenced": len(asset_refs),
        "assets_recovered": sum(1 for a in asset_refs.values() if a["status"] == "RECOVERED"),
        "assets_missing": sum(1 for a in asset_refs.values() if a["status"] != "RECOVERED"),
        "lighting_source": "place file" if lighting_ok else "defaults (no Lighting service)",
        "parts_by_container": {
            name: container_arr.count(i) for i, name in enumerate(container_names)
        },
        "parts_outside_workspace": sum(
            c for i, name in enumerate(container_names) if name != "Workspace"
            for c in [container_arr.count(i)]
        ),
    }

    return {
        "meta": {
            "game_id": game_id,
            "place_sha256": meta_in.get("sha256"),
            "source_path": meta_in.get("source_path"),
            "format": meta_in.get("format", tree.get("format")),
            "target_build": config.TARGET_WINDOWS_PLAYER_GUID,
            "exporter": "bloxen/placeview/geometry.py",
        },
        "stats": stats,
        "classes": class_list,
        "containers": container_names,
        "shapes": SHAPES,
        "materials": mat_list,
        "colors": color_list,
        "rots": rots,
        "parts": {
            "cls": cls_arr,
            "pos": pos, "size": size, "rot": rot, "col": col, "alpha": alpha,
            "refl": refl, "mat": mat, "shape": shape, "flags": flags, "parent": parent,
            "surf": surf, "container": container_arr, "name": names,
        },
        "spawns": {"pos": spawns, "rot": spawn_rot},
        "decor": decor_out,
        "assets": sorted(asset_refs.values(), key=lambda a: -a["uses"]),
        "lighting": lighting,
        "sky": sky,
        "unsupported": {
            "not_rendered_classes": unsupported,
            "csg_unions": unsupported.get("UnionOperation", 0),
            "mesh_parts": unsupported.get("MeshPart", 0),
            "terrain": "not rendered (voxel grid decoding not implemented)",
            "scripts": "inventoried, never executed (see docs/GAMES.md)",
        },
    }


# Bump when the payload shape or decoding changes so stale caches are not reused.
EXPORTER_VERSION = "1"


def geometry_cache_path(sha256: str) -> Path:
    return config.DATA / "place_geometry" / f"v{EXPORTER_VERSION}-{sha256[:32]}.json"


def load_or_build_geometry(report: dict, *, game_id: int, db_path: Path | None = None) -> dict:
    """Build geometry once per place content hash and cache it on disk."""
    sha = report.get("meta", {}).get("sha256") or report.get("sha256") or "unknown"
    cache = geometry_cache_path(sha)
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            data["meta"]["game_id"] = game_id
            data["meta"]["cached"] = True
            return data
        except Exception:
            pass
    data = build_geometry(report, game_id=game_id, db_path=db_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    data["meta"]["cached"] = False
    return data

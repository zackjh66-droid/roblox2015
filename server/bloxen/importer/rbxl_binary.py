"""RBXL/RBXM binary place/model parser.

Produces a DataModel tree of Instance objects with properties as inert data.
Scripts are captured as inert strings; NOTHING is executed during intake.

Provenance: format per public reverse-engineering (rojo-rbx/rbx-dom,
Dekkonot/rbx-binary-format). See research/sources/formats/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .bitstream import Reader, decompress_chunk

MAGIC = b"<roblox!\x89\xff\r\n\x1a\n"

# Property type ids (public format)
TYPE_STRING = 0x01
TYPE_BOOL = 0x02
TYPE_INT32 = 0x03
TYPE_FLOAT32 = 0x04
TYPE_FLOAT64 = 0x05
TYPE_UDIM = 0x06
TYPE_UDIM2 = 0x07
TYPE_RAY = 0x08
TYPE_FACES = 0x09
TYPE_AXES = 0x0A
TYPE_BRICKCOLOR = 0x0B
TYPE_COLOR3 = 0x0C
TYPE_VECTOR2 = 0x0D
TYPE_VECTOR3 = 0x0E
TYPE_VECTOR2INT16 = 0x0F
TYPE_CFRAME = 0x10
TYPE_QUATERNION = 0x11
TYPE_ENUM = 0x12
TYPE_REF = 0x13
TYPE_VECTOR3INT16 = 0x14
TYPE_NUMBERSEQ = 0x15
TYPE_COLORSEQ = 0x16
TYPE_NUMBERRANGE = 0x17
TYPE_RECT = 0x18
TYPE_PHYSICALPROPS = 0x19
TYPE_COLOR3UINT8 = 0x1A
TYPE_INT64 = 0x1B
TYPE_SHAREDSTRING = 0x1C
TYPE_BYTECODE = 0x1D

CFRAME_ROT_MATRIX = [  # 12 stored rotation matrices per axis id (Roblox legacy quirk)
    (1, 0, 0, 0, 1, 0, 0, 0, 1),
]

SCRIPT_CLASSES = {"Script", "LocalScript", "ModuleScript"}


@dataclass
class Instance:
    class_name: str
    referent: int
    properties: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent_ref: int | None = None

    @property
    def name(self) -> str:
        return self.properties.get("Name", self.class_name)

    def descendant_class_counts(self, counts: dict | None = None) -> dict:
        counts = counts if counts is not None else {}
        counts[self.class_name] = counts.get(self.class_name, 0) + 1
        for c in self.children:
            c.descendant_class_counts(counts)
        return counts

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


class ParseError(Exception):
    pass


def _parse_property_values(r: Reader, type_id: int, count: int, shared: list[bytes]):
    t = type_id
    if t == TYPE_STRING or t == TYPE_BYTECODE:
        vals = [r.string() for _ in range(count)]
        return [v.decode("utf-8", "replace") if isinstance(v, bytes) else v for v in vals]
    if t == TYPE_BOOL:
        return [bool(b) for b in r.read(count)]
    if t == TYPE_INT32:
        return r.interleaved_i32(count)
    if t == TYPE_FLOAT32:
        return r.interleaved_rbx_float32(count)
    if t == TYPE_FLOAT64:
        return [r.f64() for _ in range(count)]
    if t == TYPE_UDIM:
        return [(r.interleaved_i32(count), r.interleaved_i32(count))]  # scale, offset arrays
    if t == TYPE_UDIM2:
        sx = r.interleaved_i32(count)
        ox = r.interleaved_i32(count)
        sy = r.interleaved_i32(count)
        oy = r.interleaved_i32(count)
        return [((sx[i], ox[i]), (sy[i], oy[i])) for i in range(count)]
    if t == TYPE_RAY:
        return [{"origin": (r.f32(), r.f32(), r.f32()), "direction": (r.f32(), r.f32(), r.f32())}
                for _ in range(count)]
    if t == TYPE_FACES or t == TYPE_AXES:
        return [r.u32() for _ in range(count)]
    if t == TYPE_BRICKCOLOR:
        return r.interleaved_uint(count, 4)
    if t == TYPE_COLOR3:
        return [r.interleaved_rbx_float32(count) for _ in range(3)]  # r,g,b arrays
    if t == TYPE_VECTOR2:
        xs = r.interleaved_rbx_float32(count)
        ys = r.interleaved_rbx_float32(count)
        return [(xs[i], ys[i]) for i in range(count)]
    if t == TYPE_VECTOR3:
        xs = r.interleaved_rbx_float32(count)
        ys = r.interleaved_rbx_float32(count)
        zs = r.interleaved_rbx_float32(count)
        return [(xs[i], ys[i], zs[i]) for i in range(count)]
    if t == TYPE_VECTOR2INT16 or t == TYPE_VECTOR3INT16:
        size = 4 if t == TYPE_VECTOR2INT16 else 6
        raw = [r.read(size) for _ in range(count)]
        return raw
    if t == TYPE_CFRAME:
        out = []
        pos = []
        for _ in range(3):
            pos.append(r.interleaved_rbx_float32(count))
        for i in range(count):
            rot_id = r.u8()
            rot = (0.0,) * 9 if rot_id > 11 else CFRAME_ROT_MATRIX[0]
            # rotation matrix id semantics: store id + placeholder matrix
            out.append({"rot_id": rot_id, "pos": (pos[0][i], pos[1][i], pos[2][i])})
        return out
    if t == TYPE_QUATERNION:
        return [r.f32() * 4 for _ in range(count)]
    if t == TYPE_ENUM or t == TYPE_INT64:
        return r.interleaved_uint(count, 4)
    if t == TYPE_REF:
        return r.referents(count)
    if t == TYPE_NUMBERSEQ:
        out = []
        for _ in range(count):
            n = r.u32()
            keypoints = [(r.f32(), r.f32(), r.f32()) for _ in range(n)]
            out.append(keypoints)
        return out
    if t == TYPE_COLORSEQ:
        out = []
        for _ in range(count):
            n = r.u32()
            kps = []
            for _k in range(n):
                tstamp = r.f32()
                c = (r.f32(), r.f32(), r.f32())
                r.f32()  # envelope/unused
                kps.append((tstamp, c))
            out.append(kps)
        return out
    if t == TYPE_NUMBERRANGE:
        return [(r.f32(), r.f32()) for _ in range(count)]
    if t == TYPE_RECT:
        return [((r.f32(), r.f32()), (r.f32(), r.f32())) for _ in range(count)]
    if t == TYPE_PHYSICALPROPS:
        out = []
        for _ in range(count):
            custom = r.u8()
            if custom:
                out.append({"custom": True, "density": r.f32(), "friction": r.f32(),
                            "elasticity": r.f32(), "frictionWeight": r.f32(),
                            "elasticityWeight": r.f32()})
            else:
                out.append({"custom": False})
        return out
    if t == TYPE_COLOR3UINT8:
        return [(r.u8(), r.u8(), r.u8()) for _ in range(count)]
    if t == TYPE_SHAREDSTRING:
        idx = r.interleaved_uint(count, 4)
        return [shared[i] if i < len(shared) else b"" for i in idx]
    raise ParseError(f"unknown property type 0x{t:02x}")


def parse_binary(data: bytes) -> dict:
    """Parse a binary RBXL/RBXM file. Returns a report dict with a rooted tree."""
    if not data.startswith(MAGIC):
        raise ParseError("not a Roblox binary file (bad magic)")
    r = Reader(data)
    r.read(len(MAGIC))
    version = r.u16()
    class_count = r.u32()
    instance_count = r.u32()
    r.u64()  # reserved

    class_names: dict[int, str] = {}
    class_instance_ids: dict[int, list[int]] = {}
    instances: dict[int, Instance] = {}
    shared_strings: list[bytes] = []
    parent_pairs: list[tuple[int, int]] = []   # (child_ref, parent_ref)

    while True:
        cname = r.read(4).decode("ascii", "replace")
        comp_len = r.u32()
        uncomp_len = r.u32()
        r.u32()  # reserved
        payload = r.read(comp_len if comp_len else uncomp_len)
        chunk = decompress_chunk(payload, uncomp_len, comp_len)
        cr = Reader(chunk)

        if cname == "META":
            pass  # metadata key/values; ignored for tree building
        elif cname == "SSTR":
            n = cr.u32()
            cr.u32()  # version
            shared_strings = [cr.string() for _ in range(n)]
        elif cname == "INST":
            class_id = cr.u32()
            class_name = cr.string().decode("utf-8", "replace")
            obj_format = cr.u8()
            count = cr.u32()
            refs = cr.referents(count)
            class_names[class_id] = class_name
            class_instance_ids.setdefault(class_id, []).extend(refs)
            is_service = False
            if obj_format == 1:
                flags = cr.read(count)
                is_service = any(flags)
            for ref in refs:
                inst = Instance(class_name=class_name, referent=ref)
                inst.properties["__service__"] = is_service and obj_format == 1
                instances[ref] = inst
        elif cname == "PROP":
            class_id = cr.u32()
            prop_name = cr.string().decode("utf-8", "replace")
            type_id = cr.u8()
            refs = class_instance_ids.get(class_id, [])
            try:
                values = _parse_property_values(cr, type_id, len(refs), shared_strings)
            except Exception as e:
                values = [f"<unparsed {type_id:#x}: {e}>"] * len(refs)
            for ref, val in zip(refs, values):
                if ref in instances:
                    instances[ref].properties[prop_name] = val
        elif cname == "PRNT":
            cr.u8()  # version
            count = cr.u32()
            children = cr.referents(count)
            parents = cr.referents(count)
            parent_pairs = list(zip(children, parents))
        elif cname.rstrip("\x00") == "END":
            break

    # build tree
    roots: list[Instance] = []
    for child_ref, parent_ref in parent_pairs:
        child = instances.get(child_ref)
        if child is None:
            continue
        child.parent_ref = parent_ref
        parent = instances.get(parent_ref)
        if parent is not None:
            parent.children.append(child)
        else:
            roots.append(child)
    for ref, inst in instances.items():
        if inst.parent_ref is None and inst not in roots:
            roots.append(inst)

    class_counts: dict[str, int] = {}
    for inst in instances.values():
        class_counts[inst.class_name] = class_counts.get(inst.class_name, 0) + 1

    # inert script inventory + external asset ids
    scripts = []
    asset_ids = set()
    for inst in instances.values():
        if inst.class_name in SCRIPT_CLASSES:
            src = inst.properties.get("Source", b"")
            if isinstance(src, bytes):
                src = src.decode("utf-8", "replace")
            scripts.append({"name": inst.name, "class": inst.class_name,
                            "bytes": len(src), "sha256": _sha(src)})
        for key in ("MeshId", "Texture", "TextureID", "PantsTemplate", "ShirtTemplate",
                    "Graphic", "SoundId", "Thumbnail", "AnimationId", "Image", "SkyboxBk",
                    "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp"):
            v = inst.properties.get(key)
            if isinstance(v, bytes):
                v = v.decode("utf-8", "replace")
            if isinstance(v, str):
                for tok in v.replace("=", "&").split("&"):
                    tok = tok.strip()
                    if tok.startswith("rbxassetid://") or tok.startswith("http"):
                        asset_ids.add(tok)
                    elif tok.isdigit() and key in ("MeshId", "Texture", "TextureID", "SoundId",
                                                  "PantsTemplate", "ShirtTemplate", "AnimationId"):
                        asset_ids.add(int(tok))

    return {
        "format": "rbxl-binary",
        "format_version": version,
        "class_count_header": class_count,
        "instance_count_header": instance_count,
        "class_counts": dict(sorted(class_counts.items(), key=lambda kv: -kv[1])),
        "instances": instances,
        "roots": roots,
        "scripts": scripts,
        "external_asset_ids": sorted(asset_ids, key=str),
    }


def _sha(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()

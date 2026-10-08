"""RBXLX/RBXMX XML place/model parser (schema: research/sources/formats/roblox.xsd).

Produces the same report shape as the binary parser. Scripts stay inert.

Property elements are typed by tag and hold either text (scalars) or child elements
(structured datatypes), per the official schema:
    <Vector3 name="size"><X>4</X><Y>1.2</Y><Z>2</Z></Vector3>
    <CoordinateFrame name="CFrame"><X>..</X>..<R22>1</R22></CoordinateFrame>
    <Color3uint8 name="Color3uint8">4278190335</Color3uint8>
    <bool name="Anchored">true</bool>
"""
from __future__ import annotations

import base64
import hashlib
import re
import xml.etree.ElementTree as ET

from .rbxl_binary import SCRIPT_CLASSES, Instance

ASSET_KEYS = {"MeshId", "Texture", "TextureID", "PantsTemplate", "ShirtTemplate",
              "Graphic", "SoundId", "Thumbnail", "AnimationId", "Image"}

_INT_TAGS = {"int", "int64", "token", "enum", "BrickColor", "Color3uint8"}
_FLOAT_TAGS = {"float", "double", "time"}
_TEXT_TAGS = {"string", "Content", "ProtectedString", "SharedString", "BinaryString",
              "url", "mimeType"}


def _nums(el: ET.Element, tags: tuple[str, ...], default: float = 0.0) -> tuple:
    out = []
    for t in tags:
        child = el.find(t)
        if child is None or child.text is None:
            out.append(default)
            continue
        try:
            out.append(float(child.text.strip()))
        except ValueError:
            out.append(default)
    return tuple(out)


def _decode_value(tag: str, el: ET.Element):
    """Decode one <Properties> child element into a Python value."""
    text = (el.text or "").strip()
    if tag in _FLOAT_TAGS:
        try:
            return float(text)
        except ValueError:
            return 0.0
    if tag in ("Color3", "Color3uint8"):
        # packed 0xRRGGBB integer, or explicit <R>/<G>/<B> children
        if el.find("R") is not None:
            return _nums(el, ("R", "G", "B"))
        try:
            packed = int(float(text))
        except ValueError:
            return (0, 0, 0)
        return ((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)
    if tag in _INT_TAGS:
        try:
            return int(float(text))
        except ValueError:
            return text
    if tag == "bool":
        return text.lower() == "true"
    if tag in _TEXT_TAGS:
        return text
    if tag == "binary":
        try:
            return base64.b64decode(text or "")
        except Exception:
            return b""
    if tag == "Ref":
        return None if text in ("", "null", "nil") else text
    if tag == "Vector3":
        return _nums(el, ("X", "Y", "Z"))
    if tag == "Vector2":
        return _nums(el, ("X", "Y"))
    if tag == "Vector3int16":
        return tuple(int(float((el.find(t).text or "0").strip())) for t in ("X", "Y", "Z"))
    if tag == "CoordinateFrame":
        x, y, z = _nums(el, ("X", "Y", "Z"))
        rot = _nums(el, ("R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"),
                    default=0.0)
        if rot == (0.0,) * 9:
            rot = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        return {"pos": (x, y, z), "rot": rot}
    if tag == "UDim":
        return (_nums(el, ("S",)), _nums(el, ("O",)))
    if tag == "UDim2":
        return {c.tag: (float(c.findtext("XS") or 0), float(c.findtext("XO") or 0),
                        float(c.findtext("YS") or 0), float(c.findtext("YO") or 0))
                for c in el}
    if tag == "Ray":
        return {"origin": _nums(el, ("originX", "originY", "originZ")),
                "direction": _nums(el, ("dirX", "dirY", "dirZ"))}
    if tag in ("NumberSequence", "ColorSequence"):
        return text
    if tag == "NumberRange":
        return (float(el.findtext("min") or 0), float(el.findtext("max") or 0))
    if tag == "Rect":
        return _nums(el, ("minX", "minY", "maxX", "maxY"))
    if tag == "PhysicalProperties":
        return {"custom": True, **{c.tag: float(c.text or 0) for c in el}}
    # Unknown/container: keep text, else nested scalar children
    if text:
        return text
    if len(el):
        return {c.tag: (c.text or "").strip() for c in el}
    return text


def parse_xml(data: bytes) -> dict:
    text = data.decode("utf-8", "replace")
    if "<roblox" not in text[:200].lower():
        raise ValueError("not a Roblox XML file")
    root = ET.fromstring(data)

    instances: dict[str, Instance] = {}
    order: list[str] = []
    parent_map: list[tuple[str, str]] = []  # (child, parent)

    def handle_item(item: ET.Element, parent_ref: str | None):
        ref = item.get("referent") or f"anon-{len(order)}"
        cls = item.get("class", "Instance")
        inst = Instance(class_name=cls, referent=ref)
        for prop in item.findall("Properties/*"):
            name = prop.get("name")
            if not name:
                continue
            inst.properties[name] = _decode_value(prop.tag, prop)
        instances[ref] = inst
        order.append(ref)
        if parent_ref:
            parent_map.append((ref, parent_ref))
        for child in item.findall("Item"):
            handle_item(child, ref)

    for item in root.findall("Item"):
        handle_item(item, None)

    for child_ref, parent_ref in parent_map:
        child = instances.get(child_ref)
        parent = instances.get(parent_ref)
        if child and parent:
            child.parent_ref = parent_ref
            parent.children.append(child)

    roots = [instances[ref] for ref in order if instances[ref].parent_ref is None]

    class_counts: dict[str, int] = {}
    for inst in instances.values():
        class_counts[inst.class_name] = class_counts.get(inst.class_name, 0) + 1

    scripts = []
    asset_ids = set()
    for inst in instances.values():
        if inst.class_name in SCRIPT_CLASSES:
            src = inst.properties.get("Source", "")
            if isinstance(src, bytes):
                src = src.decode("utf-8", "replace")
            scripts.append({"name": inst.name, "class": inst.class_name,
                            "bytes": len(src),
                            "sha256": hashlib.sha256(src.encode("utf-8", "replace")).hexdigest()})
        for key in ASSET_KEYS:
            v = inst.properties.get(key)
            if isinstance(v, str) and v:
                m = re.findall(r"(?:rbxassetid://|id=)(\d+)", v)
                for mid in m:
                    asset_ids.add(int(mid))
                if v.isdigit():
                    asset_ids.add(int(v))

    return {
        "format": "rbxl-xml",
        "format_version": root.get("version"),
        "class_counts": dict(sorted(class_counts.items(), key=lambda kv: -kv[1])),
        "instances": instances,
        "roots": roots,
        "scripts": scripts,
        "external_asset_ids": sorted(asset_ids),
    }

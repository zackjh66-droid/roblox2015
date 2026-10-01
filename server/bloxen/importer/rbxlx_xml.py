"""RBXLX/RBXMX XML place/model parser (schema: research/sources/formats/roblox.xsd).

Produces the same report shape as the binary parser. Scripts stay inert.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from .rbxl_binary import SCRIPT_CLASSES, Instance

ASSET_KEYS = {"MeshId", "Texture", "TextureID", "PantsTemplate", "ShirtTemplate",
              "Graphic", "SoundId", "Thumbnail", "AnimationId", "Image"}


def _decode_value(tag: str, text: str | None):
    text = text or ""
    if tag == "string":
        return text
    if tag == "bool":
        return text.strip().lower() == "true"
    if tag in ("int", "int64", "token", "enum"):
        try:
            return int(text.strip())
        except ValueError:
            return text
    if tag in ("float", "double"):
        try:
            return float(text.strip())
        except ValueError:
            return text
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
            inst.properties[name] = _decode_value(prop.tag, prop.text)
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

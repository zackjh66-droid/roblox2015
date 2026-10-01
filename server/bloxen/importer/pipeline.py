"""Place intake pipeline.

    candidate -> quarantine -> hash -> parse -> DataModel -> report

Rules:
- scripts are inventoried as inert data; never executed at intake
- external asset IDs enumerated for recovery tracking
- compatibility report compares the place's class/property usage against the
  target build API dump (version-0d46087630eb46cd)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import config
from . import rbxl_binary, rbxlx_xml


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_api_dump() -> dict:
    if config.API_DUMP_PATH.exists():
        return json.loads(config.API_DUMP_PATH.read_text())
    return {}


def compatibility_report(report: dict, api_dump: dict) -> dict:
    known_classes = {c["Name"] for c in api_dump.get("Classes", [])}
    known_props: dict[str, set[str]] = {}
    for c in api_dump.get("Classes", []):
        known_props[c["Name"]] = {m["Name"] for m in c.get("Members", [])
                                  if m["MemberType"] == "Property"}
    used = report.get("class_counts", {})
    unknown_classes = sorted(c for c in used if c not in known_classes)

    prop_usage: dict[str, list[str]] = {}
    always_known = {"Name", "Parent", "Archivable", "ClassName", "RobloxLocked"}
    for inst in report.get("instances", {}).values():
        for pname in inst.properties:
            if pname.startswith("__") or pname in always_known:
                continue
            allowed = known_props.get(inst.class_name, set())
            if allowed and pname not in allowed:
                prop_usage.setdefault(inst.class_name, [])
                if pname not in prop_usage[inst.class_name]:
                    prop_usage[inst.class_name].append(pname)

    services_present = sorted(
        {i.name for i in report.get("instances", {}).values() if i.class_name.endswith("Service")}
        | {i.name for i in report.get("roots", [])}
    )
    return {
        "target_build": config.TARGET_WINDOWS_PLAYER_GUID,
        "classes_used": len(used),
        "unknown_classes_vs_target": unknown_classes,
        "properties_unknown_vs_target": prop_usage,
        "top_level_services": services_present[:40],
        "script_count": len(report.get("scripts", [])),
        "external_asset_count": len(report.get("external_asset_ids", [])),
    }


def import_place(path: Path) -> dict:
    path = Path(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if data.startswith(rbxl_binary.MAGIC):
        report = rbxl_binary.parse_binary(data)
    elif data.lstrip()[:100].lower().startswith(b"<roblox") or b"<roblox" in data[:200].lower():
        report = rbxlx_xml.parse_xml(data)
    else:
        raise ValueError(f"{path}: unrecognized place format")

    api_dump = load_api_dump()
    compat = compatibility_report(report, api_dump)

    # serialize non-tree parts
    out = {
        "source_path": str(path),
        "sha256": digest,
        "format": report["format"],
        "class_counts": report["class_counts"],
        "script_inventory": report["scripts"],
        "external_asset_ids": [str(a) for a in report["external_asset_ids"]],
        "service_report": compat,
        "roots": [r.name for r in report["roots"]],
        "instance_count": len(report["instances"]),
    }
    return {"meta": out, "tree": report}

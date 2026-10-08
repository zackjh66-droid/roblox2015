#!/usr/bin/env python3
"""Import historical place files from public archives into BLOXEN (real files only).

    intake -> quarantine -> SHA-256 -> parse -> DB (games / place_imports / assets)

HONESTY RULES
- a place file is only accepted when it comes from a public archive repository
  and the file itself parses; the SHA-256 of the exact bytes is recorded
- the *era* of a file is inferred from the file itself (binary format version,
  class/property fingerprints, script API usage) and recorded as an inference,
  never as a claimed save date
- creator attribution without sidecar metadata is recorded as UNVERIFIED
- scripts are inventoried as inert data and never executed

Usage:
  PYTHONPATH=server .venv/bin/python tools/import_places.py --discover DIR
  PYTHONPATH=server .venv/bin/python tools/import_places.py --state
  # then import the discovered files you want:
  PYTHONPATH=server .venv/bin/python tools/import_places.py --import ID [--import ID ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from bloxen import config, db                                    # noqa: E402
from bloxen.importer.pipeline import import_place                # noqa: E402

STATE_PATH = config.DATA / "game-archive-catalogue.json"

# Filenames in some archives assert a save date ("Flood Escape (July 8th, 2015...)"). A
# filename is NOT evidence: it is recorded as the archive author's claim, next to the
# SHA-256, and is never used to override in-file evidence.
DATE_CLAIM_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s*(\d{4})|\b(20[01]\d)\b", re.I)


def filename_date_claim(name: str) -> str | None:
    m = DATE_CLAIM_RE.search(name)
    if not m:
        return None
    return m.group(0).strip()


def sidecar_meta(path: Path) -> dict | None:
    """Archive-supplied sidecar metadata (`<file>.meta.json`) if the archive has one.

    The sidecar is the *archive author's* attribution (creator name, badge list). It is
    recorded verbatim as `archive_attributed`, which is stronger than no attribution at
    all but still not a Roblox API confirmation — the honesty ladder treats it as
    ATTRIBUTED, not VERIFIED.
    """
    for cand in (path.with_name(path.name + ".meta.json"),
                 path.with_suffix(".meta.json")):
        if cand.exists():
            try:
                data = json.loads(cand.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            if isinstance(data, dict):
                data["_sidecar_path"] = str(cand)
                return data
    return None
PLACES = config.QUARANTINE / "places"

# Classes/properties that only exist in later client builds. Used for era
# *inference* only (recorded as such) — never as a claimed save date.
ERA_MARKERS = [
    (2013, "FilteringEnabled"),
    (2013, "StreamingEnabled"),
    (2014, "BodyColors"),
    (2015, "R15"),
    (2016, "Animator"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"source_repos": [], "candidates": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


def quick_fingerprint(path: Path) -> dict:
    """Cheap scan: format, class names present, era markers (no full parse)."""
    head = path.read_bytes()[:400_000]
    info = {"bytes": path.stat().st_size, "format": "rbxl-xml" if head.lstrip()[:6] == b"<roblo"
            else "rbxl-binary" if head.startswith(b"<roblox!") else "unknown"}
    classes = set()
    for marker in (b"BodyColors", b"Humanoid", b"FilteringEnabled", b"StreamingEnabled",
                   b"Animator", b"R15", b"MeshPart", b"Terrain", b"UnionOperation",
                   b"Hint", b"NewScript", b"Script", b"Value", b"HopperBin"):
        if marker in head:
            classes.add(marker.decode())
    info["markers"] = sorted(classes)
    era = 2006
    for year, marker in ERA_MARKERS:
        if marker.encode() in head:
            era = max(era, year)
    info["era_inferred_at_least"] = era
    return info


def discover(source_dir: Path, repo: str) -> dict:
    state = load_state()
    if repo and repo not in state["source_repos"]:
        state["source_repos"].append(repo)
    found = 0
    for path in sorted(source_dir.rglob("*.rbxl*")):
        digest = sha256_file(path)
        key = digest[:16]
        if key in state["candidates"]:
            continue
        fp = quick_fingerprint(path)
        state["candidates"][key] = {
            "file": path.name, "sha256": digest, "source_dir": str(source_dir),
            "source_repo": repo, **fp, "status": "candidate", "imported_as": None,
        }
        found += 1
    save_state(state)
    return {"found": found, "total": len(state["candidates"])}


def show_state() -> None:
    state = load_state()
    cands = state["candidates"]
    print(f"sources: {', '.join(state['source_repos']) or '—'}")
    print(f"candidates: {len(cands)}")
    by_era: dict[int, int] = {}
    for c in cands.values():
        by_era[c["era_inferred_at_least"]] = by_era.get(c["era_inferred_at_least"], 0) + 1
    print("era inference (at least):", dict(sorted(by_era.items())))
    print("\nid            era  MB   status     name")
    for key, c in sorted(cands.items(), key=lambda kv: (-kv[1]["era_inferred_at_least"],
                                                        -kv[1]["bytes"])):
        if c["status"] == "imported" and c.get("imported_as"):
            continue
        print(f"{key}  {c['era_inferred_at_least']}  {c['bytes']/1e6:5.1f}  {c['status']:9} {c['file'][:62]}")


ERA_PROPS = ["FilteringEnabled", "StreamingEnabled", "BodyColors", "Animator", "R15",
             "MeshPart", "Terrain", "UnionOperation", "PackageId", "PackageName",
             "CustomPhysicalProperties", "TextureID", "ParticleEmitter"]


def full_era_evidence(tree: dict) -> dict:
    """Era evidence from the *whole* parsed file (not a byte-prefix scan)."""
    classes = set(tree.get("class_counts", {}).keys())
    props = set()
    for inst in list(tree.get("instances", {}).values())[:20000]:
        props.update(inst.properties.keys())
    markers = sorted((classes | props) & set(ERA_PROPS + ["BodyColors", "Animator"]))
    # Property-level markers that only exist after certain builds
    later = [m for m in ("FilteringEnabled", "StreamingEnabled", "R15", "BodyColors")
             if m in markers]
    return {"markers": markers, "post_2013_markers": later,
            "class_count": len(classes), "property_sample": len(props)}


def do_import(keys: list[str], *, force: bool = False) -> None:
    state = load_state()
    con = db.init()
    for key in keys:
        cand = state["candidates"].get(key)
        if not cand:
            print(f"[skip] {key}: unknown candidate id")
            continue
        src = Path(cand["source_dir"]) / cand["file"]
        if not src.exists():
            print(f"[skip] {key}: source file gone ({src})")
            continue
        PLACES.mkdir(parents=True, exist_ok=True)
        dest = PLACES / cand["file"]
        if not dest.exists() or force:
            shutil.copy2(src, dest)
        # carry the archive's own sidecar (attribution/badges) into quarantine so the
        # provenance travels with the file and is not left behind in a /tmp clone
        archive_side = sidecar_meta(src)
        if archive_side:
            carried = {k: v for k, v in archive_side.items() if not k.startswith("_")}
            carried["_carried_from"] = archive_side.get("_sidecar_path")
            (PLACES / (dest.name + ".meta.json")).write_text(
                json.dumps(carried, indent=1), encoding="utf-8")
        digest = sha256_file(dest)
        if digest != cand["sha256"]:
            print(f"[reject] {key}: hash mismatch after copy")
            continue
        res = import_place(dest)
        meta = res["meta"]
        ev = full_era_evidence(res["tree"])
        name = Path(cand["file"]).stem
        era_text = ("post-2013 markers present: " + ", ".join(ev["post_2013_markers"])
                    if ev["post_2013_markers"] else
                    "no post-2013 markers detected in class/property usage")
        claim = filename_date_claim(cand["file"])
        side = sidecar_meta(dest)
        creator = (str(side.get("Creator")).strip() if side and side.get("Creator")
                   else "unverified")
        attribution = (f"Creator (archive sidecar): {creator} — attributed by the archive "
                       f"author, NOT independently verified against Roblox services. "
                       + (f"Sidecar badge list: {len(side.get('Badges', []))} entries. "
                          if side and isinstance(side.get("Badges"), list) else "")
                       if side else
                       "No sidecar metadata in source archive: creator attribution UNVERIFIED. ")
        note = (f"Public archive: {cand['source_repo']} (file: {cand['file']}). "
                + attribution
                + (f"Filename date claim: \"{claim}\" — the archive author's claim, NOT verified. "
                   if claim else "")
                + f"Era evidence from the file itself ({meta['format']}, "
                f"{ev['class_count']} classes): {era_text}. "
                f"This is evidence, NOT a claimed save date. SHA-256 {digest[:16]}…")
        existing = con.execute("SELECT id FROM games WHERE place_sha256=?", (digest,)).fetchone()
        if existing:
            game_id = existing["id"]
            prior = con.execute("SELECT provenance_note FROM games WHERE id=?",
                                (game_id,)).fetchone()["provenance_note"] or ""
            # Two independent public archives holding byte-identical copies is real
            # corroboration of identity (not of a save date): keep both notes.
            if cand["source_repo"].split(" ")[0] not in prior:
                note = (f"{note} Corroborated: the same SHA-256 also appears in the "
                        f"previously imported archive copy, so the two archives agree on "
                        f"the exact file.")
            con.execute("UPDATE games SET place_path=?, provenance_note=?, creator=? WHERE id=?",
                        (str(dest), f"{prior} | {note}" if prior else note, creator, game_id))
        else:
            cur = con.execute(
                """INSERT INTO games (name, creator, description, genre, place_path, place_sha256,
                   provenance_grade, provenance_note, compatibility_status, historical_place_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (name, "unverified", f"Preserved historical place: {name}. "
                 f"Imported from {cand['source_repo']}.", "All", str(dest), digest,
                 "3", note, "parsed", None))
            game_id = cur.lastrowid
        # Sidecar conventions in quarantine/places/:
        #   <name>.rbxl.meta.json  the archive's own metadata, carried verbatim
        #                          (creator/badges as the archive asserts them)
        #   <stem>.meta.json       same, for the curated/seeded set
        #   <stem>.bloxen.json     BLOXEN's provenance record: SHA-256, source repo,
        #                          era evidence, attribution caveats
        # Keeping BLOXEN's record separate means it can never overwrite an archive
        # sidecar (which is evidence) with our own summary.
        sidecar = dest.with_suffix(".bloxen.json")
        sidecar.write_text(json.dumps({
            "File": cand["file"], "Source": cand["source_repo"],
            "SHA256": digest, "Creator": "unverified",
            "FilenameDateClaim": claim or "none",
            "ArchiveAttributedCreator": creator,
            "EraEvidence": {"markers": ev["markers"],
                            "post_2013_markers": ev["post_2013_markers"],
                            "class_count": ev["class_count"],
                            "basis": "full parsed class/property usage, not a claimed save date"},
            "ImportNote": "Imported by tools/import_places.py; scripts inventoried, never executed.",
        }, indent=1))

        row = con.execute("SELECT id FROM place_imports WHERE sha256=?", (digest,)).fetchone()
        if not row:
            con.execute(
                """INSERT INTO place_imports (source_path, sha256, format, class_counts,
                   external_asset_ids, service_report, script_inventory, accepted)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (meta["source_path"], digest, meta["format"], json.dumps(meta["class_counts"]),
                 json.dumps(meta["external_asset_ids"]), json.dumps(meta["service_report"]),
                 json.dumps(meta["script_inventory"])))
            for a in meta["external_asset_ids"]:
                try:
                    aid = int(a)
                except ValueError:
                    continue
                con.execute("INSERT OR IGNORE INTO assets (historical_asset_id, asset_type, status) "
                            "VALUES (?, 'Unknown', 'MISSING')", (aid,))
                arow = con.execute("SELECT id FROM assets WHERE historical_asset_id=?", (aid,)).fetchone()
                con.execute("INSERT OR IGNORE INTO asset_dependencies (game_id, asset_id) VALUES (?,?)",
                            (game_id, arow["id"]))
        con.commit()
        cand["status"] = "imported"
        cand["era_evidence"] = ev
        cand["imported_as"] = {"game_id": game_id, "name": name, "sha256": digest}
        save_state(state)
        print(f"[imported] #{game_id} {name[:44]:46} instances={meta['instance_count']:6} "
              f"scripts={len(meta['script_inventory']):4} assets={len(meta['external_asset_ids']):4}")
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", metavar="DIR")
    ap.add_argument("--repo", default="")
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--import", dest="imports", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.discover:
        print(discover(Path(args.discover), args.repo))
    if args.imports:
        do_import(args.imports, force=args.force)
    if args.state or not (args.discover or args.imports):
        show_state()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

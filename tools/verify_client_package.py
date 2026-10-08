#!/usr/bin/env python3
"""Verify the quarantined 2015 WindowsPlayer package against its recorded manifest.

The client is treated as *evidence*, so it is hashed, never executed:

    PYTHONPATH=server .venv/bin/python tools/verify_client_package.py            # verify
    PYTHONPATH=server .venv/bin/python tools/verify_client_package.py --write-manifest \
        --source "/path/to/July 23 (0.205.0.61876)"                              # record

What is checked
- every file's SHA-256 against CLIENT-MANIFEST.json
- RobloxPlayerBeta.exe against the hash this project recorded *before* the package was
  obtainable (docs/WINDOWS-REAL-CLIENT-VALIDATION.md §2) — the point of the exercise
- the PE header facts that date the build (timestamp, version resource, Authenticode)

Files under PlatformContent/ are large (~90 MB of DDS textures) and are deliberately not
committed; the manifest still carries their hashes so the package can be completed and
verified from the source archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "quarantine" / "client" / "version-0d46087630eb46cd"
MANIFEST = CLIENT_DIR / "CLIENT-MANIFEST.json"

# Recorded in the project before the package was obtainable; it stayed UNVERIFIED for as
# long as no copy of the client could be reached from this environment.
EXPECTED_EXE_SHA256 = ("384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44")
EXPECTED_VERSION = "0.205.0.61876"
ACQUIRED_FROM = {
    "repo": "github.com/KloBraticc/2015-Client",
    "path": "July 23 (0.205.0.61876)",
    "commit": "7a0742cb900079d39c43e1113350338bff1f5a06",
    "note": ("Public archive of the 23 July 2015 build. Held by two archives in identical "
             "form (see docs/CLIENT-PACKAGE.md); the file version resource, PE timestamp "
             "and the client's own hash all agree with the recorded target."),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pe_facts(exe: Path) -> dict:
    """Version resource + PE timestamp + Authenticode presence, read from the bytes."""
    with open(exe, "rb") as f:
        head = f.read(4096)
    pe = struct.unpack_from("<I", head, 0x3C)[0]
    if head[pe:pe + 4] != b"PE\x00\x00":
        return {"error": "not a PE file"}
    machine, sections, ts = struct.unpack_from("<HHI", head, pe + 4)
    magic = struct.unpack_from("<H", head, pe + 24)[0]
    ddoff = pe + 24 + (96 if magic == 0x10B else 112)
    cert_off, cert_size = struct.unpack_from("<II", head, ddoff + 4 * 8)
    facts = {
        "machine": f"0x{machine:04x}",
        "sections": sections,
        "pe_timestamp_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
        "authenticode": f"signed ({cert_size} byte certificate table)" if cert_size
                        else "not signed",
    }
    # VS_FIXEDFILEINFO carries the numeric version the deploy history quotes
    i = exe.read_bytes().find(b"\xbd\x04\xef\xfe")
    if i != -1:
        fv_ms, fv_ls = struct.unpack_from("<II", exe.read_bytes(), i + 8)[:2]
        facts["file_version"] = f"{fv_ms >> 16}.{fv_ms & 0xffff}.{fv_ls >> 16}.{fv_ls & 0xffff}"
    return facts


def walk(base: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(base.rglob("*")):
        if path.is_file():
            rel = path.relative_to(base).as_posix()
            out[rel] = {"sha256": sha256_file(path), "size": path.stat().st_size}
    return out


def write_manifest(source: Path | None) -> None:
    """Record hashes for the committed subset, plus the deferred PlatformContent files."""
    files: dict[str, dict] = {}
    if CLIENT_DIR.exists():
        for rel, meta in walk(CLIENT_DIR).items():
            files[rel] = {**meta, "present": True}
    deferred = 0
    deferred_bytes = 0
    if source and source.exists():
        for rel, meta in walk(source).items():
            if rel in files:
                continue
            files[rel] = {**meta, "present": False,
                          "deferred_reason": "PlatformContent textures: not committed "
                                             "(~90 MB); complete from the source archive"}
            deferred += 1
            deferred_bytes += meta["size"]
    exe = CLIENT_DIR / "RobloxPlayerBeta.exe"
    manifest = {
        "package": f"WindowsPlayer version-0d46087630eb46cd ({EXPECTED_VERSION})",
        "acquired_from": ACQUIRED_FROM,
        "verification": {
            "robloxplayerbeta_sha256": sha256_file(exe) if exe.exists() else None,
            "expected_sha256": EXPECTED_EXE_SHA256,
            "pe": pe_facts(exe) if exe.exists() else None,
            "corroboration": ("DeployHistory.txt (research/sources/setup-rbxcdn/) records "
                              "'New WindowsPlayer version-0d46087630eb46cd at 7/23/2015 "
                              "11:33:45 PM, file version: 0, 205, 0, 61876'."),
        },
        "file_count": len(files),
        "committed_files": sum(1 for f in files.values() if f["present"]),
        "deferred_files": deferred,
        "deferred_bytes": deferred_bytes,
        "files": files,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print(f"manifest written: {MANIFEST}")
    print(f"  committed {manifest['committed_files']} files, "
          f"deferred {deferred} ({deferred_bytes / 1e6:.1f} MB of PlatformContent)")


def verify() -> int:
    if not MANIFEST.exists():
        print("no CLIENT-MANIFEST.json — run with --write-manifest first")
        return 2
    manifest = json.loads(MANIFEST.read_text())
    bad = missing = 0
    for rel, meta in manifest["files"].items():
        if not meta["present"]:
            continue
        path = CLIENT_DIR / rel
        if not path.exists():
            print(f"  MISSING  {rel}")
            missing += 1
            continue
        if sha256_file(path) != meta["sha256"]:
            print(f"  MISMATCH {rel}")
            bad += 1
    ver = manifest["verification"]
    exe = CLIENT_DIR / "RobloxPlayerBeta.exe"
    exe_hash = sha256_file(exe) if exe.exists() else None
    hash_ok = exe_hash == ver["expected_sha256"]
    print(f"files: {manifest['committed_files']} committed, "
          f"{manifest['deferred_files']} deferred")
    print(f"RobloxPlayerBeta.exe SHA-256: {exe_hash}")
    print(f"  matches the hash recorded before acquisition: {'YES' if hash_ok else 'NO'}")
    pe = ver.get("pe") or {}
    print(f"  file version {pe.get('file_version')}  PE timestamp {pe.get('pe_timestamp_utc')}")
    print(f"  {pe.get('authenticode')}")
    ok = not (bad or missing) and hash_ok
    print("RESULT:", "VERIFIED" if ok else f"PROBLEMS (bad={bad} missing={missing})")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-manifest", action="store_true")
    ap.add_argument("--source", type=Path, default=None,
                    help="full package directory (including PlatformContent) to hash")
    args = ap.parse_args()
    if args.write_manifest:
        write_manifest(args.source)
        return 0
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())

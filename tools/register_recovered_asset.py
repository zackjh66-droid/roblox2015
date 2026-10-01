"""Register recovered historical assets with provenance (idempotent).

Usage:
  PYTHONPATH=server .venv/bin/python tools/register_recovered_asset.py \
      <asset_id> <local_path> <asset_type> <source_url> <grade> "<note>"
"""
import datetime as dt
import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def register(asset_id: int, local: Path, asset_type: str, source_url: str,
             grade: str = "3", note: str = "") -> None:
    local = (ROOT / local).resolve()
    digest = sha256_file(local)
    con = sqlite3.connect(ROOT / "data" / "bloxen.db")
    con.execute(
        """UPDATE assets SET status='RECOVERED', asset_type=?, name=?, local_path=?,
           sha256=?, source_url=?, provenance_grade=?, notes=?
           WHERE historical_asset_id=?""",
        (asset_type, f"Recovered {asset_type} {asset_id}", str(local.relative_to(ROOT)),
         digest, source_url, grade, note, asset_id),
    )
    con.commit()
    row = con.execute(
        "SELECT historical_asset_id,status,sha256 FROM assets WHERE historical_asset_id=?",
        (asset_id,)).fetchone()
    print(f"assets -> {row}")
    # research DB record
    rcon = sqlite3.connect(ROOT / "research" / "db" / "research.sqlite3")
    exists = rcon.execute(
        "SELECT 1 FROM sources WHERE local_path=?",
        (str(local.relative_to(ROOT)),)).fetchone()
    if not exists:
        rcon.execute(
            """INSERT INTO sources (title, url, archive_timestamp, retrieved_at,
               content_type, historical_entity, local_path, sha256, provenance_grade,
               verification_state, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (f"Recovered historical asset {asset_id}", source_url,
             "2025", dt.datetime.now().isoformat(timespec="seconds"),
             asset_type, f"Roblox asset {asset_id}", str(local.relative_to(ROOT)),
             digest, grade, "partially-verified", note),
        )
        rcon.commit()
    print(f"research.db -> recorded asset {asset_id}")


if __name__ == "__main__":
    aid = int(sys.argv[1])
    register(aid, Path(sys.argv[2]), sys.argv[3], sys.argv[4],
             sys.argv[5] if len(sys.argv) > 5 else "3",
             sys.argv[6] if len(sys.argv) > 6 else "")

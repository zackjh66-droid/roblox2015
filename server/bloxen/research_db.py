"""Research database access + provenance helpers."""
import datetime as _dt
import hashlib
import sqlite3
from pathlib import Path

from . import config

GRADE_LABELS = {
    "1": "ORIGINAL (preserved original material)",
    "2": "ARCHIVED-EXACT (archived exact-date evidence)",
    "3": "ARCHIVED-NEAR (archived near-date evidence)",
    "4": "RECONSTRUCTION (reconstruction from evidence)",
    "5": "INFERENCE (inference only)",
}


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.RESEARCH_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection) -> None:
    schema = (config.RESEARCH / "schema.sql").read_text()
    con.executescript(schema)
    con.commit()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def add_source(con, *, title, url=None, archive_timestamp=None, target_date=None,
               content_type=None, historical_entity=None, local_path=None,
               sha256=None, grade="4", verification_state="unverified", notes=None) -> int:
    cur = con.execute(
        """INSERT INTO sources (title, url, archive_timestamp, retrieved_at, target_date,
           content_type, historical_entity, local_path, sha256, provenance_grade,
           verification_state, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (title, url, archive_timestamp, _dt.datetime.now().isoformat(timespec="seconds"),
         target_date, content_type, historical_entity,
         str(local_path) if local_path else None, sha256, str(grade),
         verification_state, notes),
    )
    con.commit()
    return cur.lastrowid


def add_claim(con, *, topic, claim, evidence_source_id=None, grade="5", state="proposed") -> int:
    cur = con.execute(
        "INSERT INTO claims (topic, claim, evidence_source_id, grade, state) VALUES (?,?,?,?,?)",
        (topic, claim, evidence_source_id, str(grade), state),
    )
    con.commit()
    return cur.lastrowid


def log_verification(con, subject, method, result, detail=None) -> None:
    con.execute(
        "INSERT INTO verification_log (subject, method, result, detail) VALUES (?,?,?,?)",
        (subject, method, result, detail),
    )
    con.commit()

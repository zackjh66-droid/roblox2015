"""SQLite access + migration runner for the BLOXEN application database."""
import sqlite3
from pathlib import Path

from . import config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def applied(con: sqlite3.Connection) -> set[str]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    return {r["name"] for r in con.execute("SELECT name FROM _migrations")}


def migrate(con: sqlite3.Connection) -> list[str]:
    done = applied(con)
    ran = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.name in done:
            continue
        con.executescript(f.read_text())
        con.execute("INSERT INTO _migrations (name) VALUES (?)", (f.name,))
        con.commit()
        ran.append(f.name)
    return ran


def init(path: Path | None = None) -> sqlite3.Connection:
    con = connect(path)
    migrate(con)
    return con

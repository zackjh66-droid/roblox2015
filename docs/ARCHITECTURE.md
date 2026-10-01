# BLOXEN — ARCHITECTURE

```
run_all.py
├── web   (FastAPI + Jinja2 + aiosqlite)      :8080   website, auth, play tickets
├── compat (FastAPI)                          :8081   2015-client HTTP surface (localhost only)
├── assets (FastAPI)                          :8082   asset recovery index (localhost only)
└── gameserver (asyncio UDP RakNet + replicator) :53640  game server
```

## Modules

| Path | Role |
|---|---|
| `server/bloxen/app.py` | website routes (2015-styled pages + JSON APIs) |
| `server/bloxen/db.py` | SQLite schema + helpers (users, sessions, tickets, items, inventory, avatar, games, friends, groups, messages, places, instances, assets, compat_requests) |
| `server/bloxen/security.py` | PBKDF2 hashing, session tokens, single-use play tickets |
| `server/bloxen/research_db.py` | provenance DB (sources/captures/findings/verification_log) |
| `server/bloxen/config.py` | target date, ports, protocol 31, RakNet magic, build constants |
| `server/bloxen/importer/` | RBXL/RBXLX parser (binary + XML), script inventory, asset extraction, compatibility report |
| `server/bloxen/compat/` | 2015-client HTTP surface |
| `server/bloxen/assetsvc/` | asset recovery service |
| `server/bloxen/gameserver/` | bitstream, raknet, descriptors (API-dump based), replicator (SET_GLOBALS/ID_DATA), GameServer |
| `server/bloxen/launcher/` | bloxen-player URI parser + ticket validation + client hash allowlist (never executes) |
| `server/bloxen/simulator/` | SIMULATOR-TESTED full-stack client harness (`python -m bloxen.simulator.client -v`) |
| `tools/seed.py` | evidence-backed seeder (games, catalog items, research DB) |
| `tools/import_capture.py` | quarantine-style research capture intake |
| `tests/` | unit + full-stack end-to-end tests (live services over real ports) |
| `tests/test_importer_fixtures.py` | parser regression fixtures against quarantined places |

## Data

| Path | Role |
|---|---|
| `data/bloxen.sqlite3` | main DB |
| `data/research.db` | research/provenance DB |
| `data/world_cache.json` | parsed-place cache (keyed by place SHA-256) |
| `quarantine/places/` | accepted place files + `.meta.json` + SHA-256 manifests |
| `research/sources/` | source snapshots + format specs |
| `checkpoints/` | run records + screenshots |

## Testing

```
.venv/bin/python -m pytest tests/ -q
```

- unit: importer, launcher URI, bitstream, game lists
- `tests/test_e2e_stack.py`: starts the REAL multi-service stack and drives the full journey:
  register → login → session → catalog browse → purchase → inventory → avatar equip →
  profile → friends → messages → **Play ticket (single-use)** → simulator: ticket validation →
  compat negotiate/visit/placelauncher/characterfetch → RakNet handshake → protocol 31 →
  descriptor sync (332 classes) → SET_GLOBALS (121-bit preamble, 22 containers,
  ReplicatedFirst) → ID_DATA.

All wire/game-server results are SIMULATOR-TESTED.

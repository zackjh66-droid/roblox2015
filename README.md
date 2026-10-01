# BLOXEN

**An unofficial preservation reconstruction of the July 2015 Roblox experience.**
Not affiliated with Roblox Corporation. Target date: **23 July 2015**. Target client:
**Windows Player 0.205.0.61876 (`version-0d46087630eb46cd`)** — version identity verified
from three independent archived sources.

## What this is

- Historically faithful website (Games, Catalog, Profile, Character/Avatar, Inventory,
  Friends, Groups, Develop, Messages, Search, Login/Register, Account Settings) built on
  **preserved original 2015 CSS bundles** and archived page structure
- Accounts, profiles, friends, messages (modern password hashing; never real Roblox creds)
- Historical **catalog** (evidence-backed items only — no invented filler) + avatar editor +
  inventory, wired end-to-end
- **Legitimately preserved historical games** (7 accepted, imported, parsed; scripts
  inventoried and never executed) + RBXL/RBXLX importer with compatibility reports
- **2015-client compatibility HTTP service** + game server (RakNet, protocol 31, replica
  init with the evidenced SET_GLOBALS layout, authoritative ID_DATA) + launcher with
  single-use Play tickets
- A **simulated historical client harness** (SIMULATOR-TESTED) driving the full stack
- Research/provenance database with grading (1 preserved original → 5 inference); anything
  reconstructed is labeled **not original**

## Status highlights

- Target build identity: **VERIFIED** (3 sources)
- Full end-to-end suite: **7/7 passing** (live web + compat + assets + game server)
- Simulator scenario: register → Play → RakNet → descriptors → SET_GLOBALS → ID_DATA: **PASS**
- Genuine client execution: **BLOCKED in this cloud environment** — see
  `docs/WINDOWS-REAL-CLIENT-VALIDATION.md`. Nothing is claimed REAL-CLIENT-TESTED.
- Asset recovery: 609 unique external asset IDs referenced by preserved games,
  **15 recovered** (real historical meshes/sounds/textures) / **594 honestly labeled
  MISSING** (no fabrications)

## Run

```bash
.venv/bin/python server/run_all.py
# web http://localhost:8080 · compat :8081 · assets :8082 · game udp/53640

PYTHONPATH=server .venv/bin/python -m bloxen.simulator.client -v   # simulator scenario
.venv/bin/python -m pytest tests/ -q                                # full test suite
```

## Docs

`docs/ARCHITECTURE.md` · `docs/CLIENT.md` · `docs/WEBSITE.md` · `docs/GAMES.md` ·
`docs/CATALOG.md` · `docs/ASSETS.md` · `docs/PROTOCOL.md` · `docs/PROVENANCE.md` ·
`docs/WINDOWS-REAL-CLIENT-VALIDATION.md`

## Honesty rules baked into the system

1. Never invent historical content; missing stays **MISSING**
2. Grade 4/5 material is labeled **not original**, never "preserved"
3. Simulator results are **SIMULATOR-TESTED**; genuine-client observations always win
4. Import intake: quarantine → hash → parse → report; scripts as inert data
5. Compat services are local/private by default and **never** forward to live Roblox
6. No real Roblox credentials; no execution of unreviewed historical executables

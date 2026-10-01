# BLOXEN — GAMES

## Preservation sources

| Source | Content | Grade |
|---|---|---|
| [LuaGunsX/RobloxRBXLArchive](https://github.com/LuaGunsX/RobloxRBXLArchive) | 661 .rbxl files + 86 sidecar `.meta.json` (creator + historical badge IDs) | 3 (archived near; sidecar metadata cross-checked) |
| [beagleded/Roblox-Places-Archive](https://github.com/beagleded/Roblox-Places-Archive) | 125 .rbxl files, "most from Old Roblox (2007–2015)" — README warns untested | 3 |
| tropicalbananas/robloxplacearchive, Dawgra/Roblox-Archived-Places, MisoNotSoupx/Old-Roblox-Place-Archive, LeonetKenner/RobloxRBXLArchive | additional candidates | 3 |

Provenance policy: filenames are never trusted alone; each candidate is checked for creator
records (sidecar metadata), place-file parse results (class/property fingerprints), badge IDs,
and cross-source consistency. Material from leaks / private access / credential theft /
exploit dumping is **rejected** (no such sources were used).

## Accepted games (all imported + parsed)

| Game | Creator | Place file | SHA-256 (prefix) | Instances | Scripts (inert) | External asset IDs | Provenance |
|---|---|---|---|---|---|---|---|
| Work at a Pizza Place (2014L) | Dued1 | `quarantine/places/Work at a Pizza Place (2014L).rbxl` | ec24026c… | 33,221 | 311 | 228 | meta.json: creator Dued1 + 6 badge IDs |
| Speed Run 4 (1st part) | Vurse | `Speed Run 4 (1st part).rbxl` | 01e1cba1… | 6,904 | 131 | 75 | meta.json: creator Vurse + 8 badges |
| Welcome to the Town of Robloxia | 1dev2 | `Welcome to the Town of Robloxia.rbxl` | f88df433… | 13,567 | 221 | 0 | meta.json: creator 1dev2 + 9 badges (300k…10M visits) |
| The Normal Elevator | NowDoTheHarlemShake | `The Normal Elevator - Fixed for 2015M.rbxl` | e2eab5df… | 19,382 | 289 | 307 | meta.json + **filename marks community modification ("Fixed for 2015M") — recorded, not hidden** |
| Mad Games (v1.3b, 2015) | loleris | `Mad Games (v1.3b, 2015).rbxl` | 8b514a0a… | 33,089 | 228 | 197 | meta.json: creator loleris + 1 badge; version label v1.3b 2015 |
| Flood Escape (July 8th, 2015, V1.6.5) | Crazyblox | `Flood Escape (July 8th, 2015, V1.6.5).rbxl` | c247b438… | 10,015 | 311 | 82 | meta.json: creator Crazyblox + 17 badges; **exact-era save date** |
| Natural Disaster Survival | Stickmasterluke | `Natural Disaster Survival.rbxl` | da90bd8d… | 9,595 | 23 | 0 | beagleded copy (no sidecar); creator attribution grade 3 |

**Total: 7 preserved games imported and parsed, 1,500+ scripts inventoried (never
executed), 609 unique external asset IDs indexed.**

## Rejected / missing candidates

- **Hide and Seek Extreme** — no place file found in any legitimate public source located.
  Script fragments exist (`lechayy/Hide-And-Seek-Extreme-v2`), but a script is not a place.
  Status: **MISSING**. Search continues; do not fabricate.

## Importer pipeline

`server/bloxen/importer/` — pipeline: candidate → quarantine → SHA-256 → parse (binary
RBXL or XML RBXLX) → DataModel tree → services/instances/properties/references →
**scripts as inert data** → external asset IDs → compatibility report vs the target build
API dump.

Binary format implemented from public reverse-engineering (rojo-rbx/rbx-dom,
Dekkonot/rbx-binary-format — source snapshots in `research/sources/formats/`): chunk framing
(META/SSTR/INST/PROP/PRNT/END), LZ4 blocks (compressed_length==0 ⇒ raw — note LZ4 blocks can
compress to exactly their uncompressed size; length equality is NOT a raw/compressed test),
interleaved integer arrays, rotated floats, zigzag-delta referents. XML format per the
official `roblox.xsd`.

Regression fixtures: `tests/test_importer_fixtures.py` runs the parser against the real
quarantined places and asserts class/instance fingerprints (safe parsed metadata only).

## Scripting / game logic policy

- Historical Lua is **inventoried, hashed, and never auto-executed** (intake rule).
- Compatibility status ladder: `researched → imported → parsed → metadata-ok →
  SIMULATOR-TESTED → REAL-CLIENT-TESTED`.
- No game is claimed *playable* until its actual required logic runs under a controlled,
  reviewed runtime. Current status of every game: **parsed / metadata-ok**, SIMULATOR-TESTED
  replication of its hierarchy. Gameplay logic = NOT RUNNING (explicitly).
- A controlled script-evaluation stage (reviewed scripts only, sandboxed) is future work;
  per-game requirements will be tracked in `place_imports.script_inventory`.

## Per-game playability requirements (static analysis — scripts never executed)

`tools/gameplay_requirements.py` statically scans all 1,514 script bodies (3.5 MB Lua,
SHA-256'd) to classify required runtime features. Output:
`research/db/gameplay_requirements.json`.

| Game | Scripts | Source scanned | Features detected (sample) | Required logic pillars | Playable? |
|---|---|---|---|---|---|
| Work at a Pizza Place | 311 | 1.0 MB | remotes, Humanoid, GUI, persistence, BodyMovers, teams | pizza state machine, jobs, building tools, money, customer AI | **NO** |
| Speed Run 4 | 131 | 78 KB | checkpoints, leaderstats, spawn/reset | stage system, timer, kill bricks | **NO** |
| Town of Robloxia | 221 | 309 KB | jobs, tools, teams, day/night | job system, disaster cycle, housing | **NO** |
| The Normal Elevator | 289 | 714 KB | GUI, remotes, camera | elevator FSM, floors, minigame rounds | **NO** |
| Mad Games | 228 | 792 KB | round logic, loadout, leaderstats | minigame rotation, scoring | **NO** |
| Flood Escape | 311 | 530 KB | physics parts, GUI, voting | water sim, maps, buttons, stages | **NO** |
| Natural Disaster Survival | 23 | 90 KB | disaster scheduler, effects, admin-commands script (**stays inert forever**) | disaster physics, map rotation, scoring | **NO** |

**No game is claimed playable.** The path to "playable" is: review each script family →
sandboxed 2015-Lua runtime → feature-gated activation per pillar → SIMULATOR-TESTED →
(real client) REAL-CLIENT-TESTED. Person299's Admin Commands (NDS) and any admin/HTTP
scripts remain quarantined inert data regardless.

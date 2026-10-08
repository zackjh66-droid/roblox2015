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

---

# Game library expansion (2026-10-05) — real files from public archives

Seven more real historical place files were imported from
`beagleded/Roblox-Places-Archive` (GitHub, public; the same archive that supplied Natural
Disaster Survival). Import is performed by `tools/import_places.py`, which implements the
intake rule end-to-end: candidate → quarantine → SHA-256 → parse → DB.

| Game | Place file | Instances | Scripts | Notes |
|---|---|---|---|---|
| Contamination | `Contamination.rbxl` | 6,287 | 555 | no post-2013 markers in the file |
| Base Wars | `Base Wars.rbxl` | 4,793 | 473 | no post-2013 markers in the file |
| Happy Home in Robloxia | `Happy Home in Robloxia.rbxl` | 18,631 | 6 | post-2013 markers present |
| Rocket Fight Advanced | `Rocket Fight Advanced.rbxl` | 370 | 81 | post-2013 markers present |
| ROBLOX Battle | `ROBLOX Battle.rbxl` | 2,280 | 126 | post-2013 markers present |
| Martian Invasion | `Martian Invasion.rbxl` | 8,723 | 256 | post-2013 markers present |
| Building with Friends | `Building with Friends.rbxl` | 2,644 | 6 | post-2013 markers present |

**Total library: 14 preserved games, 3,000+ scripts inventoried (never executed).**

## Provenance policy for these seven (stricter, because the archive has no sidecars)

- **Creator attribution: UNVERIFIED.** No sidecar metadata exists in this archive, so the
  `games.creator` value is literally `unverified`. The site shows that. Nothing is guessed.
- **Era is evidence, not a claim.** The importer records *in-file* evidence — the set of
  classes/properties actually used (`FilteringEnabled`, `StreamingEnabled`, `BodyColors`,
  `Animator`, `R15`, meshes, CSG…) — in the `.meta.json` sidecar under `EraEvidence`, next to
  the SHA-256 of the exact bytes. No save date is claimed for any of them. An early byte-prefix
  heuristic in the tool was rejected as unreliable and replaced by a scan of the whole parsed
  tree before import.
- Files that are visibly modern (post-2016 markers) are still marked as such rather than
  presented as 2015-era copies.

## Catalogue state and pending candidates

`tools/import_places.py --state` prints the full candidate inventory (currently 124 files
hashed from the archive, 7 imported). Candidates are ranked by in-file era evidence and size.
Unported candidates remain **candidates** — never described as part of the library.

```bash
PYTHONPATH=server .venv/bin/python tools/import_places.py --discover DIR --repo "owner/repo"
PYTHONPATH=server .venv/bin/python tools/import_places.py --state
PYTHONPATH=server .venv/bin/python tools/import_places.py --import <candidate-id> [...]
```

## Playability statement (unchanged, now with a visual runtime)

All 14 games are **parsed / metadata-ok / geometry-exported / BROWSER-TESTED as maps**. What
that means precisely:

- their **world geometry, colours, spawn points and lighting render** in the BLOXEN client
  runtime, from the real file bytes (docs/CLIENT-RUNTIME.md)
- their **Lua does not run**, so no game logic, rounds, disasters, tools or scoring exist
- maps whose authoring keeps the world in `ServerStorage`/`ReplicatedStorage` (Flood Escape,
  The Normal Elevator, Mad Games) show those parts **as saved in the file**, with the container
  reported in the runtime menu and a toggle to hide them — because cloning them into the world
  happens in script, which we do not run
- **no game is claimed playable as a game.** The script-evaluation path (reviewed scripts →
  sandboxed 2015-Lua runtime) remains future work.


## 2015 additions and the attribution ladder (2026-10-05, later)

Six further places were added from `LuaGunsX/RobloxRBXLArchive` because the archive
labels them with real 2015 save windows, and four of them came with the archive's own
sidecar metadata:

| # | Place | Archive label | Attribution |
|---|-------|---------------|-------------|
| 15 | After The Flash — Sandstorm | December 2015 | none in archive (UNVERIFIED) |
| 16 | F3X Building Game | 2015M build | none in archive (UNVERIFIED) |
| 17 | Island III | 2015L build | none in archive (UNVERIFIED) |
| 18 | The Plaza Karts | September 27th, 2015 | none in archive (UNVERIFIED) |
| 19 | Vampire Hunters 2 | Beta 1.2, June 14th, 2015 | none in archive (UNVERIFIED) |
| 20 | Flood Escape | January 19th, 2015, V1.6.2 | Crazyblox (archive sidecar) |

**Corroboration event.** Three files already in the library turned out to share a SHA-256
with LuaGunsX's dated copies: *Mad Games* (v1.3b, 2015), *The Normal Elevator*
("Fixed for 2015M") and *Flood Escape* (V1.6.5, July 8th 2015). Two independent public
archives holding byte-identical copies upgrades the *identity* evidence — it does not
verify a save date. Those three moved from creator `unverified` to the creator the
archive's sidecar names (loleris, NowDoTheHarlemShake, Crazyblox), recorded in the DB as
attribution by the archive author, explicitly not verified against Roblox services.

**Attribution ladder** (each rung is a claim of different strength; nothing here is
independently verified):

1. `UNVERIFIED` — no sidecar; only in-file era evidence.
2. `ATTRIBUTED` — the archive's sidecar names a creator (this is what the three above
   are). Recorded as such, never as fact.
3. `FILENAME CLAIM` — a date in a filename ("July 8th, 2015"). Recorded as the archive
   author's claim in every case, never used to date the build.
4. In-file era evidence — binary format, class/property fingerprints. The strongest
   *machine* signal available here, still an inference.

Sidecar files are kept in `quarantine/places/` under three names, and the importer never
overwrites one kind with another: `<name>.rbxl.meta.json` (the archive's metadata, carried
verbatim), `<stem>.meta.json` (same for the curated/seeded set) and `<stem>.bloxen.json`
(BLOXEN's own provenance record — SHA-256, source repo, era evidence, caveats).

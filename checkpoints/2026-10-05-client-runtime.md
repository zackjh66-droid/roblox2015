# Checkpoint — 2026-10-05: playable browser client runtime + game archive import

## What was delivered

1. **BLOXEN client runtime** (`web/static/js/bloxen-client.js`, `web/templates/play.html`,
   `web/static/css/bloxen-runtime.css`) — renders preserved 2015 place files in a browser via
   three.js: real geometry, sizes, CFrames, BrickColor palette, surface types, materials,
   spawns and Lighting; R6 character with genuine dimensions and 2015 physics constants
   (gravity 196.2, WalkSpeed 16, JumpPower 50); third-person camera with occlusion pull-in,
   free camera and top-down overview; in-experience honesty panel.
2. **Geometry exporter** (`server/bloxen/placeview/geometry.py`) — parsed place tree →
   render-ready payload, cached per place SHA-256; reports everything it does *not* draw
   (CSG unions, mesh parts, terrain, unrecovered decals, un-run Lua) and which container each
   part came from (Workspace vs ServerStorage/ReplicatedStorage maps).
3. **Importer/parser fixes found while building it** (all pinned by tests):
   - interleaved integer byte-planes were read little-endian; the format is big-endian
     (plane 0 = most significant) → every binary place previously produced garbage
     sizes/positions
   - CFrame blocks: the orientation-id byte precedes the three position arrays, and the
     24-entry compact orientation table must be applied (was a single placeholder identity)
   - UDim/Color3 were per-instance tuples instead of arrays-of-arrays
   - RBXLX structured properties (Vector3 / CoordinateFrame / Color3) were dropped entirely;
     colors now decode from the packed 0xRRGGBB form
4. **Game library: 7 → 14 real preserved games**, imported by the new
   `tools/import_places.py` (discover → catalogue → quarantine → hash → parse → DB), with
   creator attribution recorded as UNVERIFIED where the archive has no sidecar and era
   recorded as in-file evidence only (124-file candidate catalogue kept in
   `data/game-archive-catalogue.json`).
5. **Website**: Play buttons on the games grid and place pages launch the runtime; games
   without a place file are labelled not playable; `/images/…` returns a labelled MISSING
   placeholder; Source Sans Pro served locally (dead 2015 Google CDN); trademark imagery
   suppressed; the place page no longer posted to a non-existent route.
6. **Validation tooling**: `tools/browser/probe_client.py` (real CDP probe: console,
   exceptions, failed requests, page state, screenshot) and
   `tools/browser/validate_all_games.py`.
7. **Tests**: `tests/test_place_geometry.py` (19 new tests) — 36/36 passing suite.

## Evidence

| Check | Result |
|---|---|
| `pytest tests/ -q` | **36 passed** |
| Headless Chromium, all 14 games | **14/14 PASS**, 0 JS errors, 0 HTTP failures |
| Renderer | ANGLE/Vulkan SwiftShader WebGL2 (software) — 20–55 fps at 1280×860 |
| Screenshots | `checkpoints/screenshots/runtime-play-01..14.png`, `runtime-site-*.png` |
| Geometry payload sizes | 0.01–2.6 MB per place, 9.0 MB total, cached |

## Physics fixes found by browser validation

- negative first-frame `dt` (boot's `performance.now()` can post-date the first rAF
  timestamp) launched the character upward — fixed and clamped
- single-point ground probing tunnelled through floors at fall speed, and step-up ratcheted
  the character 2 studs/frame while stuck in geometry — replaced by a swept ground column
  plus an explicit depenetration routine
- spawn resolution: prefer an unobstructed `SpawnLocation` **with ground beneath it**, else
  stand on the nearest real surface, else depenetrate to a clear spot with ground below.
  Several preserved maps (Contamination, Speed Run 4, Natural Disaster Survival, Mad Games)
  keep their spawns in mid-air because scripted logic would move the player; that logic does
  not run here, so this is documented as a BLOXEN choice, not engine behaviour

## Known gaps (unchanged honesty rules)

- Windows Player execution still **BLOCKED** (needs a real Windows VM; see
  docs/WINDOWS-REAL-CLIENT-VALIDATION.md). Nothing is REAL-CLIENT-TESTED.
- Place Lua is **never executed**: no game logic, rounds, disasters or tools.
- CSG unions, mesh parts and terrain are **not rendered** (no substitutes).
- 594/609 referenced external assets remain MISSING.
- Wedge orientation unresolved → flip toggle (docs/CLIENT-RUNTIME.md §7.1).
- Terrain voxel decoding, mesh asset retrieval and a reviewed Lua sandbox are the next
  fidelity steps.

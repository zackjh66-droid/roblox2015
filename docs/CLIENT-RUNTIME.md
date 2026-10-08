# BLOXEN — CLIENT RUNTIME (playable browser client)

**Status: BROWSER-TESTED.** The BLOXEN client runtime renders preserved 2015 place files in a
real browser, driven by a real WebGL renderer, and every game in the library has been loaded
and validated in headless Chromium with zero JS/HTTP errors (see § Validation evidence).

This is **not** the original Windows Player. The original client binaries are not obtainable
from this environment (docs/CLIENT.md), and nothing here is claimed to *be* that client. What
this runtime is: an honest, inspectable re-implementation that consumes the **real preserved
place files** so their maps can be walked and looked at, labelled feature by feature.

Run it: `.venv/bin/python server/run_all.py` → <http://localhost:8080/games> → **Play**.

---

## 1. What is REAL (taken from the preserved place file)

| Rendered / used | Source |
|---|---|
| Part positions, sizes, rotation matrices | decoded `CFrame` / `size` properties |
| Colours | `BrickColor` palette index → historical RGB table, or explicit `Color3uint8` |
| Transparency, reflectance, material names | `Transparency`, `Reflectance`, `Material` |
| Part shapes (Block / Ball / Cylinder / Wedge / CornerWedge / Truss) | class + `shape` enum |
| Surface studs and inlets | per-face `SurfaceType` (Studs / Inlet / Universal / Glue / Weld) |
| Spawn points | `SpawnLocation` CFrame (the client picks the least obstructed one) |
| Lighting | `Lighting` service: `Ambient`, `OutdoorAmbient`, `Brightness`, `TimeOfDay`, `FogColor`, fog range |
| Collision | `CanCollide` + anchored flags from the file; `Anchored=false` parts are not physically simulated (no physics engine) |
| Container layout | which service each part lives in is preserved and shown in the menu |

Geometry fidelity is byte-for-byte derived from the place file: the geometry payload records
the place SHA-256 it came from, and `tests/test_place_geometry.py` asserts physical plausibility
(all part sizes within Roblox's 0.05–2048 stud limits, all CFrames finite and in range).

## 2. What is a RECONSTRUCTION (labelled in the in-experience menu)

| Item | Why | Where |
|---|---|---|
| HUD chrome (top bar, menu, chat, player list) | the 2015 client's UI bitmaps ship inside the client package, which is not available | `web/static/css/bloxen-runtime.css`, `web/templates/play.html` |
| Stud / inlet **textures** | same reason; the pattern is generated from the surface-type data instead of the client's bitmaps | `makeSurfaceTexture()` |
| R6 walk animation | the default R6 animation asset is not recovered; the motion is procedural (alternating limb swing at the classic cadence) | `animateCharacter()` |
| Character appearance | defaults only: genuine R6 dimensions and classic default colours. No hats/clothing — those assets are MISSING and are **not** faked | `buildCharacter()` |
| Sky gradient | derived from the place's clock time; the 2015 sky asset set is not recovered | `buildSky()` |

## 3. What is NOT rendered at all (no substitutes, ever)

- **CSG `UnionOperation`** — the solid data is not decoded, so the part is skipped. Counts are
  reported per place in the menu (e.g. Mad Games: 402 unions not drawn).
- **`MeshPart` / `SpecialMesh` / `FileMesh`** — mesh asset data is 594/609 MISSING. The owning
  part is drawn as its primitive box only where the file itself stores a primitive.
- **Terrain** — voxel grid decoding is not implemented.
- **Decals / Textures** — drawn only when the image asset is actually RECOVERED in the asset
  index; otherwise nothing is shown (e.g. Flood Escape: 104 referenced, 3 recovered).
- **The place's Lua** — inventoried, hashed, **never executed**.

Every one of these is listed in the in-experience menu ("Not rendered — honest report") and in
the `/api/place/{id}/geometry` payload under `unsupported`.

## 4. Physics and controls

Physics constants are the genuine 2015 defaults, not tuned-for-fun values:

| Constant | Value | Note |
|---|---|---|
| Gravity | 196.2 studs/s² | 2015 default |
| WalkSpeed | 16 studs/s | 2015 default |
| JumpPower | 50 studs/s | 2015 default (≈6.4 stud jump apex) |
| R6 height / radius | 5 studs / 1 stud | genuine R6 part dimensions |

Controls: **WASD** move, **Space** jump, **Shift** walk, right-drag orbit, wheel zoom,
**F** free camera (noclip), **O** top-down overview, **R** respawn, **M** menu, **Enter** chat.
Stepping up to 2 studs and sliding along walls are implemented; there is no ragdoll, no player
collision (single-player session) and no physics for unanchored parts.

### Spawn placement, and why it is a documented BLOXEN choice

In the real 2015 engine a player's spawn is resolved by scripted game logic. **None of that
Lua runs here**, so the runtime resolves spawns itself from the place's own geometry, in this
order (all implemented, all logged in the placeholder panel):

1. choose the `SpawnLocation` whose surroundings are least obstructed **and which has real
   ground beneath it** (a spawn floating over the void is scored worse);
2. if the chosen column has no floor at all (several preserved maps keep their spawns in the
   air — e.g. *Contamination*, *Speed Run 4*, *Natural Disaster Survival*, *Mad Zone*), stand
   on the nearest surface the file actually contains, searching outward and then upward;
3. if the character ends up overlapping geometry (spawn authored inside a building), move it
   to the nearest clear position **that has ground below it**, so it can never be pushed over
   an edge into the void;
4. if it still ends up falling for more than 4.5 s (mid-air spawn over a map with no
   baseplate), respawn once with the same procedure — this repeats occasionally for maps
   whose only spawns are over nothing, and the panel always reports the spawn it used.

Two physics bugs found and fixed during this work are worth recording because they were
invisible in the code and obvious in the browser:

- the first animation frame's timestamp can be *earlier* than any `performance.now()` taken
  during boot, which produced a **negative `dt`** and launched the character upward on the
  first frame (fixed by initialising from the frame timestamp and clamping `dt ≥ 0`);
- a single-point ground probe tunnelled through floors at high fall speed, and the step-up
  rule then *ratcheted* the character upward 2 studs per frame while it was stuck inside
  geometry (fixed with a swept ground column and an explicit depenetration routine).

## 5. API surface used by the runtime

| Route | Purpose |
|---|---|
| `GET /play/{game_id}` | the runtime page (200; 302 to /games if unknown) |
| `GET /api/place/{game_id}/geometry` | real place geometry (gzip; cached per place SHA-256 in `data/place_geometry/`) |
| `GET /api/place/{game_id}/scripts` | inert script inventory for the runtime panel |
| `GET /static/js/bloxen-client.js` | the runtime itself |
| `GET /static/js/three.module.js` | vendored three.js (MIT) — rendering only, no game data |
| `GET /static/data/brickcolor.json` | historical BrickColor palette |
| `GET /asset/{id}` | recovered historical asset, or 404 `{"status":"MISSING"}` |

`POST /play/start` (used by the place page) redirects into the runtime, so the historical
**Play** button and the tile-engine launch-ticket flow both lead to the same place.

## 6. Validation evidence

`tools/browser/probe_client.py` drives real headless Chromium over CDP: it collects console
output, JS exceptions and failed network requests, reads renderer state out of the page and
captures a screenshot. `tools/browser/validate_all_games.py` runs it for every imported game.

Latest run (2026-10-05, Chromium 153, SwiftShader WebGL2):

| Game | Loaded | WebGL | JS/HTTP errors | Draw calls | Notes |
|---|---|---|---|---|---|
| Work at a Pizza Place | ✅ | ✅ | 0 | 164 | spawn 65,0.8,-18 |
| Speed Run 4 | ✅ | ✅ | 0 | 79 | |
| Welcome to the Town of Robloxia | ✅ | ✅ | 0 | 98 | full map visible in overview |
| The Normal Elevator | ✅ | ✅ | 0 | 168 | |
| Mad Games | ✅ | ✅ | 0 | 171 | 402 CSG unions reported, not drawn |
| Flood Escape | ✅ | ✅ | 0 | 171 | |
| Natural Disaster Survival | ✅ | ✅ | 0 | 108 | |
| Contamination | ✅ | ✅ | 0 | 24 | |
| Base Wars | ✅ | ✅ | 0 | 24 | |
| Happy Home in Robloxia | ✅ | ✅ | 0 | 41 | |
| Rocket Fight Advanced | ✅ | ✅ | 0 | 5 | |
| ROBLOX Battle | ✅ | ✅ | 0 | 9 | |
| Martian Invasion | ✅ | ✅ | 0 | 9 | |
| Building with Friends | ✅ | ✅ | 0 | 7 | |

**14/14 PASS.** Screenshots: `checkpoints/screenshots/runtime-play-*.png`.
Reproduce with:

```bash
tools/browser/run-chromium.sh &                     # headless Chromium on :9222
.venv/bin/python tools/browser/validate_all_games.py --out-dir checkpoints/screenshots
```

### Fidelity ladder for this runtime

`parsed` → `geometry-exported` → **BROWSER-TESTED** (current) → REAL-CLIENT-TESTED (still
blocked: requires the genuine Windows client, docs/WINDOWS-REAL-CLIENT-VALIDATION.md).

## 7. Open verification items (found while building this)

1. **Wedge orientation is unresolved.** The definitive check (a part resting on a wedge's
   slope surface) was run statistically over all 7.1k wedge parts in the corpus and was
   inconclusive (side A 5150 vs side B 5378 hits — measurement noise, largely because the
   flat-corpus ramps have both floor neighbours at the same height). The runtime therefore
   draws the wedge with its vertical face on the part's **+Z** side and exposes a
   **"Flip wedge orientation"** toggle in the menu; **any screenshot showing a wedge can be
   corrected in one click, and neither variant is claimed to be verified.**
2. **Stud/inlet/universal textures** are approximations of the 2015 surface pattern, not the
   client's bitmaps.
3. **Lighting response curve.** The runtime mixes the place's Ambient/OutdoorAmbient with a
   hemispheric + directional model. It reproduces the 2015 flat-lit *look* but is not a
   numerically faithful reproduction of the 2015 lighting model.
4. **Terrain and CSG** remain unimplemented (reported, not faked).
5. `BrickColor` → RGB uses the historical palette table
   (`web/static/data/brickcolor.json`, generated from the public rbx-dom reference table); it is
   the palette, not a screenshot-verified 2015 rendering.
6. **Spawn resolution is BLOXEN's, not the 2015 engine's** — see §4. It uses only the place's
   own geometry, it is visible in the panel, and it is required precisely *because* scripted
   game logic does not run.

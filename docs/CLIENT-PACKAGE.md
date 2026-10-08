# THE 2015 CLIENT PACKAGE — REAL, VERIFIED, NOT EXECUTED

**Status: real client package ACQUIRED and VERIFIED. Execution = still BLOCKED (this is a
Linux cloud environment; the binary is a Windows PE and cannot be run here).**

This is the most important honesty line in the project: the game files, the client package
and its artwork are **real historical artefacts that have been hashed and verified**. What
runs in your browser is still BLOXEN's own runtime — a real renderer, but not Roblox's
2015 engine. It has never been REAL-CLIENT-TESTED, because that requires Windows.

## 1. What was acquired

| | |
|---|---|
| Package | WindowsPlayer `version-0d46087630eb46cd`, file version `0.205.0.61876` |
| Built | 23 July 2015 (matches the deployed date in `research/sources/setup-rbxcdn/DeployHistory.txt`) |
| Source | `github.com/KloBraticc/2015-Client`, path `July 23 (0.205.0.61876)/`, commit `7a0742cb900079d39c43e1113350338bff1f5a06` |
| Content | 771 files: the player executable, shaders, `content/`, `PlatformContent/`, DLLs, `ReflectionMetadata.xml` |
| Held in | `quarantine/client/version-0d46087630eb46cd/` — 659 committed files (38 MB). The 112 `PlatformContent/` DDS textures (93 MB) are hashed in the manifest but not committed |

## 2. Verification (this is the part that matters)

The project recorded `384a4cb3…120c8a44` as the expected SHA-256 of `RobloxPlayerBeta.exe`
long before any copy of the client was reachable, and marked it UNVERIFIED. It is now
verified against a real download:

| Check | Result |
|---|---|
| SHA-256 | `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44` — **exact match** |
| Size | 16,826,224 bytes |
| PE timestamp | 2015-07-23 19:45:30 UTC (build time; deploy was 23:33:45 PT the same day) |
| Version resource | `FileVersion 0.205.0.61876`, `ProductVersion 0.205.0.0` |
| Authenticode | present (6,512-byte certificate table) |
| Deploy history | `DeployHistory.txt`: *"New WindowsPlayer version-0d46087630eb46cd at 7/23/2015 11:33:45 PM, file version: 0, 205, 0, 61876"* |

Reproduce:

```bash
PYTHONPATH=server .venv/bin/python tools/verify_client_package.py
```

The same file is also published by `BrookenRecord/RobloxVersionArchive` and
`meowlyyy/RobloxVersionArchive`, so the identity of the build is corroborated across
independent archives.

## 3. What the package gives the project

The package is treated as **evidence, not as a program to run**. Order of business for
everything that came out of it: hash it, record where it came from, never execute it
(see docs/WINDOWS-REAL-CLIENT-VALIDATION.md §4 for the execution rules).

1. **The real material and surface bitmaps** — converted verbatim by
   `tools/import_client_assets.py` into `web/static/textures/client/` (19 material
   bitmaps + the 6-face default skybox), and used by the browser runtime instead of
   textures it used to draw itself. Provenance for each file (source path + source
   SHA-256) is in `web/static/data/client-textures.json`.
2. **`ReflectionMetadata.xml`** — the client's own class/property reflection dump. This is
   reference data for the descriptor table, superseding third-party API dumps.
3. **`content/fonts/*.rbxm`** — the real character models (R6 `character.rbxm`, R15
   `character3.rbxm`), the humanoid animation bundles, rocket/slingshot models.
4. **`content/sky/null_plainsky512_*.jpg`** — the default 2015 skybox.
5. **`shaders/source/*.hlsl`** — the real 2015 shader sources.

### Airbrushing out the guesswork: the surface atlas

`PlatformContent/pc/textures/studs.dds` is a 128×2048 atlas of **16 cells of 128×128**.
Measured by inspection (`tools/import_client_assets.py` + the images below):

| cells | contents |
|---|---|
| 0–3 | four "R" studs per cell |
| 4–7 | mixed: two "R" studs, two plain squares |
| 8–11 | four recessed square inlets |
| 12–15 | mixed, mirrored |

Each cell is a **2×2 arrangement**, so one cell spans **2 studs** — that is the measured
figure the runtime uses to scale it (`CELL_STUDS = 2` in `web/static/js/bloxen-client.js`).
The runtime's UVs are in studs, so the texture repeats once per 2 studs.

Examples: `checkpoints/client/atlas-cell-00-studs.png`,
`checkpoints/client/atlas-cell-08-inlets.png`, `checkpoints/client/studs-atlas.png`.

What is *not* measured and therefore still a BLOXEN choice: how many studs a material
bitmap (brick, wood, …) covers per tile. The runtime tiles them once per stud and says so
in the panel.

## 4. What is still NOT done

- **The real client has never been executed.** It is a Windows PE; running it needs a
  Windows machine and the controlled protocol in docs/WINDOWS-REAL-CLIENT-VALIDATION.md.
  Nothing in this project is REAL-CLIENT-TESTED.
- The protocol comparison items in that document (HTTP calls, RakNet framing, descriptor
  sync, SET_GLOBALS preamble, ID_DATA) remain unverified against the genuine client.
- `PlatformContent/` is not committed (93 MB of DDS). The manifest carries every hash, so
  the package can be completed and re-verified from the source archive at any time.

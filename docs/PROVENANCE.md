# BLOXEN — PROVENANCE

## Grading scale

| Grade | Meaning | Labeling |
|---|---|---|
| 1 | Preserved original | "preserved original" |
| 2 | Archived exact-date capture | "archived" |
| 3 | Archived near-date capture | "archived near-date" |
| 4 | Historically justified reconstruction | **"not original"** |
| 5 | Historical inference | **"not original"** |

Items at grade 4/5 are labeled as not original and never presented as preserved originals.
Everything in BLOXEN carries `provenance_grade`, `provenance_note`, `archive_source`, and a
verification status in the research DB.

## Research database

`data/research.db` — tables: `sources`, `captures`, `findings`, `verification_log`. Populated
by `tools/import_capture.py` (does not silently import unclassified material).

### Major source records

| Source | Type | Grade | Notes |
|---|---|---|---|
| DeployHistory mirror (setup-rbxcdn.github.io, `research/sources/setup-rbxcdn/`) | build history | 2 | target build entries |
| RobloxAPI/build-archive `API-Dump.json`/`ReflectionMetadata.xml` for `version-0d46087630eb46cd` | reflection data | 1–2 | exact target build |
| trade2015 CSS bundles + trade.html (via watrbx.xyz; capture from `alainbacu27/Roblox-2015TradeWebsite`) | website | CSS 1 / HTML 3 | documented revival-host caveat |
| `Intelinsidecom/Roblox-Webserver` Extras/HtmlDumps (2014–2016 page dumps) | website supporting | 3 | only public archived pages used; rest of repo (leaked dev sources) **rejected** |
| `DiscMil/AllCSS-ROBLOX` AllCSS-2012-era.css | website supporting | 1/3 | |
| `LuaGunsX/RobloxRBXLArchive` | games | 3 | 661 places + sidecar metadata |
| `beagleded/Roblox-Places-Archive` | games | 3 | NDS + 125 games |
| `xIcee/Economy-Simulator-ClientArchive` | catalog | 3 | captured product records; one contradictory record rejected |
| `KloBraticc/2015-Client` | client | 2 | AppSettings only; binaries unavailable |
| `setup-rbxcdn/setup-rbxcdn.github.io` | client builds | 2 | version history + launch manifests |
| `rojo-rbx/rbx-dom`, `Dekkonot/rbx-binary-format`, `TornadoCookie/OpenRBLX` (roblox.xsd) | format specs | 1–3 | importer authority |
| `Novetus_src`, `Roblox-Freedom-Distribution` | launcher/compat references | 3 | as reference only |
| Wayback Machine (wayback.saveweb…), web.archive.org | blocked/unreachable | — | fetches failed; noted |

### Rejected sources (leaks / private access / credential theft / exploit material)

`pekora-latest-src`, `kornet`, `athera-open-src-version`, `bubbablox-v2`, `OpenZekoro`,
`jrei2no9bgi43`, `SANS3R66/roblox-2016-source-code`, `lmaobamar/projectpizzacomplete`,
`Intelinsidecom/roblox-master-2016`, `TheCoderRaman/roblox-hitius-sourcecode`,
`anorrl/client`, `arcode1997/Roblox-2015-Client-src`, `arnav100/lua-roblox-source`,
`aviation-is-cool/FusionCore`, `gamingdannysmalls-sourcearchive`, and similar leak/exploit
repositories. **Never use.** Only the genuinely public archived-page folders
(Extras/HtmlDumps, CSS) were consulted; everything else in that repository was avoided.

### Discrepancies

- NDS records: LuaGunsX sidecar (Stickmasterluke + 7 badges) vs Economy-Simulator capture
  ("Tea", assetId 4883, UniverseId 27) → sidecar + independent corroboration wins; capture
  entry logged as discrepancy.
- 46156 "Dominus Messor": kept under captured name; ambiguous -> re-verify against captures.
- 43791 "Empyrean Reignment": kept under captured name; ambiguous spelling.

## Genuinely historical vs reconstructed — quick map

| Area | Historical | Reconstruction |
|---|---|---|
| Build identity | verified (3 sources) | — |
| Reflection data | original dump for exact build | — |
| CSS/layout | original bundles, evidenced dimensions | per-page body HTML (grade 4) |
| Catalog items | evidenced IDs/names | price at date mostly unevidenced |
| Games | preserved place files + sidecar metadata | game logic NOT running |
| Client binaries | unavailable (blocked) | launcher flow by design only |
| Wire protocol | observations listed in PROTOCOL.md | message IDs = placeholders |

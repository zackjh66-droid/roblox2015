# BLOXEN — ASSET RECOVERY

## Index

Every accepted place's external asset IDs are enumerated at import (textures, decals, meshes,
sounds, shirts, pants, faces, hats, models, animations) and registered in the `assets` table:

- `historical_asset_id`, `asset_type`, `name`, `source_url`, `local_path`, `sha256`
- `status`: **MISSING** / RECOVERED / REJECTED
- dependencies per game (`asset_dependencies`)

Current state (seeded from 7 preserved games): **609 unique external asset IDs referenced**
(639 place↔asset dependency rows). **15 recovered, 594 MISSING** — game pages show this
honestly ("N recovered / M referenced").

### Recovered so far (all grade 3, public preservation re-hosts)

| IDs | Type | Source | Notes |
|---|---|---|---|
| 10548108, 10730819, 11450310, 12517136, 15729251 | Sound (Ogg) | artemhao/OldRobloxSounds, RBXUser4132/novetus-assets | filenames = historical asset IDs |
| 1033714, 13073626, 15726506, 16646125, 16657069, 18813348, 21382712, 22589477, 42163552 | Mesh (classic `version 1.00` format) | RBXUser4132/novetus-assets | verified mesh headers |
| 53550245 | Texture (PNG) | RBXUser4132/novetus-assets | verified PNG magic |

Each is hash-registered in `assets` + `research` DB `sources` with retrieval date and source
URL. Rejected as historical: `Soliviant/Solivion-s-Archive-But-Readable` (modern Luau-era
personal collection), `volxten/VolxtensNovetusAssets` (name-organized music, not historical
IDs), `tajoma9x/rbxpack` (tooling only).

## Rules

1. **MISSING means MISSING.** No fake replacements are generated and called preserved.
2. Every recovered asset records: source, hash, type, date, provenance grade, dependent games.
3. Sources must be legitimate archives/public releases; leak/exploit-sourced material is
   REJECTED.

## Candidate recovery sources (investigated)

| Source | Status |
|---|---|
| `artemhao/OldRobloxSounds` (Novetus-oriented sound archive) | identified; bulk download blocked (GitHub token expired mid-session) — queued |
| `tajoma9x/rbxpack` (asset/project packs for old launchers) | identified; queued |
| `PressTpro/accesiblerevivalresources` (asset server + roblox.xsd) | repository content empty at check time |
| Place-file-embedded meshes (`SpecialMesh`/`CylinderMesh`/`BlockMesh` are procedural; `FileMesh`/`DataModelMesh` with `MeshId` reference external IDs) | parsed; IDs indexed |
| Roblox CDN (`assetdelivery.roblox.com`, `www.roblox.com/asset/?id=`) | **not used** — BLOXEN never proxies live Roblox services (security rule) |

## Asset service

`server/bloxen/assetsvc/` runs locally (127.0.0.1:8082): `GET /v1/asset/{id}` serves recovered
files or 404 with `{"status":"MISSING"}`; `/v1/asset/{id}/meta` returns provenance;
`/v1/status` reports recovery counts. The compat service's `/asset/` endpoint defers to it.

## Recovery log

`assets` rows + `research` DB `verification_log` entries record each recovery attempt.

---

# Browser delivery (2026-10-05)

## Recovered assets

`GET /asset/{id}` on the web service (browser-facing) mirrors the private asset service:
recovered file if the asset is RECOVERED **and** the file exists in this checkout, otherwise
`404 {"status":"MISSING"}`. Nothing is substituted. This matters for the client runtime: decal
and texture assets are only drawn when they are genuinely recovered.

## Missing historical imagery — the /images/ placeholder route

The preserved 2015 CSS bundles reference `/images/…` (Logo, NextStyleGuide sprite, Buttons,
Icons, Badges, spinners, …). Those files live on Roblox's origin and essentially none of them
survive in a legitimate archive.

`GET /images/{path}` therefore returns a 1×1 transparent SVG with:

```
X-Bloxen-Asset-Status: MISSING
X-Bloxen-Asset-Path: /images/…
```

so the page keeps its historical layout metrics without fabricating artwork, and the response
itself states that the asset is missing. The interface substitutes:

- **wordmark**: the preserved `.logo-transitional` 30×30 logo slot is filled with the BLOXEN
  wordmark (same box metrics as the historical CSS) — see `web/static/css/bloxen.css`
- **Roblox trademark imagery is deliberately never reproduced** (logo "R" marks and the 2015
  navigation sprite are suppressed in `bloxen.css`)
- **fonts**: the 2015 bundles load Source Sans Pro from `themes.googleusercontent.com`, which no
  longer serves those files; the same typeface (SIL OFL 1.1) is served locally from
  `web/static/fonts/`. Failed requests to that dead CDN are treated as expected-missing by the
  validation tooling, not as runtime errors.

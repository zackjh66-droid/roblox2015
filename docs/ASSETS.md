# BLOXEN — ASSET RECOVERY

## Index

Every accepted place's external asset IDs are enumerated at import (textures, decals, meshes,
sounds, shirts, pants, faces, hats, models, animations) and registered in the `assets` table:

- `historical_asset_id`, `asset_type`, `name`, `source_url`, `local_path`, `sha256`
- `status`: **MISSING** / RECOVERED / REJECTED
- dependencies per game (`asset_dependencies`)

Current state (seeded from 7 preserved games): **889 external asset IDs referenced,
0 recovered, 889 MISSING**. Game pages show this honestly ("0 recovered / N referenced").

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

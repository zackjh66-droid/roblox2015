# BLOXEN — CATALOG

## Evidence

Catalog records come from captured catalog API responses preserved in
[xIcee/Economy-Simulator-ClientArchive](https://github.com/xIcee/Economy-Simulator-ClientArchive)
(`11166~2.json`, `4005~2.json` — CollectionsItems captures). Item IDs in these captures
corroborate independent historical knowledge of classic catalog IDs. Grade **3
(archived near-date evidence)**; price-at-target-date is **not** claimed where the captures
show `null`.

**Discarded capture record:** the same archive contains an "Natural Disaster Survival" entry
(creator "Tea", assetId 4883, UniverseId 27) that contradicts other sources; it is recorded
in the research DB as a discrepancy and **not used**.

## Seeded items (12, all evidenced)

| Historical asset ID | Name | Type | Price (target date) | Limited | Provenance |
|---|---|---|---|---|---|
| 31521 | Red Roblox Cap | Hat | not evidenced (historically free) | no | capture + corroboration |
| 11979 | Workclock Headphones | Hat | unevidenced | no | capture |
| 20856 | Fiery Egg of Egg Testing | Hat | unevidenced | limited | capture |
| 45651 | Hiccup's (Improved) Helmet | Hat | unevidenced | no | capture |
| 45619 | Black Pointy Fluffy Ears | Hat | unevidenced | no | capture |
| 43791 | Empyrean Reignment | Hat | unevidenced | no | capture (name as captured) |
| 45846 | Green Sparkle Time Fedora | Hat | unevidenced | limited-unique | capture |
| 27214 | Archduchess of the Federation | Hat | unevidenced | limited-unique | capture |
| 20854 | Dominus Vespertilio | Hat | unevidenced | limited | capture |
| 31616 | Supa Fly Cap | Hat | unevidenced | limited | capture |
| 51277 | Duchess of the Federation | Hat | unevidenced | limited-unique | capture |
| 46156 | Dominus Messor | Hat | unevidenced | limited | capture |

**Do not invent catalog filler.** Shirts/pants/T-shirts/faces/gear will be added only when
evidenced records are found. Price fields stay NULL with `provenance_note` explaining.

## Functional flow (tested end-to-end)

Catalog → acquire → Inventory ("My Stuff") → Character (equip) → avatar state in DB →
CharacterFetch compat endpoint → game character configuration.

Thumbnails: MISSING (no recovered thumbnail assets yet) — shown as labeled missing, never
fabricated.

## Item schema

`items` table stores: historical_asset_id (unique), name, description, creator, item_type,
price_robux, price_tix, is_limited, created_date, thumbnail_path, archive_source,
provenance_grade, provenance_note.

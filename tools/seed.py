"""Seed BLOXEN databases with evidence-backed historical content.

Rules:
- historical content only when evidence exists (provenance grade recorded)
- nothing invented is labeled original
- MISSING stays MISSING
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from bloxen import config, db, security          # noqa: E402
from bloxen import research_db as rdb            # noqa: E402
from bloxen.importer.pipeline import import_place  # noqa: E402

RESEARCH_NOTES = config.RESEARCH / "notes"


def seed_research():
    con = rdb.connect()
    rdb.init_db(con)

    def src(**kw):
        return rdb.add_source(con, **kw)

    s_api = src(title="RobloxAPI/build-archive API-Dump for version-0d46087630eb46cd",
                url="https://github.com/RobloxAPI/build-archive (data/legacy/builds/version-0d46087630eb46cd/API-Dump.json)",
                archive_timestamp="git history", target_date="2015-07-23",
                content_type="api-dump", historical_entity="WindowsPlayer 0.205.0.61876",
                local_path="research/sources/build-archive/version-0d46087630eb46cd/API-Dump.json",
                grade="2", verification_state="cross-checked",
                notes="332 classes matches genuine-client descriptor observation")
    src(title="DeployHistory.txt mirror (setup-rbxcdn)", 
        url="https://github.com/setup-rbxcdn/setup-rbxcdn.github.io (DeployHistory.txt)",
        target_date="2015-07-23", content_type="deploy-history",
        historical_entity="WindowsPlayer version-0d46087630eb46cd",
        local_path="research/sources/setup-rbxcdn/DeployHistory.txt",
        grade="2", verification_state="cross-checked",
        notes="Line 1774: New WindowsPlayer version-0d46087630eb46cd at 7/23/2015 11:33:45 PM, file version 0,205,0,61876")
    src(title="setup-rbxcdn version-history WindowsPlayer.json",
        url="https://github.com/setup-rbxcdn/setup-rbxcdn.github.io (version-history/Windows/WindowsPlayer.json)",
        target_date="2015-07-23", content_type="version-history",
        historical_entity="0.205.0.61876 -> version-0d46087630eb46cd",
        grade="2", verification_state="cross-checked")
    src(title="RobloxAPI/build-archive legacy metadata.json",
        url="https://github.com/RobloxAPI/build-archive (data/legacy/metadata.json)",
        target_date="2015-07-23", content_type="metadata",
        historical_entity="GUID version-0d46087630eb46cd Date 2015-07-23T23:33:45-07:00",
        grade="2", verification_state="cross-checked")
    src(title="Preserved 2015-era CSS bundle (main___7000c43d73500e63554d81258494fa21_m.css)",
        url="https://github.com/alainbacu27/Roblox-2015TradeWebsite (css/)",
        target_date="2015", content_type="css",
        historical_entity="Roblox web CSS bundle with original ~/CSS/Base/CSS/*.css path comments",
        local_path="research/sources/website/trade2015/css/main_m.css", grade="1",
        verification_state="unverified",
        notes="path comments preserved; era-fit assessed against 2015 page captures")
    src(title="Preserved 2015-era CSS bundle (page___454963b97fe545e3b3f2aaf85eef6d4a_m.css)",
        url="https://github.com/alainbacu27/Roblox-2015TradeWebsite (css/)",
        target_date="2015", content_type="css",
        historical_entity="Roblox web page CSS bundle",
        local_path="research/sources/website/trade2015/css/page_m.css", grade="1")
    src(title="AllCSS.ashx archival (2012-era bundle)",
        url="https://github.com/DiscMil/AllCSS-ROBLOX", target_date="2012-03",
        content_type="css", historical_entity="Roblox AllCSS.ashx",
        local_path="research/sources/website/AllCSS-2012-era.css", grade="1",
        notes="Near-date CSS; used only as supporting layout evidence")
    src(title="Archived 2015 trade page HTML (structure evidence)",
        url="https://github.com/alainbacu27/Roblox-2015TradeWebsite (trade.html)",
        target_date="2015", content_type="html",
        historical_entity="2015-era page shell: #header/.rbx-header, #navContent, #MasterContainer, #BodyWrapper, universal search",
        local_path="research/sources/website/trade-2015.html", grade="3",
        notes="capture served by a revival host (watrbx.xyz) in 2015 style; structure + CSS refs treated as near-date evidence, not original")
    src(title="Roblox XML schema (roblox.xsd)",
        url="https://github.com/TornadoCookie/OpenRBLX (staticdata/roblox.xsd)",
        content_type="schema", historical_entity="RBXLX/RBXMX XML schema v2.0 (authored Erik Cassel / Roblox)",
        local_path="research/sources/formats/roblox.xsd", grade="1")
    src(title="rbx-binary-format reader source (format reference)",
        url="https://github.com/Dekkonot/rbx-binary-format", content_type="format-reference",
        historical_entity="RBXL/RBXM binary chunk + datatype layout",
        local_path="research/sources/formats/rbx-binary-format/", grade="1",
        verification_state="cross-checked",
        notes="type ids 0x01..0x1d; interleaved int arrays; rotated floats; LZ4 chunks")
    src(title="Catalog item captures (CollectionsItems JSON)",
        url="https://github.com/xIcee/Economy-Simulator-ClientArchive (11166~2.json, 4005~2.json)",
        content_type="catalog-capture",
        historical_entity="Red Roblox Cap 31521, Workclock Headphones 11979, Dominus Vespertilio 20854, GSTF 45846, Dominus Messor 46156, ...",
        local_path="research/sources/catalog/", grade="3",
        verification_state="cross-checked",
        notes="item IDs corroborated against independent historical knowledge; NDS record in same capture contradicts other sources (creator 'Tea', id 4883) and is NOT used")

    places = {
        "Work at a Pizza Place (2014L)": ("Dued1", "WAAPP 2014 version, era-matched to target date"),
        "Speed Run 4 (1st part)": ("Vurse", "Speed Run 4 first part"),
        "Welcome to the Town of Robloxia": ("1dev2", "Town of Robloxia"),
        "The Normal Elevator - Fixed for 2015M": ("NowDoTheHarlemShake", "community-modified copy ('Fixed for 2015M') — provenance reflects modification"),
        "Mad Games (v1.3b, 2015)": ("loleris", "Mad Games v1.3b 2015"),
        "Flood Escape (July 8th, 2015, V1.6.5)": ("Crazyblox", "Flood Escape July 8 2015 — exact era match"),
        "Natural Disaster Survival": ("Stickmasterluke", "beagleded/Roblox-Places-Archive copy; no sidecar metadata; creator from historical record"),
    }
    for name, (creator, note) in places.items():
        p = config.QUARANTINE / "places" / f"{name}.rbxl"
        meta = config.QUARANTINE / "places" / f"{name}.meta.json"
        sha = rdb.sha256_file(p) if p.exists() else None
        src(title=f"Place file: {name}",
            url="https://github.com/LuaGunsX/RobloxRBXLArchive" if "Natural" not in name
                else "https://github.com/beagleded/Roblox-Places-Archive",
            content_type="place-file", historical_entity=f"{name} by {creator}",
            local_path=str(p), sha256=sha, grade="3",
            verification_state="hash-verified" if sha else "unverified",
            notes=note)
        if meta.exists():
            src(title=f"Place metadata: {name}", url="same as place file",
                content_type="place-metadata", historical_entity=f"{name} badges/creator",
                local_path=str(meta), grade="3", verification_state="cross-checked",
                notes=f"creator record: {creator}")

    rdb.log_verification(con, "WindowsPlayer 0.205.0.61876 = version-0d46087630eb46cd",
                         "3-source cross-check (DeployHistory mirror, build-archive metadata, setup-rbxcdn history)",
                         "PASS", "DeployHistory line 1774 + metadata date 2015-07-23T23:33:45-07:00")
    rdb.log_verification(con, "API dump descriptor counts",
                         "count classes/properties/events in build-archive dump",
                         "PASS", "332 classes (matches genuine observation); inherited-member materialization tracks 968/320")
    con.close()


GAMES = [
    dict(name="Work at a Pizza Place", creator="Dued1", historical_place_id=None,
         genre="All", file="Work at a Pizza Place (2014L).rbxl",
         desc="2014L version of Dued1's classic. Preserved place file with sidecar badge metadata.",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json (creator Dued1). Era-matched (2014L sits within the target window). Scripts inventoried, not executed."),
    dict(name="Speed Run 4", creator="Vurse", historical_place_id=None,
         genre="All", file="Speed Run 4 (1st part).rbxl",
         desc="Vurse's Speed Run 4 (first part).",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json (creator Vurse)."),
    dict(name="Welcome to the Town of Robloxia", creator="1dev2", historical_place_id=None,
         genre="All", file="Welcome to the Town of Robloxia.rbxl",
         desc="1dev2's Town of Robloxia.",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json (creator 1dev2, badge IDs preserved)."),
    dict(name="The Normal Elevator", creator="NowDoTheHarlemShake", historical_place_id=None,
         genre="All", file="The Normal Elevator - Fixed for 2015M.rbxl",
         desc="The Normal Elevator — community copy adjusted for 2015M clients.",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json. NOTE: filename marks this copy as 'Fixed for 2015M' (community-modified) — not the untouched original."),
    dict(name="Mad Games", creator="loleris", historical_place_id=None,
         genre="All", file="Mad Games (v1.3b, 2015).rbxl",
         desc="Mad Games v1.3b (2015).",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json (creator loleris). Version label v1.3b 2015."),
    dict(name="Flood Escape", creator="Crazyblox", historical_place_id=None,
         genre="All", file="Flood Escape (July 8th, 2015, V1.6.5).rbxl",
         desc="Flood Escape V1.6.5 — saved 8 July 2015, two weeks before the target date.",
         prov=3, note="LuaGunsX/RobloxRBXLArchive + meta.json (creator Crazyblox). Near-exact era match."),
    dict(name="Natural Disaster Survival", creator="Stickmasterluke", historical_place_id=None,
         genre="All", file="Natural Disaster Survival.rbxl",
         desc="Natural Disaster Survival (preserved copy).",
         prov=3, note="beagleded/Roblox-Places-Archive (no sidecar metadata). Creator attribution from historical record (grade 3)."),
]

CATALOG = [
    # (hist_id, name, type, price_robux, price_tix, limited, note)
    (31521, "Red Roblox Cap", "Hat", None, None, 0, "captured CollectionsItems record; classic free cap"),
    (11979, "Workclock Headphones", "Hat", None, None, 0, "captured record"),
    (20856, "Fiery Egg of Egg Testing", "Hat", None, None, 1, "captured record (limited)"),
    (45651, "Hiccup's (Improved) Helmet", "Hat", None, None, 0, "captured record"),
    (45619, "Black Pointy Fluffy Ears", "Hat", None, None, 0, "captured record"),
    (43791, "Empyrean Reignment", "Hat", None, None, 0, "captured record (name as captured)"),
    (45846, "Green Sparkle Time Fedora", "Hat", None, None, 1, "captured record (limited-unique)"),
    (27214, "Archduchess of the Federation", "Hat", None, None, 1, "captured record (limited-unique)"),
    (20854, "Dominus Vespertilio", "Hat", None, None, 1, "captured record (limited)"),
    (31616, "Supa Fly Cap", "Hat", None, None, 1, "captured record (limited)"),
    (51277, "Duchess of the Federation", "Hat", None, None, 1, "captured record (limited-unique)"),
    (46156, "Dominus Messor", "Hat", None, None, 1, "captured record (limited)"),
]


def seed_app():
    con = db.init()
    # research files' asset enumeration per game is done in import step
    for g in GAMES:
        path = config.QUARANTINE / "places" / g["file"]
        if not path.exists():
            print(f"[seed] MISSING place file {g['file']}")
            continue
        sha = security.token_hash  # placeholder to keep import light
        import hashlib
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        existing = con.execute("SELECT id FROM games WHERE name=?", (g["name"],)).fetchone()
        if existing:
            game_id = existing["id"]
            con.execute(
                "UPDATE games SET place_path=?, place_sha256=?, provenance_note=?, compatibility_status=? WHERE id=?",
                (str(path), h, g["note"], "imported", game_id))
        else:
            cur = con.execute(
                """INSERT INTO games (name, creator, description, genre, place_path, place_sha256,
                   provenance_grade, provenance_note, compatibility_status, historical_place_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (g["name"], g["creator"], g["desc"], g["genre"], str(path), h,
                 g["prov"], g["note"], "imported", g["historical_place_id"]))
            game_id = cur.lastrowid
        # sidecar meta: record badges as provenance
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            badges = ", ".join(f"{b['ID']}:{b['Name']}" for b in meta.get("Badges", []))
            con.execute("INSERT INTO game_versions (game_id, version_label, notes) VALUES (?,?,?)",
                        (game_id, "sidecar meta", f"creator={meta.get('Creator')}; badges={badges}"))

    for hid, name, itype, prx, tix, limited, note in CATALOG:
        con.execute(
            """INSERT INTO items (historical_asset_id, name, description, creator, item_type,
               price_robux, price_tix, is_limited, archive_source, provenance_grade, provenance_note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(historical_asset_id) DO NOTHING""",
            (hid, name, "", "ROBLOX", itype, prx, tix, limited,
             "xIcee/Economy-Simulator-ClientArchive captures", 3, note))
    con.commit()
    con.close()


def import_all():
    con = db.init()
    for g in GAMES:
        path = config.QUARANTINE / "places" / g["file"]
        if not path.exists():
            continue
        row = con.execute("SELECT id, place_imports_done FROM (SELECT id, 0 AS place_imports_done FROM games WHERE name=?)", (g["name"],)).fetchone()
        if not row:
            continue
        game_id = row["id"]
        existing = con.execute("SELECT id FROM place_imports WHERE source_path=?", (str(path),)).fetchone()
        if existing:
            continue
        print(f"[import] {g['name']} ...")
        res = import_place(path)
        m = res["meta"]
        con.execute(
            """INSERT INTO place_imports (source_path, sha256, format, class_counts,
               external_asset_ids, service_report, script_inventory, accepted)
               VALUES (?,?,?,?,?,?,?,1)""",
            (m["source_path"], m["sha256"], m["format"], json.dumps(m["class_counts"]),
             json.dumps(m["external_asset_ids"]), json.dumps(m["service_report"]),
             json.dumps(m["script_inventory"])))
        # register assets (MISSING until recovery) + dependencies
        for a in m["external_asset_ids"]:
            try:
                aid = int(a)
            except ValueError:
                continue
            con.execute("INSERT OR IGNORE INTO assets (historical_asset_id, asset_type, status) VALUES (?, 'Unknown', 'MISSING')", (aid,))
            asset_row = con.execute("SELECT id FROM assets WHERE historical_asset_id=?", (aid,)).fetchone()
            con.execute("INSERT OR IGNORE INTO asset_dependencies (game_id, asset_id) VALUES (?, ?)",
                        (game_id, asset_row["id"]))
        con.execute("UPDATE games SET compatibility_status='parsed' WHERE id=?", (game_id,))
        con.commit()
        print(f"[import]   instances={m['instance_count']} scripts={len(m['script_inventory'])} "
              f"external-assets={len(m['external_asset_ids'])}")
    con.close()


if __name__ == "__main__":
    print("== seeding research db")
    seed_research()
    print("== seeding app db")
    seed_app()
    print("== importing places")
    import_all()
    print("done")

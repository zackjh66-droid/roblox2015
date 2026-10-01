"""Populate the BLOXEN research database with source records and graded claims.

Idempotent: skips titles already recorded.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from bloxen import research_db as rdb

SOURCES = [
    # --- target build identity ---
    dict(title="DeployHistory.txt mirror (setup-rbxcdn.github.io)",
         url="https://github.com/setup-rbxcdn/setup-rbxcdn.github.io",
         archive_timestamp="2025-03-18", target_date="2015-07-23",
         content_type="build-history",
         historical_entity="WindowsPlayer 0.205.0.61876 / version-0d46087630eb46cd",
         local_path="research/sources/setup-rbxcdn/DeployHistory.txt",
         grade="2", verification_state="verified",
         notes="line 1774: WindowsPlayer version-0d46087630eb46cd at 7/23/2015 23:33:45 PM, file version 0.205.0.61876"),
    dict(title="RobloxAPI build-archive reflection data for version-0d46087630eb46cd",
         url="https://github.com/RobloxAPI/build-archive",
         archive_timestamp="2025", target_date="2015-07-23",
         content_type="reflection",
         historical_entity="API-Dump.json / ReflectionMetadata.xml for the exact target build",
         local_path="research/sources/build-archive/version-0d46087630eb46cd/API-Dump.json",
         grade="1", verification_state="verified",
         notes="332 classes; 851 direct property members; matches genuine-client descriptor class count"),
    dict(title="RobloxApp version manifest (target build)",
         url="https://github.com/setup-rbxcdn/setup-rbxcdn.github.io",
         archive_timestamp="2025-03-18", target_date="2015-07-23",
         content_type="manifest", historical_entity="RobloxApp20150723T233345Z.version-0d46087630eb46cd.json",
         grade="2", verification_state="verified",
         notes="client package manifest; binaries unobtainable in this environment"),
    # --- website ---
    dict(title="2015-era CSS bundle main___7000c43d…m.css",
         url="https://github.com/alainbacu27/Roblox-2015TradeWebsite",
         archive_timestamp="2023-01-01", target_date="2015-07-23",
         content_type="css", historical_entity="2015 Roblox web CSS",
         local_path="research/sources/website/trade2015/css/main_m.css",
         grade="1", verification_state="verified",
         notes="original bundle; ~/CSS/Base/CSS/Roblox.css path comments preserved"),
    dict(title="2015-era CSS bundle page___454963b9…m.css",
         url="https://github.com/alainbacu27/Roblox-2015TradeWebsite",
         archive_timestamp="2023-01-01", target_date="2015-07-23",
         content_type="css", historical_entity="2015 Roblox web page CSS",
         local_path="research/sources/website/trade2015/css/page_m.css",
         grade="1", verification_state="verified", notes="original bundle"),
    dict(title="2015 trade page HTML capture (trade.html)",
         url="https://github.com/alainbacu27/Roblox-2015TradeWebsite",
         archive_timestamp="2023-01-01", target_date="2015-07-23",
         content_type="html", historical_entity="2015 Trade/Transactions page",
         local_path="research/sources/website/trade-2015.html",
         grade="3", verification_state="partially-verified",
         notes="capture served by revival host watrbx.xyz (documented caveat); header/nav/structure used; 2015 nav = Games/Catalog/Develop/ROBUX"),
    dict(title="AllCSS.ashx 2012-era bundle",
         url="https://github.com/DiscMil/AllCSS-ROBLOX",
         archive_timestamp="2021", target_date="2012-01-01",
         content_type="css", historical_entity="AllCSS-2012-era.css",
         local_path="research/sources/website/AllCSS-2012-era.css",
         grade="3", verification_state="partually-verified", notes="supporting evidence only"),
    # --- games ---
    dict(title="LuaGunsX/RobloxRBXLArchive",
         url="https://github.com/LuaGunsX/RobloxRBXLArchive",
         archive_timestamp="2025-10", target_date="2014-2015",
         content_type="places", historical_entity="661 RBXL places + sidecar metadata",
         local_path="quarantine/places/",
         grade="3", verification_state="partually-verified",
         notes="sidecar .meta.json creators+badges cross-checked; 6 games accepted into BLOXEN"),
    dict(title="beagleded/Roblox-Places-Archive",
         url="https://github.com/beagleded/Roblox-Places-Archive",
         archive_timestamp="2025-10", target_date="2007-2015",
         content_type="places", historical_entity="125 RBXL places + Natural Disaster Survival",
         local_path="quarantine/places/Natural Disaster Survival.rbxl",
         grade="3", verification_state="partially-verified",
         notes="README warns untested; NDS accepted with creator attribution Stickmasterluke (grade 3)"),
    # --- catalog ---
    dict(title="xIcee/Economy-Simulator-ClientArchive catalog captures",
         url="https://github.com/xIcee/Economy-Simulator-ClientArchive",
         archive_timestamp="2025", target_date="2015-07-23",
         content_type="catalog-api", historical_entity="CollectionsItems/product API captures",
         local_path="research/sources/catalog/11166~2.json",
         grade="3", verification_state="partially-verified",
         notes="12 items seeded; prices null at target date; contradictory NDS record rejected"),
    # --- formats ---
    dict(title="rojo-rbx/rbx-dom + Dekkonot/rbx-binary-format",
         url="https://github.com/rojo-rbx/rbx-dom",
         archive_timestamp="2025", target_date=None,
         content_type="format-spec", historical_entity="RBXL binary chunk format",
         local_path="research/sources/formats/rbx-binary-format/",
         grade="2", verification_state="verified",
         notes="importer implementation authority: chunks META/SSTR/INST/PROP/PRNT/END; zigzag+delta referents; rotated floats"),
    dict(title="roblox.xsd (official RBXLX schema, from TornadoCookie/OpenRBLX)",
         url="https://github.com/TornadoCookie/OpenRBLX",
         archive_timestamp="2025", target_date=None,
         content_type="format-spec", historical_entity="roblox.xsd",
         local_path="research/sources/formats/roblox.xsd",
         grade="1", verification_state="verified",
         notes="authored by Erik Cassel / Roblox; XML place format authority"),
    # --- client / launcher references ---
    dict(title="KloBraticc/2015-Client (AppSettings for target version)",
         url="https://github.com/KloBraticc/2015-Client",
         archive_timestamp="2025-10", target_date="2015-07-23",
         content_type="client-settings", historical_entity="AppSettings.xml",
         local_path="research/sources/client-settings/AppSettings.xml",
         grade="2", verification_state="partially-verified",
         notes="binaries not included; claimed SHA-256 384a4cb3… recorded but UNVERIFIED; archive.roblonium.com mirror unreachable"),
    dict(title="Novetus_src + Roblox-Freedom-Distribution",
         url="https://github.com/Bitl/Novetus_src",
         archive_timestamp="2025", target_date=None,
         content_type="launcher-reference", historical_entity="legacy launcher conventions",
         grade="3", verification_state="partially-verified",
         notes="as engineering reference for launch/compat surface only"),
]

CLAIMS = [
    ("client", "WindowsPlayer 0.205.0.61876 = version-0d46087630eb46cd, deployed 2015-07-23T23:33:45-07:00", "2", "verified"),
    ("client", "332 classes in the target-build API dump match the genuine-client descriptor class count", "1", "verified"),
    ("client", "genuine wire descriptor counts observed: 968 properties / 320 events / 182 types (counting semantics open)", "2", "open"),
    ("client", "SET_GLOBALS has a 121-bit Workspace preamble; correct decode = 22 top containers; first class 231 = ReplicatedFirst", "2", "verified"),
    ("client", "claimed client SHA-256 384a4cb3…0c8a44 is UNVERIFIED (binaries unobtainable)", "3", "open"),
    ("protocol", "RakNet transport, protocol 31", "2", "verified"),
    ("protocol", "authoritative server→client ID_DATA is the observed blocker; implemented + SIMULATOR-TESTED in BLOXEN", "2", "open"),
    ("protocol", "legacy Huffman string behavior identified on genuine wire; not yet implemented", "2", "open"),
    ("website", "2015 nav = Games, Catalog, Develop, ROBUX + universal search; container 970px; Source Sans Pro", "3", "verified"),
    ("games", "Work at a Pizza Place place file (2014L) authored by Dued1 — sidecar creator + badge metadata", "3", "verified"),
    ("games", "Hide and Seek Extreme place file not found in legitimate public sources — MISSING", "3", "verified"),
    ("catalog", "12 catalog items seeded from captured product records; price-at-target-date mostly unevidenced", "3", "partially-verified"),
]


def main():
    con = rdb.connect()
    try:
        rdb.init_db(con)
    except Exception:
        pass
    have = {r["title"] for r in con.execute("SELECT title FROM sources")}
    added = 0
    for s in SOURCES:
        if s["title"] in have:
            continue
        if s.get("local_path"):
            p = ROOT / s["local_path"]
            if p.is_file():
                s["sha256"] = rdb.sha256_file(p)
        rdb.add_source(con, **s)
        added += 1
    for topic, claim, grade, state in CLAIMS:
        rdb.add_claim(con, topic=topic, claim=claim, grade=grade, state=state)
    con.commit()
    n_src = con.execute("SELECT count(*) FROM sources").fetchone()[0]
    n_cl = con.execute("SELECT count(*) FROM claims").fetchone()[0]
    print(f"sources={n_src} (added {added}) claims={n_cl}")


if __name__ == "__main__":
    main()

# Checkpoint — 2026-10-01 — Full E2E suite green

## State
- pytest tests/: **16 passed** (9 unit + 7 full-stack E2E)
- E2E drives live services (web 8080, compat 8081, assets 8082, game udp/53640):
  register → login → catalog browse → purchase → inventory → avatar equip → profile →
  friends → messages → Play ticket (single-use) → simulator: ticket validate →
  compat negotiate/visit/placelauncher/characterfetch → RakNet handshake → protocol 31 →
  descriptor sync (332 classes) → SET_GLOBALS (121-bit preamble / 22 containers /
  ReplicatedFirst 231) → ID_DATA (world + player tree).
- Game server startup ~0.0s via data/world_cache.json (place parse cached by SHA-256).
- Research DB: 62 sources + 12 claims, grades 1–5, verification states recorded.

## Fixes in this session (wire bugs found by instrumented simulator debugging)
1. RakNet reliability_flags must be 0–4 (3=RELIABLE_ORDERED), NOT a flag byte (0x11 overflowed).
2. SPLIT_FLAG must be bit 4 (0x10); bits 5–7 are the reliability field.
3. Frame payload bitlen is u16 BITS — max 8191 bytes/frame; split at 1200B.
4. Descriptor sync = ONE logical message via split frames (not 51 messages).
5. ID_CONNECTION_REQUEST_ACCEPTED is frame-wrapped — accept inside frame dispatch.
6. 4MB socket buffers + send throttling (asyncio.sleep(0) every 32 parts) needed for 838KB ID_DATA.
7. World cache keyed by place SHA-256 (re-parse only on change).

## Deliverables
- docs/: ARCHITECTURE, CLIENT, WEBSITE, GAMES, CATALOG, ASSETS, PROTOCOL, PROVENANCE,
  WINDOWS-REAL-CLIENT-VALIDATION
- tools/: seed.py, import_capture.py, populate_research_db.py, browser/cdp.py
- quarantine/places/ + web/ + server/bloxen/ (importer, gameserver, compat, assetsvc,
  launcher, simulator)

## Open / blocked
- Genuine client package: CDN unreachable → REAL WINDOWS CLIENT EXECUTION = BLOCKED
- Claimed client SHA-256 UNVERIFIED
- Byte-level wire message IDs = placeholders (await genuine capture)
- Legacy Huffman strings not implemented
- Asset recovery 0/889 (all MISSING, honestly labeled)
- GH_TOKEN expired mid-session → further GitHub downloads/pushes blocked until reconnected

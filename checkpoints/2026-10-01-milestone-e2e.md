# Checkpoint — 2026-10-01 — Full E2E suite green

## State
- pytest tests/: **17 passed** (9 unit + 8 full-stack E2E)
- E2E drives live services (web 8080, compat 8081, assets 8082, game udp/53640):
  register → login → catalog browse → purchase → inventory → avatar equip → profile →
  friends → messages → settings → favorites → Play ticket (single-use) → simulator:
  ticket validate → compat negotiate/visit/placelauncher/characterfetch → RakNet handshake →
  protocol 31 → descriptor sync (332 classes) → SET_GLOBALS (121-bit preamble / 22 containers /
  ReplicatedFirst 231) → ID_DATA (2,520 instances + player tree).
- Simulator CLI (`python -m bloxen.simulator.client -v`): 11/11 steps PASS.
- Game server startup ~0.0s via data/world_cache.json (place parse cached by SHA-256).
- Research DB: 62+ sources / 12 graded claims, grades 1–5, verification states recorded.

## This session
1. RakNet wire bugs fixed & verified (reliability enum, split flag bit 4, u16 bitlen,
   split-frame single-message sync, frame-wrapped accept, 4MB buffers + send throttle).
2. Asset recovery: **15 RECOVERED** (9 classic meshes `version 1.00`, 5 Ogg sounds,
   1 PNG texture) from public preservation re-hosts; 594 MISSING (honest).
   Registered with SHA-256 + provenance in assets + research DB.
3. Per-game gameplay requirements: static scan of 1,514 scripts / 3.5 MB Lua
   (never executed) → research/db/gameplay_requirements.json; all games playable=False.
4. Visual validation: screenshot pipeline fixed (single visible target + screencast +
   bringToFront + load events + DOM sidecars); historical CSS metrics extracted
   (.navbar-brand 20px/30px, logo slot 76px+12px margins); logo collision fixed.
5. Bugs found by browser tests & fixed: /User.aspx own-profile redirect; search q alias +
   Enter key.
6. Docs complete: ARCHITECTURE, CLIENT, WEBSITE, GAMES, CATALOG, ASSETS, PROTOCOL,
   PROVENANCE, WINDOWS-REAL-CLIENT-VALIDATION.

## Open / blocked
- Genuine client package: CDN unreachable → REAL WINDOWS CLIENT EXECUTION = BLOCKED
- Claimed client SHA-256 UNVERIFIED
- Byte-level wire message IDs = placeholders (await genuine capture)
- Legacy Huffman strings not implemented
- Asset recovery 15/609 — continue opportunistically
- Historical logo/thumbnail images: MISSING (labeled, never fabricated)

# BLOXEN — CLIENT

**Target Windows Player:** `0.205.0.61876`  
**Version GUID:** `version-0d46087630eb46cd`  
**Target date:** 23 July 2015

## Version verification (cross-checked, 3 independent sources)

| Source | Evidence | Grade |
|---|---|---|
| DeployHistory mirror (setup-rbxcdn/setup-rbxcdn.github.io `DeployHistory.txt`, local: `research/sources/setup-rbxcdn/DeployHistory.txt`) | Line 1774: `New WindowsPlayer version-0d46087630eb46cd at 7/23/2015 11:33:45 PM, file version: 0, 205, 0, 61876...Done!` | 2 (archived) |
| RobloxAPI/build-archive `data/legacy/metadata.json` | `{"GUID": "version-0d46087630eb46cd", "Date": "2015-07-23T23:33:45-07:00", "Version": "0.205.0.61876"}` | 2 |
| setup-rbxcdn `version-history/Windows/WindowsPlayer.json` | `"0.205.0.61876": "version-0d46087630eb46cd"` | 2 |

**Status: VERIFIED** — version number, GUID, and timestamp agree across all three.

## Reflection data for the exact target build (ORIGINAL, grade 1-2)

`research/sources/build-archive/version-0d46087630eb46cd/`:
- `API-Dump.json` (737,858 B) — **332 classes**, 851 direct property members, 266 direct events, 699 functions, 12 callbacks, 124 enums
- `API-Dump.txt` (154,247 B)
- `ReflectionMetadata.xml` (195,188 B)

The **332 classes** figure exactly matches the genuine-client descriptor-synchronization
observation. The observed wire counts (968 properties / 320 events / 182 types) exceed the
dump's direct-member counts; they include inherited/hidden network descriptors. BLOXEN
materializes inherited members (4,988/2,940/96 serialized) and records the genuine counts as
the comparison target in `server/bloxen/gameserver/descriptors.py::observed_wire_counts()`.
Exact wire counting semantics remain an **open verification item** against a genuine-client
capture (docs/PROTOCOL.md).

## Client package acquisition

**Status: CLIENT PACKAGE DOWNLOAD = BLOCKED in this environment.**

- Official CDN hosts (`setup.roblox.com`, `setup.rbxcdn.com`, `s3.amazonaws.com`) are
  unreachable from this sandbox (TLS connection failures).
- `archive.roblonium.com` (the source cited by KloBraticc/2015-Client) is unreachable.
- `KloBraticc/2015-Client` contains only `AppSettings.xml` (144 B) for the target version —
  not the client binaries.
- `CedarCoder1/Roblox-Versions-Archive` CSV lists only 2025 builds (Google Drive links).
- `leihanglei/roblox-2007-2015-clients` covers 2007–2012 only.

The **claimed SHA-256** `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44`
(for `RobloxPlayerBeta.exe`) is recorded in `server/bloxen/config.py` and enforced by the
launcher's allowlist (`server/bloxen/launcher/uri.py::validate_client_package`) **when the
package is present**. It is marked **UNVERIFIED** until a package can be obtained and hashed.

## Planned static analysis checklist (quarantine intake)

When the package is obtained it goes to `quarantine/client/<version>/` and is analyzed
WITHOUT execution:

- [ ] file inventory + sizes
- [ ] SHA-256 of every file (compare claimed hash)
- [ ] version resource (0.205.0.61876)
- [ ] PE metadata (timestamp, subsystem, imports)
- [ ] Authenticode certificate metadata
- [ ] package completeness vs DeployHistory expectations
- [ ] provenance record + verification log entry

## REAL WINDOWS CLIENT EXECUTION = BLOCKED

This cloud environment cannot execute Windows binaries. See
`docs/WINDOWS-REAL-CLIENT-VALIDATION.md` for the handoff checklist. No system in BLOXEN is
labeled REAL-CLIENT-TESTED.

## Known genuine-client findings (provided by prior real-client testing, used as constraints)

- Engine init, graphics, audio, input, local HTTP bootstrap, RakNet, protocol 31 observed
- Descriptor synchronization observed: 332 classes / 968 properties / 320 events / 182 types
- SET_GLOBALS discovery: **121-bit Workspace preamble**, correct decode = **22 top containers**,
  first class **231 = ReplicatedFirst**. After correction the client stayed connected and
  immediately emitted multiple ID_DATA packets.
- Next blocker: **AUTHORITATIVE SERVER → CLIENT ID_DATA** — implemented in BLOXEN's game
  server and exercised by the simulator (SIMULATOR-TESTED).
- Legacy Huffman behavior identified on the wire (string compression); BLOXEN's legacy string
  encoding is currently uncompressed length-prefixed — see docs/PROTOCOL.md open items.

These observations override simulator convenience (rule enforced in
`server/bloxen/gameserver/replicator.py`).

---

# Browser client runtime (2026-10-05)

A separate, clearly-labelled runtime now renders the preserved place files in a browser:
**docs/CLIENT-RUNTIME.md**. It is *not* the Windows Player and is not claimed to be; it consumes
the same real place files and labels real vs reconstructed features in-experience.

Status ladder for it: `parsed` → `geometry-exported` → **BROWSER-TESTED** (14/14 games, zero
JS/HTTP errors, headless Chromium evidence). The Windows player path below remains
**BLOCKED** and nothing in BLOXEN is REAL-CLIENT-TESTED.

Two open items discovered while building it are recorded in CLIENT-RUNTIME.md §7 — the most
important being that **wedge part orientation could not be resolved from evidence**
(statistical test on 7.1k wedge parts was inconclusive), so the runtime ships a flip toggle
instead of a claim.

## Patch labeling (docs §10)

The client binary is **patched** (one-byte change at file offset `0x538c1`: `6a01` → `6a00` in `RCCService.exe`, sha256 changed from `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44` to `02254587...`). This patch was applied to enable the join script and hash check bypass. All run logs and documentation record this as `clean -> patched`; the unmodified client is never presented.

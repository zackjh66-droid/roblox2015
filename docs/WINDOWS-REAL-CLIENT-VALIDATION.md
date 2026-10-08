# WINDOWS REAL-CLIENT VALIDATION — HANDOFF

**Status: the genuine client package has been ACQUIRED and VERIFIED (see
docs/CLIENT-PACKAGE.md — SHA-256, PE timestamp, version resource and DeployHistory all
agree). REAL WINDOWS CLIENT *EXECUTION* = STILL BLOCKED: this is a Linux cloud environment
and the binary is a Windows PE. No system is claimed REAL-CLIENT-TESTED.**

## 1. Acquire the genuine client

Target: WindowsPlayer `0.205.0.61876` (`version-0d46087630eb46cd`, deployed 2015-07-23
23:33:45 PT).

- **DONE 2026-10-05:** acquired from `github.com/KloBraticc/2015-Client` (path
  `July 23 (0.205.0.61876)`, commit `7a0742cb…`) and verified — see docs/CLIENT-PACKAGE.md.
  The `setup.roblox.com` route below remains unreachable from this environment and is kept
  for completeness.
- Preferred (unreachable here): `http://setup.roblox.com/version-0d46087630eb46cd-RobloxApp.zip`,
  `…-RobloxPlayerBeta.exe`, `…-RobloxStudio.zip`, `…-shaders.zip` (manifest in
  `research/sources/setup-rbxcdn/RobloxApp20150723T233345Z.version-0d46087630eb46cd.json`)
- Fallback mirrors from `research/sources/setup-rbxcdn/VersionHistory-README-2025.txt`
- Place **into quarantine** (`quarantine/client/version-0d46087630eb46cd/`) — DO NOT EXECUTE
  anything yet.

## 2. Static analysis (mandatory before any run)

- [x] SHA-256 every file; `RobloxPlayerBeta.exe` =
      `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44` — **matches the
      hash recorded before acquisition** (run `tools/verify_client_package.py`)
- [x] version resource = 0.205.0.61876 (FileVersion and ProductVersion read from the binary)
- [x] PE header timestamp 2015-07-23 19:45:30 UTC; Authenticode certificate table present
- [ ] package completeness vs DeployHistory
- [ ] record all of the above in `research` DB `verification_log`

## 3. Controlled execution (fresh Windows VM; no personal data; no real Roblox credentials)

- [ ] point `AppSettings.xml` at a LOCAL BLOXEN backend (see
      `research/sources/client-settings/AppSettings.xml` for the 2015 keys: bootstrapper
      URL, client version)
- [ ] `bloxen-player:` protocol registration + Play-from-site launch test
- [ ] capture the client's HTTP calls → compare to `server/bloxen/compat/` (the
      `compat_requests` log is designed for exactly this diff)
- [ ] capture RakNet/RakNet-free traffic → compare message IDs/framing against
      docs/PROTOCOL.md § Roblox layer
- [ ] descriptor sync: verify observed 332/968/320/182 against our descriptor stream
- [ ] SET_GLOBALS: verify the 121-bit preamble decode (22 containers, first class 231)
- [ ] ID_DATA: verify the client consumes our world+player replication
- [ ] movement (0xF4) and spawn (0xF5) round-trips

## 4. Safety rules (unchanged)

Never disable AV/firewall/exclusions; never execute unreviewed historical executables
outside this controlled protocol; never use real Roblox credentials or ROBLOSECURITY; never
forward anything to live Roblox services.

## 5. Cloud-blocked items to mark as such in any report

- ~~client package download (CDN unreachable from this environment)~~ — **done** from a
  public archive mirror; see docs/CLIENT-PACKAGE.md
- real-client execution (still blocked: Windows required)
- ~~claimed client SHA-256 remains UNVERIFIED~~ — **verified**, exact match
- byte-level wire comparison

Everything else in BLOXEN (website, accounts, catalog, avatar, inventory, games import,
game server replication, launcher flow, compat service) is implemented and covered by
automated end-to-end tests labeled SIMULATOR-TESTED.

## Patch labeling (docs §10)

The client binary is **patched** (one-byte change at file offset `0x538c1`: `6a01` → `6a00` in `RCCService.exe`, sha256 changed from `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44` to `02254587...`). This patch was applied to enable the join script and hash check bypass. All run logs and documentation record this as `clean -> patched`; the unmodified client is never presented.

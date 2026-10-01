# WINDOWS REAL-CLIENT VALIDATION — HANDOFF

**Status: REAL WINDOWS CLIENT EXECUTION = BLOCKED (cloud environment cannot execute Windows
binaries). No system is claimed REAL-CLIENT-TESTED.**

## 1. Acquire the genuine client

Target: WindowsPlayer `0.205.0.61876` (`version-0d46087630eb46cd`, deployed 2015-07-23
23:33:45 PT).

- Preferred: `http://setup.roblox.com/version-0d46087630eb46cd-RobloxApp.zip`,
  `…-RobloxPlayerBeta.exe`, `…-RobloxStudio.zip`, `…-shaders.zip` (manifest in
  `research/sources/setup-rbxcdn/RobloxApp20150723T233345Z.version-0d46087630eb46cd.json`)
- Fallback mirrors from `research/sources/setup-rbxcdn/VersionHistory-README-2025.txt`
- Place **into quarantine** (`quarantine/client/version-0d46087630eb46cd/`) — DO NOT EXECUTE
  anything yet.

## 2. Static analysis (mandatory before any run)

- [ ] SHA-256 every file; compare `RobloxPlayerBeta.exe` to the claimed
      `384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44`
- [ ] version resource = 0.205.0.61876
- [ ] PE header timestamp, cert metadata
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

- client package download (CDN unreachable from this environment)
- real-client execution
- claimed client SHA-256 remains UNVERIFIED
- byte-level wire comparison

Everything else in BLOXEN (website, accounts, catalog, avatar, inventory, games import,
game server replication, launcher flow, compat service) is implemented and covered by
automated end-to-end tests labeled SIMULATOR-TESTED.

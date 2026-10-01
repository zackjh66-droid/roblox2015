# BLOXEN — PROTOCOL

## Evidence anchors (genuine-client observations — these constrain all work here)

From prior REAL genuine-client testing of `0.205.0.61876` (see docs/CLIENT.md):

- RakNet transport, **protocol 31**
- descriptor synchronization: observed **332 classes / 968 properties / 320 events / 182 types**
- **SET_GLOBALS**: **121-bit Workspace preamble**; correct decode = **22 top containers**;
  first class **231 = ReplicatedFirst**
- after the SET_GLOBALS correction the client stayed connected and emitted multiple
  **ID_DATA** packets; the next blocker is **AUTHORITATIVE SERVER → CLIENT ID_DATA**
- legacy Huffman string behavior identified on the wire

BLOXEN's game server + simulator implement exactly this shape. Simulator results are labeled
**SIMULATOR-TESTED** and never override these observations.

## Transport: RakNet (implemented, `server/bloxen/gameserver/raknet.py`)

- OpenConnectionRequest1/Reply1/Request2/Reply2 with RakNet magic
- ConnectionRequest / ConnectionRequestAccepted / NewIncomingConnection
- connected ping/pong
- frame sets (sequence numbers, u24 little-endian), reliable + ordered frames,
  **split frames** (bit-4 split flag; reliability in bits 5–7), ACK/NACK, retransmission
- byte-plane interleaved integers; rotated floats; zigzag+delta referents (binary place format)

## Roblox layer (RECONSTRUCTION — message IDs pending capture comparison)

| ID | Name | Direction | Status |
|---|---|---|---|
| 0xF0/0xF1 | HELLO / HELLO_REPLY (carries protocol=31 + version GUID) | C↔S | reconstruction |
| 0xF2 | REQUEST_DESCRIPTORS | C→S | reconstruction |
| 0x84/0x87 | DESCRIPTOR_BEGIN/END block (classes, property descriptors, event descriptors, types) | S→C | reconstruction; counts from real API dump |
| 0x85 | SET_GLOBALS | S→C | **layout per genuine evidence** |
| 0x86 | ID_DATA (instance replication) | S→C | reconstruction; this is the evidenced blocker |
| 0xF3 | PLAYER_INIT (user id + name) | C→S | reconstruction |
| 0xF4/0xF5 | MOVE / SPAWN_CHARACTER | C→S | stubs |

Message-ID numbers are provisional placeholders in `descriptors.py` / `server.py`; the
MESSAGE SEMANTICS and SET_GLOBALS layout follow genuine observations. Exact byte-level
identity awaits a genuine-client capture (recorded as the top open item).

## SET_GLOBALS layout (encoded exactly as evidenced)

```
byte  msgid = 0x85
16b   first class id = 231        (ReplicatedFirst)
8b    top container count = 22
      ...padding to exactly 121 bits of Workspace preamble...
then  22 containers: (index u32, class id u32, class name string), container 0 = ReplicatedFirst
```

Asserted in code (`replicator.build_set_globals`) and validated by the simulator
(`simulator/client.py` step "set-globals").

## Descriptor synchronization

Built from the **real target-build API dump** (332 classes). Inherited members are
materialized (4,988 property descriptors). The genuine wire counts (968/320/182) are recorded
as `observed_wire_counts()`; the counting-semantics gap is an open verification item —
likely hidden/network-only members not present in the public dump.

## ID_DATA

Authoritative server→client instance replication: world roots (bounded 2,500 roots /
6,000 instances per session from the imported place) + Players/Player + character
(Model/Torso/Head/Humanoid/BodyColors). Simulator validates instance count and player-tree
presence.

## 2015-client compatibility HTTP surface (`server/bloxen/compat/`)

| Endpoint | Purpose | Status |
|---|---|---|
| `/Login/Negotiate.ashx`, `/Login/RequestAuth.ashx` | auth handshake | reconstruction |
| `/Game/Visit.ashx` | visit start → join-script style payload | reconstruction |
| `/Game/PlaceLauncher.ashx` | place launch bridge | reconstruction |
| `/Game/Join.ashx` | join | reconstruction |
| `/Asset/CharacterFetch.ashx?userId=` | character appearance from BLOXEN DB | reconstruction |
| `/Avatar/BodyColors.ashx?userId=` | body colors (XML shape) | reconstruction |
| `/asset/?id=` | asset delivery (defers to asset service; MISSING stays MISSING) | reconstruction |
| `/Setting/Values` | bootstrap settings (client version/GUID/base URLs/protocol) | reconstruction |
| `/presence/ping` | presence | reconstruction |
| catch-all | **logged + 404 — never forwarded to live Roblox** | rule |

Every request is recorded in `compat_requests` for later comparison with genuine-client
captures.

## Launcher / Play flow

`bloxen-player:play?ticket=…&game=…` — ticket: cryptographically random (24B urlsafe),
single-use, TTL 120s, user+game scoped. Replay/expiry/wrong-user/wrong-game all rejected
(tested). Launcher validates URI strictly, hash-verifies the client package against the
allowlist, then launches with `--base-url` pointing at the compat service. Windows process
launch + `bloxen-player:` protocol registration = **AWAITING WINDOWS VALIDATION**.

## Open items

1. Byte-level message IDs / framing vs genuine-client capture (compare `compat_requests` logs
   and RakNet captures)
2. Legacy Huffman string compression (identified on genuine wire; not yet implemented)
3. Descriptor counting semantics (968/320/182)
4. Ordering/sequencing edge cases, replication of physics/movement state

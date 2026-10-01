"""RakNet transport layer (2005-2015 era wire format) for BLOXEN.

Implements:
- OpenConnection handshake (request1/reply1/request2/reply2) with RakNet magic
- connected ping/pong
- ConnectionRequest / ConnectionRequestAccepted
- reliable + ordered frames, frame sets, ACK/NACK, retransmission, split packets

Wire format references: open-source RakNet implementations and protocol
dissectors (e.g. Arisstath/raknet-dissector). See docs/PROTOCOL.md.
"""
from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass, field

RAKNET_MAGIC = b"\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xfd\xfd\xfd\xfd\x12\x34\x56\x78"

ID_CONNECTED_PING = 0x00
ID_UNCONNECTED_PING = 0x01
ID_CONNECTED_PONG = 0x03
ID_OPEN_CONNECTION_REQUEST_1 = 0x05
ID_OPEN_CONNECTION_REPLY_1 = 0x06
ID_OPEN_CONNECTION_REQUEST_2 = 0x07
ID_OPEN_CONNECTION_REPLY_2 = 0x08
ID_CONNECTION_REQUEST = 0x09
ID_CONNECTION_REQUEST_ACCEPTED = 0x10
ID_NEW_INCOMING_CONNECTION = 0x13
ID_DISCONNECTION_NOTIFICATION = 0x15
ID_INCOMPATIBLE_PROTOCOL_VERSION = 0x19
ID_FRAME_SET_START = 0x80
ID_FRAME_SET_END = 0x8F
ID_ACK = 0xC0
ID_NACK = 0xA0

RELIABLE_FLAG = 0x20
ORDERED_FLAG = 0x10
SPLIT_FLAG = 0x10           # RakNet: bit 4 is the split flag (bits 5-7 are reliability)
VALID_RELIABILITY_MASK = 0x1B


@dataclass
class Frame:
    payload: bytes
    reliable_index: int | None = None
    sequence_index: int | None = None
    order_index: int | None = None
    order_channel: int = 0
    split: bool = False
    split_count: int = 0
    split_id: int = 0
    split_index: int = 0
    reliability_flags: int = 3   # RELIABLE_ORDERED (standard RakNet enum)


@dataclass
class PeerState:
    guid: int = 0
    addr: tuple = ("", 0)
    mtu: int = 1464
    next_send_seq: int = 0
    next_recv_seq: int = 0
    reliable_index: int = 0
    order_index: int = 0
    acks: set = field(default_factory=set)
    nacks: set = field(default_factory=set)
    sent: dict = field(default_factory=dict)          # seq -> (time, datagram)
    recv_ordered: dict = field(default_factory=dict)  # order_index -> payload
    next_ordered_deliver: int = 0
    splits: dict = field(default_factory=dict)        # split_id -> {index: payload}
    connected: bool = False
    last_seen: float = 0.0


class RakNetServer:
    """asyncio DatagramProtocol implementing the server side of RakNet."""

    def __init__(self, on_message, on_connect=None):
        self.on_message = on_message            # async (peer, payload)
        self.on_connect = on_connect            # async (peer)
        self.transport = None
        self.peers: dict[tuple, PeerState] = {}
        self.protocol_version = 6

    def connection_made(self, transport):
        self.transport = transport
        try:
            sock = transport.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass

    def datagram_received(self, data: bytes, addr):
        asyncio.ensure_future(self._handle(data, addr))

    async def _handle(self, data: bytes, addr: tuple):
        if not data:
            return
        pid = data[0]
        peer = self.peers.get(addr)
        if peer is None:
            peer = PeerState(addr=addr)
            self.peers[addr] = peer
        peer.last_seen = time.time()

        if pid == ID_UNCONNECTED_PING:
            await self._send_unconnected_pong(data, addr)
        elif pid == ID_OPEN_CONNECTION_REQUEST_1:
            await self._open_request1(data, addr)
        elif pid == ID_OPEN_CONNECTION_REQUEST_2:
            await self._open_request2(data, addr)
        elif pid == ID_CONNECTION_REQUEST:
            await self._connection_request(peer, data)
        elif pid == ID_CONNECTED_PING:
            await self._connected_ping(peer, data)
        elif pid == ID_DISCONNECTION_NOTIFICATION:
            self.peers.pop(addr, None)
        elif ID_FRAME_SET_START <= pid <= ID_FRAME_SET_END:
            await self._frame_set(peer, data)
        elif pid == ID_ACK:
            self._handle_ack(peer, data)
        elif pid == ID_NACK:
            self._handle_nack(peer, data)

    # ------------------------------------------------------------ handshake
    def _addr_bytes(self, addr) -> bytes:
        """RakNet address: version byte + inverted IP bytes + port u16."""
        ip, port = addr
        parts = [int(x) for x in ip.split(".")]
        return bytes([4] + [(~p) & 0xFF for p in parts]) + port.to_bytes(2, "big")

    async def _send_unconnected_pong(self, data, addr):
        out = bytes([ID_CONNECTED_PONG]) + data[1:9] + (0).to_bytes(8, "little")
        self.transport.sendto(out, addr)

    async def _open_request1(self, data, addr):
        proto = data[1 + len(RAKNET_MAGIC)] if len(data) > 1 + len(RAKNET_MAGIC) else 0
        if proto != self.protocol_version:
            out = bytes([ID_INCOMPATIBLE_PROTOCOL_VERSION, self.protocol_version]) + RAKNET_MAGIC + (0).to_bytes(8, "little")
            self.transport.sendto(out, addr)
            return
        peer = self.peers[addr]
        mtu = min(max(len(data), 500), 1464)
        peer.mtu = mtu
        out = (bytes([ID_OPEN_CONNECTION_REPLY_1]) + RAKNET_MAGIC
               + (0x1122334455667788).to_bytes(8, "little")   # server guid
               + b"\x00"                                       # no security
               + mtu.to_bytes(2, "big"))
        self.transport.sendto(out, addr)

    async def _open_request2(self, data, addr):
        peer = self.peers[addr]
        # request2: 0x07 + magic + server address + mtu u16 + client guid
        pos = 1 + len(RAKNET_MAGIC)
        addr_len = data[pos]
        pos += 1 + addr_len
        mtu = int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
        client_guid = int.from_bytes(data[pos:pos + 8], "little")
        peer.guid = client_guid
        peer.mtu = min(mtu, 1464)
        out = (bytes([ID_OPEN_CONNECTION_REPLY_2]) + RAKNET_MAGIC
               + client_guid.to_bytes(8, "little")
               + self._addr_bytes(addr)
               + peer.mtu.to_bytes(2, "big")
               + b"\x00")
        self.transport.sendto(out, addr)

    async def _connection_request(self, peer: PeerState, data: bytes):
        # 0x09 + client guid + request time + security
        peer.connected = True
        out = bytearray([ID_CONNECTION_REQUEST_ACCEPTED])
        out += self._addr_bytes(peer.addr)
        out += (0).to_bytes(2, "big")                 # system index
        for _ in range(10):                            # internal ids
            out += self._addr_bytes(("127.0.0.1", 0))
        out += int(time.time() * 1000).to_bytes(8, "little")   # request time
        out += int(time.time() * 1000).to_bytes(8, "little")   # accepted time
        await self._send_reliable(peer, bytes(out))
        if self.on_connect:
            await self.on_connect(peer)

    async def _connected_ping(self, peer: PeerState, data: bytes):
        out = bytes([ID_CONNECTED_PONG]) + data[1:9] + int(time.time() * 1000).to_bytes(8, "little")
        await self._send_reliable(peer, out)

    # ------------------------------------------------------------- sending
    def _wrap_frames(self, peer: PeerState, frames: list[Frame]) -> bytes:
        out = bytearray([ID_FRAME_SET_START])
        out += peer.next_send_seq.to_bytes(3, "little")
        peer.next_send_seq = (peer.next_send_seq + 1) & 0xFFFFFF
        for fr in frames:
            flags = (fr.reliability_flags & 0x07) << 5
            if fr.split:
                flags |= SPLIT_FLAG
            out.append(flags)
            out += (len(fr.payload) * 8).to_bytes(2, "big")
            if fr.reliability_flags in (2, 3, 4):     # reliable
                out += (fr.reliable_index or 0).to_bytes(3, "little")
            if fr.split:
                out += fr.split_count.to_bytes(4, "big")
                out += fr.split_id.to_bytes(2, "big")
                out += fr.split_index.to_bytes(4, "big")
            if fr.reliability_flags in (1, 3, 4):     # sequenced/ordered
                out += (fr.order_index or 0).to_bytes(3, "little")
                out.append(fr.order_channel)
            out += fr.payload
        return bytes(out)

    async def _send_reliable(self, peer: PeerState, payload: bytes):
        max_payload = 1200
        if len(payload) <= max_payload:
            fr = Frame(payload=payload,
                       reliable_index=peer.reliable_index,
                       order_index=peer.order_index,
                       reliability_flags=3)       # RELIABLE_ORDERED
            peer.reliable_index += 1
            peer.order_index += 1
            datagram = self._wrap_frames(peer, [fr])
            seq = peer.next_send_seq - 1
            peer.sent[seq] = (time.time(), datagram)
            self.transport.sendto(datagram, peer.addr)
            return
        # split payload across frames sharing one order index
        parts = [payload[i:i + max_payload] for i in range(0, len(payload), max_payload)]
        split_id = peer.reliable_index & 0xFFFF
        for idx, part in enumerate(parts):
            fr = Frame(payload=part,
                       reliable_index=peer.reliable_index,
                       order_index=peer.order_index,
                       reliability_flags=3,
                       split=True,
                       split_count=len(parts),
                       split_id=split_id,
                       split_index=idx)
            peer.reliable_index += 1
            datagram = self._wrap_frames(peer, [fr])
            seq = peer.next_send_seq - 1
            peer.sent[seq] = (time.time(), datagram)
            self.transport.sendto(datagram, peer.addr)
            if idx % 32 == 31:
                await asyncio.sleep(0)      # let the peer drain socket buffers
        peer.order_index += 1

    async def send_message(self, peer: PeerState, payload: bytes):
        await self._send_reliable(peer, payload)

    # ----------------------------------------------------------- receiving
    async def _frame_set(self, peer: PeerState, data: bytes):
        seq = int.from_bytes(data[1:4], "little")
        peer.acks.add(seq)
        if seq >= peer.next_recv_seq:
            peer.next_recv_seq = seq + 1
        pos = 4
        while pos < len(data):
            flags = data[pos]
            reliability = (flags >> 5) & 0x07
            split = bool(flags & SPLIT_FLAG)
            pos += 1
            bitlen = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            payload_len = bitlen // 8
            reliable_index = None
            split_count = split_id = split_index = 0
            order_index = None
            order_channel = 0
            if reliability in (2, 3, 4):           # reliable -> has index
                reliable_index = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
            if split:
                split_count = int.from_bytes(data[pos:pos + 4], "big")
                pos += 4
                split_id = int.from_bytes(data[pos:pos + 2], "big")
                pos += 2
                split_index = int.from_bytes(data[pos:pos + 4], "big")
                pos += 4
            if reliability in (1, 3, 4):           # sequenced/ordered -> order index
                order_index = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                order_channel = data[pos]
                pos += 1
            payload = data[pos:pos + payload_len]
            pos += payload_len

            if split:
                bucket = peer.splits.setdefault(split_id, {"count": split_count, "parts": {}})
                bucket["parts"][split_index] = payload
                if len(bucket["parts"]) == bucket["count"]:
                    payload = b"".join(bucket["parts"][i] for i in range(bucket["count"]))
                    peer.splits.pop(split_id, None)
                else:
                    continue

            if order_index is not None and reliability == 3:
                peer.recv_ordered[order_index] = payload
                while peer.next_ordered_deliver in peer.recv_ordered:
                    p = peer.recv_ordered.pop(peer.next_ordered_deliver)
                    peer.next_ordered_deliver += 1
                    await self._dispatch(peer, p)
            else:
                await self._dispatch(peer, payload)

    async def _dispatch(self, peer: PeerState, payload: bytes):
        if not payload:
            return
        pid = payload[0]
        if pid == ID_CONNECTED_PING:
            await self._connected_ping(peer, payload)
            return
        if pid == ID_CONNECTION_REQUEST:
            await self._connection_request(peer, payload)
            return
        if pid == ID_NEW_INCOMING_CONNECTION:
            return
        await self.on_message(peer, payload)

    def _send_ack_or_nack(self, peer: PeerState, sequences: set[int], is_ack: bool):
        if not sequences:
            return
        out = bytearray([ID_ACK if is_ack else ID_NACK])
        seqs = sorted(sequences)
        out += len(seqs).to_bytes(2, "big")
        single = not (len(seqs) > 1 and seqs[-1] - seqs[0] == len(seqs) - 1)
        if single:
            out.append(0)
            for s in seqs:
                out += s.to_bytes(3, "little")
        else:
            out.append(1)
            out += seqs[0].to_bytes(3, "little")
            out += seqs[-1].to_bytes(3, "little")
        self.transport.sendto(bytes(out), peer.addr)

    def flush_acks(self, peer: PeerState):
        self._send_ack_or_nack(peer, set(peer.acks), True)
        peer.acks.clear()

    def _handle_ack(self, peer: PeerState, data: bytes):
        pos = 3 if data[1] == 0 else 1
        count = int.from_bytes(data[1:3], "big")
        pos = 3
        for _ in range(count):
            if data[pos] == 0:
                pos += 1
                seq = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                peer.sent.pop(seq, None)
            else:
                pos += 1
                start = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                end = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                for s in range(start, end + 1):
                    peer.sent.pop(s, None)

    def _handle_nack(self, peer: PeerState, data: bytes):
        # retransmit requested sequences
        count = int.from_bytes(data[1:3], "big")
        pos = 3
        for _ in range(count):
            if data[pos] == 0:
                pos += 1
                seq = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                if seq in peer.sent:
                    self.transport.sendto(peer.sent[seq][1], peer.addr)
            else:
                pos += 1
                start = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                end = int.from_bytes(data[pos:pos + 3], "little")
                pos += 3
                for s in range(start, end + 1):
                    if s in peer.sent:
                        self.transport.sendto(peer.sent[s][1], peer.addr)

    def tick(self):
        """Resend unacked reliable datagrams + flush acks (call periodically)."""
        now = time.time()
        for peer in self.peers.values():
            self.flush_acks(peer)
            for seq, (t, datagram) in list(peer.sent.items()):
                if now - t > 0.8:
                    peer.sent[seq] = (now, datagram)
                    self.transport.sendto(datagram, peer.addr)


class RakNetClient:
    """Client side of the RakNet handshake + reliable messaging (for the simulator)."""

    def __init__(self, server_addr, on_message=None):
        self.server_addr = server_addr
        self.on_message = on_message
        self.transport = None
        self.peer = PeerState(addr=server_addr)
        self.guid = 0x424c4f58454e0001      # 'BLOXEN\0\1'
        self.ready = asyncio.Event()
        self.received: asyncio.Queue = asyncio.Queue()
        self.splits: dict = {}

    def connection_made(self, transport):
        self.transport = transport
        try:
            sock = transport.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass

    def connection_lost(self, exc):
        pass

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self._handle(data, addr))

    async def _handle(self, data: bytes, addr):
        pid = data[0]
        if pid == ID_OPEN_CONNECTION_REPLY_1:
            out = (bytes([ID_OPEN_CONNECTION_REQUEST_2]) + RAKNET_MAGIC
                   + self._addr_bytes(addr)
                   + self.peer.mtu.to_bytes(2, "big")
                   + self.guid.to_bytes(8, "little"))
            self.transport.sendto(out, addr)
        elif pid == ID_OPEN_CONNECTION_REPLY_2:
            out = (bytes([ID_CONNECTION_REQUEST])
                   + self.guid.to_bytes(8, "little")
                   + int(time.time() * 1000).to_bytes(8, "little")
                   + b"\x00")
            self.transport.sendto(out, addr)
        elif pid == ID_CONNECTION_REQUEST_ACCEPTED:
            out = (bytes([ID_NEW_INCOMING_CONNECTION])
                   + self._addr_bytes(addr) + (0).to_bytes(2, "big"))
            for _ in range(10):
                out += self._addr_bytes(("127.0.0.1", 0))
            out += int(time.time() * 1000).to_bytes(8, "little") * 2
            self.transport.sendto(out, addr)
            self.peer.connected = True
            self.ready.set()
        elif ID_FRAME_SET_START <= pid <= ID_FRAME_SET_END:
            await self._frame_set(data, addr)
        elif pid == ID_ACK:
            pass

    async def _accept(self, addr):
        out = (bytes([ID_NEW_INCOMING_CONNECTION])
               + self._addr_bytes(addr) + (0).to_bytes(2, "big"))
        for _ in range(10):
            out += self._addr_bytes(("127.0.0.1", 0))
        out += int(time.time() * 1000).to_bytes(8, "little") * 2
        self.transport.sendto(out, addr)
        self.peer.connected = True
        self.ready.set()

    def _addr_bytes(self, addr) -> bytes:
        ip, port = addr
        parts = [int(x) for x in ip.split(".")]
        return bytes([4] + [(~p) & 0xFF for p in parts]) + port.to_bytes(2, "big")

    async def _frame_set(self, data: bytes, addr):
        seq = int.from_bytes(data[1:4], "little")
        ack = bytearray([ID_ACK, 0, 1, 0]) + seq.to_bytes(3, "little")
        self.transport.sendto(bytes(ack), addr)
        pos = 4
        while pos < len(data):
            flags = data[pos]
            reliability = (flags >> 5) & 0x07
            split = bool(flags & SPLIT_FLAG)
            pos += 1
            payload_len = int.from_bytes(data[pos:pos + 2], "big") // 8
            pos += 2
            if reliability in (2, 3, 4):
                pos += 3
            split_count = split_id = split_index = 0
            if split:
                split_count = int.from_bytes(data[pos:pos + 4], "big")
                pos += 4
                split_id = int.from_bytes(data[pos:pos + 2], "big")
                pos += 2
                split_index = int.from_bytes(data[pos:pos + 4], "big")
                pos += 4
            if reliability in (1, 3, 4):
                pos += 4
            payload = data[pos:pos + payload_len]
            pos += payload_len
            if split:
                bucket = self.splits.setdefault(split_id, {"count": split_count, "parts": {}})
                bucket["parts"][split_index] = payload
                if len(bucket["parts"]) == bucket["count"]:
                    payload = b"".join(bucket["parts"][i] for i in range(bucket["count"]))
                    self.splits.pop(split_id, None)
                else:
                    continue
            if not payload:
                continue
            if payload[0] == ID_CONNECTION_REQUEST_ACCEPTED:
                await self._accept(addr)
                continue
            if payload[0] == ID_CONNECTED_PONG:
                continue
            await self.received.put(payload)

    async def send_reliable(self, payload: bytes):
        max_payload = 1200
        if len(payload) > max_payload:
            parts = [payload[i:i + max_payload] for i in range(0, len(payload), max_payload)]
            split_id = self.peer.reliable_index & 0xFFFF
            for idx, part in enumerate(parts):
                out = bytearray([ID_FRAME_SET_START])
                out += self.peer.next_send_seq.to_bytes(3, "little")
                self.peer.next_send_seq = (self.peer.next_send_seq + 1) & 0xFFFFFF
                out.append((3 << 5) | SPLIT_FLAG)
                out += (len(part) * 8).to_bytes(2, "big")
                out += self.peer.reliable_index.to_bytes(3, "little")
                self.peer.reliable_index += 1
                out += len(parts).to_bytes(4, "big")
                out += split_id.to_bytes(2, "big")
                out += idx.to_bytes(4, "big")
                out += self.peer.order_index.to_bytes(3, "little")
                out.append(0)
                out += part
                self.transport.sendto(bytes(out), self.server_addr)
            self.peer.order_index += 1
            return
        out = bytearray([ID_FRAME_SET_START])
        out += self.peer.next_send_seq.to_bytes(3, "little")
        self.peer.next_send_seq = (self.peer.next_send_seq + 1) & 0xFFFFFF
        out.append(3 << 5)
        out += (len(payload) * 8).to_bytes(2, "big")
        out += self.peer.reliable_index.to_bytes(3, "little")
        self.peer.reliable_index += 1
        out += self.peer.order_index.to_bytes(3, "little")
        self.peer.order_index += 1
        out.append(0)
        out += payload
        self.transport.sendto(bytes(out), self.server_addr)

    async def open(self):
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: self, remote_addr=self.server_addr)
        out = (bytes([ID_OPEN_CONNECTION_REQUEST_1]) + RAKNET_MAGIC
               + bytes([6]) + b"\x00" * 12)
        self.transport.sendto(out, self.server_addr)
        await asyncio.wait_for(self.ready.wait(), timeout=5)

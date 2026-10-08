"""Low-level readers for the Roblox binary place/model format (RBXL/RBXM).

Byte layouts follow the publicly documented format as implemented by mature
open-source readers (rojo-rbx/rbx-dom, Dekkonot/rbx-binary-format):
- chunk framing: name[4] + u32 compressedLen + u32 uncompressedLen + u32 reserved
- chunk payload: LZ4 block (compressedLen != 0) or raw
- strings: u32 length + bytes
- integer arrays: byte-plane interleaved big-endian
- referents: interleaved u32 -> zigzag+delta decode
- floats: stored as u32 rotated right by 1 bit
"""
from __future__ import annotations

import struct

try:
    import lz4.block as _lz4
except ImportError:  # pragma: no cover
    _lz4 = None


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError(f"needed {n} bytes at {self.pos}, have {self.remaining()}")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.read(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.read(8))[0]

    def string(self) -> bytes:
        n = self.u32()
        return self.read(n)

    def rbx_float32(self) -> float:
        raw = struct.unpack("<I", self.read(4))[0]
        rotated = ((raw >> 1) | (raw << 31)) & 0xFFFFFFFF
        return struct.unpack("<f", struct.pack("<I", rotated))[0]

    def interleaved_uint(self, count: int, size: int) -> list[int]:
        """Interleaved byte-plane big-endian integer array.

        Reference: stream.lua::readInterleavedUInt — each element is assembled as
        int = int*256 + bytes[plane k] for k = 0..size-1, so plane 0 is the MOST
        significant byte (big-endian within the element, byte-plane interleaved
        across the array).
        """
        planes = [self.read(count) for _ in range(size)]
        out = []
        for i in range(count):
            v = 0
            for k in range(size):                 # plane 0 = most significant byte
                v = (v << 8) | planes[k][i]
            out.append(v)
        return out

    def interleaved_i32(self, count: int) -> list[int]:
        out = []
        for v in self.interleaved_uint(count, 4):
            if v >= 2**31:
                v -= 2**32
            out.append(v)
        return out

    def interleaved_rbx_float32(self, count: int) -> list[float]:
        out = []
        for raw in self.interleaved_uint(count, 4):
            rotated = ((raw >> 1) | (raw << 31)) & 0xFFFFFFFF
            out.append(struct.unpack("<f", struct.pack("<I", rotated))[0])
        return out

    def referents(self, count: int) -> list[int]:
        vals = self.interleaved_uint(count, 4)
        out = []
        acc = 0
        for v in vals:
            # zigzag decode
            n = (v >> 1) ^ -(v & 1)
            acc += n
            out.append(acc)
        return out


def decompress_chunk(payload: bytes, uncompressed_len: int, compressed_len: int = 1) -> bytes:
    # Format rule (rbx-dom / rbx-binary-format): compressed_length == 0 -> raw block,
    # otherwise LZ4 block compressed. Payload length is NOT a reliable indicator
    # (an LZ4 block can compress to exactly the uncompressed size).
    if compressed_len == 0:
        return payload
    if _lz4 is None:
        raise RuntimeError("lz4 package required to read compressed chunks")
    return _lz4.decompress(payload, uncompressed_size=uncompressed_len)

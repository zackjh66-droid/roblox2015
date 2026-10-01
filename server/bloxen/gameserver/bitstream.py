"""BitStream implementation for the 2015-era Roblox replicator protocol.

Reconstruction notes (docs/PROTOCOL.md):
- Roblox's RakNet carried serialized BitStream messages on ID_DATA
- strings are length-prefixed with "legacy string" encoding
- the descriptor/schema system serializes classes, properties, events, types
- SET_GLOBALS carries the Workspace preamble; genuine-client evidence reports
  a 121-bit Workspace preamble with 22 top containers and ReplicatedFirst
  first (class id 231)
"""
from __future__ import annotations

import struct


class BitWriter:
    def __init__(self):
        self.bits: list[int] = []

    def write_bit(self, b: int):
        self.bits.append(1 if b else 0)

    def write_bits(self, value: int, n: int):
        for i in range(n - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def write_byte(self, v: int):
        self.write_bits(v & 0xFF, 8)

    def write_bytes(self, data: bytes):
        for b in data:
            self.write_byte(b)

    def write_u16(self, v: int):
        self.write_bits(v & 0xFFFF, 16)

    def write_u32(self, v: int):
        self.write_bits(v & 0xFFFFFFFF, 32)

    def write_string(self, s: str | bytes):
        """Legacy string encoding: u32 length + bytes."""
        data = s.encode("utf-8") if isinstance(s, str) else s
        self.write_u32(len(data))
        self.write_bytes(data)

    def to_bytes(self) -> bytes:
        out = bytearray()
        acc = 0
        n = 0
        for bit in self.bits:
            acc = (acc << 1) | bit
            n += 1
            if n == 8:
                out.append(acc)
                acc = 0
                n = 0
        if n:
            out.append(acc << (8 - n))
        return bytes(out)


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_bit(self) -> int:
        byte_i, bit_i = divmod(self.pos, 8)
        if byte_i >= len(self.data):
            raise EOFError("out of bits")
        self.pos += 1
        return (self.data[byte_i] >> (7 - bit_i)) & 1

    def read_bits(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.read_bit()
        return v

    def read_byte(self) -> int:
        return self.read_bits(8)

    def read_bytes(self, n: int) -> bytes:
        return bytes(self.read_byte() for _ in range(n))

    def read_u16(self) -> int:
        return self.read_bits(16)

    def read_u32(self) -> int:
        return self.read_bits(32)

    def read_string(self) -> bytes:
        n = self.read_u32()
        return self.read_bytes(n)

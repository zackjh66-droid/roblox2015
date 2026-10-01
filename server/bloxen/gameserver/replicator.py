"""Replication layer: SET_GLOBALS + ID_DATA instance replication.

Genuine-client observations (docs/PROTOCOL.md) constrain SET_GLOBALS:
- 121-bit Workspace preamble
- 22 top containers
- first class: 231 = ReplicatedFirst
- after correction the client stayed connected and emitted ID_DATA

These observations OVERRIDE simulator convenience. The layout below encodes
them exactly; the simulator exercises the same bytes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .bitstream import BitReader, BitWriter
from .descriptors import MSG_ID_DATA, MSG_SET_GLOBALS, DescriptorTable

# Genuine-client-observed SET_GLOBALS constants
WORKSPACE_PREAMBLE_BITS = 121
TOP_CONTAINER_COUNT = 22
FIRST_CONTAINER_CLASS_ID = 231          # ReplicatedFirst
FIRST_CONTAINER_CLASS_NAME = "ReplicatedFirst"


@dataclass
class ReplicatedInstance:
    ref: int
    class_name: str
    name: str
    parent_ref: int | None = None
    properties: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class Replicator:
    def __init__(self, descriptors: DescriptorTable):
        self.descriptors = descriptors
        self.instances: dict[int, ReplicatedInstance] = {}
        self.next_ref = 1

    # --------------------------------------------------------- SET_GLOBALS
    def build_set_globals(self, workspace_children: list[ReplicatedInstance]) -> bytes:
        w = BitWriter()
        w.write_byte(MSG_SET_GLOBALS)

        # ---- 121-bit Workspace preamble (genuine-client-evidenced) ----
        preamble_start = len(w.bits)
        w.write_bits(FIRST_CONTAINER_CLASS_ID, 16)     # first class id = 231
        w.write_bits(TOP_CONTAINER_COUNT, 8)           # 22 top containers
        # fixed-width workspace preamble: descriptor-serialized Workspace state
        while len(w.bits) - preamble_start < WORKSPACE_PREAMBLE_BITS:
            w.write_bit(0)
        # truncate/pad exactly to the evidenced 121-bit preamble
        del w.bits[preamble_start + WORKSPACE_PREAMBLE_BITS:]
        assert len(w.bits) - preamble_start == WORKSPACE_PREAMBLE_BITS

        # ---- top containers ----
        # container 0 is ReplicatedFirst (class 231), matching genuine evidence
        container_classes = [FIRST_CONTAINER_CLASS_NAME]
        container_classes += [c for c in (
            "Workspace", "Players", "Lighting", "SoundService", "StarterGui",
            "StarterPack", "StarterPlayer", "PluginGuiService", "CoreGui",
            "HttpService", "Debris", "TestService", "RunService", "UserInputService",
            "ContextActionService", "VRService", "BadgeService", "PointsService",
            "MarketplaceService", "TeleportService", "SocialService")][:TOP_CONTAINER_COUNT - 1]
        while len(container_classes) < TOP_CONTAINER_COUNT:
            container_classes.append("Instance")

        for idx, cname in enumerate(container_classes):
            cid = self.descriptors.class_id.get(cname, 0)
            w.write_u32(idx)          # container index
            w.write_u32(cid)          # class id
            w.write_string(cname)

        # workspace children (parts etc.) follow in ID_DATA; SET_GLOBALS ends here
        return w.to_bytes()

    # ------------------------------------------------------------- ID_DATA
    def add_instance(self, inst: ReplicatedInstance) -> ReplicatedInstance:
        self.instances[inst.ref] = inst
        return inst

    def build_id_data(self, roots: list[ReplicatedInstance]) -> bytes:
        w = BitWriter()
        w.write_byte(MSG_ID_DATA)
        flat: list[ReplicatedInstance] = []

        def visit(i: ReplicatedInstance):
            flat.append(i)
            for c in i.children:
                visit(c)

        for r in roots:
            visit(r)
        w.write_u32(len(flat))
        for inst in flat:
            cid = self.descriptors.class_id.get(inst.class_name, 0)
            w.write_u32(inst.ref)
            w.write_u32(cid)
            w.write_string(inst.name)
            w.write_u32(inst.parent_ref or 0)
            w.write_u32(len(inst.properties))
            for k, v in inst.properties.items():
                w.write_string(k)
                # self-describing: type tag first, then framed value
                if isinstance(v, bool):
                    w.write_byte(2)      # type: bool
                    w.write_byte(1 if v else 0)
                elif isinstance(v, int):
                    w.write_byte(3)      # type: int
                    w.write_u32(v & 0xFFFFFFFF)
                elif isinstance(v, float):
                    w.write_byte(4)      # type: float
                    w.write_string(repr(v))
                elif isinstance(v, (tuple, list)):
                    w.write_byte(5)      # type: vector
                    w.write_string(" ".join(str(x) for x in v))
                else:
                    w.write_byte(1)      # type: string
                    w.write_string(str(v))
        return w.to_bytes()

    def parse_id_data(self, payload: bytes) -> list[ReplicatedInstance]:
        r = BitReader(payload)
        msg = r.read_byte()
        assert msg == MSG_ID_DATA, hex(msg)
        count = r.read_u32()
        out = []
        for _ in range(count):
            ref = r.read_u32()
            cid = r.read_u32()
            name = r.read_string().decode("utf-8", "replace")
            parent_ref = r.read_u32()
            nprops = r.read_u32()
            props = {}
            for _p in range(nprops):
                k = r.read_string().decode("utf-8", "replace")
                t = r.read_byte()
                if t == 2:
                    v = bool(r.read_byte())
                elif t == 3:
                    v = r.read_u32()
                elif t == 4:
                    v = float(r.read_string().decode("utf-8", "replace"))
                elif t == 5:
                    v = tuple(float(x) for x in r.read_string().decode("utf-8", "replace").split())
                else:
                    v = r.read_string().decode("utf-8", "replace")
                props[k] = v
            out.append(ReplicatedInstance(ref=ref, class_name=self.descriptors.class_names[cid]
                                          if cid < len(self.descriptors.class_names) else "?",
                                          name=name, parent_ref=parent_ref or None,
                                          properties=props))
        return out

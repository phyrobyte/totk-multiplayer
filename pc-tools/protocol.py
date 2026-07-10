"""Wire protocol v0 — shared by every PC-side tool and mirrored by the sysmodule.

See config/protocol.md for the on-the-wire spec. Little-endian throughout.
Python 3.9 compatible (no 3.10+ syntax).
"""
import json
import os
import struct

MAGIC = b"TOTK"
PROTO_VER = 0

# msg_type values
MSG_RAW_REGION = 1
MSG_STRUCTURED = 2
MSG_TAG = 3

# Header: magic, proto_ver, msg_type, player_id, flags, seq, t_send, region_off, length
_HEADER = struct.Struct("<4sBBBBIdIH")
HEADER_SIZE = _HEADER.size  # 26

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9917


def pack(msg_type, payload=b"", player_id=0, seq=0, t_send=0.0, region_off=0, flags=0):
    """Build a wire packet (header + payload) as bytes."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    header = _HEADER.pack(
        MAGIC, PROTO_VER, msg_type, player_id, flags,
        seq & 0xFFFFFFFF, float(t_send), region_off & 0xFFFFFFFF, len(payload),
    )
    return header + payload


def parse(data):
    """Parse a wire packet. Returns a dict, or None if invalid/too short/bad magic."""
    if len(data) < HEADER_SIZE:
        return None
    magic, proto_ver, msg_type, player_id, flags, seq, t_send, region_off, length = \
        _HEADER.unpack(data[:HEADER_SIZE])
    if magic != MAGIC:
        return None
    payload = data[HEADER_SIZE:HEADER_SIZE + length]
    return {
        "proto_ver": proto_ver,
        "msg_type": msg_type,
        "player_id": player_id,
        "flags": flags,
        "seq": seq,
        "t_send": t_send,
        "region_off": region_off,
        "length": length,
        "payload": payload,
    }


# --- little-endian field readers/writers over a bytes/bytearray region ---

def read_f32(buf, off):
    return struct.unpack_from("<f", buf, off)[0]


def read_u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def write_f32(buf, off, value):
    struct.pack_into("<f", buf, off, float(value))


def write_u32(buf, off, value):
    struct.pack_into("<I", buf, off, int(value) & 0xFFFFFFFF)


_READERS = {"f32": read_f32, "u32": read_u32}


def read_field(buf, field):
    """Read a field described by an entry from a layout/address config's 'fields'."""
    return _READERS[field["type"]](buf, field["offset"])


def load_layout(path):
    """Load a sim_layout.json / addresses.<version>.json config file."""
    with open(path, "r") as f:
        return json.load(f)


def repo_config_dir():
    """Path to the repo's config/ dir, relative to this file (pc-tools/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "config"))

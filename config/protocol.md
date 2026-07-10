# Wire Protocol v0

Small, versioned UDP protocol shared by every component (fake simulator, real
sysmodule, recorder, visualizer, PC server). Little-endian.

## Packet header (26 bytes)

`struct` format: `<4sBBBBIdIH`

| Field        | Type   | Bytes | Meaning                                             |
|--------------|--------|-------|-----------------------------------------------------|
| `magic`      | `4s`   | 4     | always `b"TOTK"` — reject packets without it         |
| `proto_ver`  | `u8`   | 1     | protocol version, currently `0`                      |
| `msg_type`   | `u8`   | 1     | `1`=RAW_REGION, `2`=STRUCTURED, `3`=TAG              |
| `player_id`  | `u8`   | 1     | which player/console this is about                   |
| `flags`      | `u8`   | 1     | reserved, `0` for now                                |
| `seq`        | `u32`  | 4     | monotonically increasing sequence number            |
| `t_send`     | `f64`  | 8     | sender timestamp (seconds, monotonic)               |
| `region_off` | `u32`  | 4     | base offset of the raw region in game memory (RAW)  |
| `length`     | `u16`  | 2     | payload length in bytes                             |

Payload (`length` bytes) follows the header.

## Message types

- **RAW_REGION (1)** — payload is a raw copy of a chunk of game RAM starting at
  `region_off`. Used for address hunting: the analyzer diffs these over time. This
  is the primary Phase 0–2 message.
- **STRUCTURED (2)** — payload is parsed fields (pos/rot/anim/hp) once addresses
  are known. Used later for efficient netcode. Layout TBD in Phase 4.
- **TAG (3)** — payload is a UTF-8 label (e.g. `"jump"`, `"damage"`). Emitted by the
  human **action tagger** on the console to mark "this happened NOW", so the
  analyzer can correlate memory changes to actions. `region_off` unused.

## Why raw regions first

We don't know where anything is yet. Streaming a whole region and diffing it on the
PC lets the analyzer *discover* offsets from ground-truth-free data. Once confirmed
and written into `addresses.<version>.json`, tools can extract fields directly.

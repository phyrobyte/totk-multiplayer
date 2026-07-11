# Switch sysmodule (the thin memory pipe)

The on-console half of the mod. A small Atmosphère background sysmodule whose only
jobs are: read a region of TOTK's RAM, send it to the PC as wire-protocol v0
`RAW_REGION` packets, and write "ghost" data back into RAM. All logic stays on the
PC — this stays tiny.

**Status: skeleton.** `source/main.c` compiles later with devkitPro + libnx. The
memory read/write calls are stubbed and get wired to Atmosphère's `dmnt:cht` service
(`ReadCheatProcessMemory` / `WriteCheatProcessMemory`) once the console is modded and
addresses are confirmed (Phase 1–2).

The packet layout in `main.c` (`totk_header_t`) is byte-identical to
`pc-tools/protocol.py` and `config/protocol.md` — keep them in sync.

## Build (later, once the console is modded)

1. Install devkitPro + `switch-dev` + libnx: https://devkitpro.org/wiki/Getting_Started
2. Reference sysmodule setup: https://github.com/switchbrew/switch-examples
3. Wire up the `switch_rules` include in the `Makefile`, then `make`.
4. Copy the built module to `sdcard:/atmosphere/contents/<program-id>/` and reboot.

## What to fill in

- `REGION_BASE` / `REGION_SIZE` — from `config/addresses.1.2.1.json` (Phase 2).
- `PC_HOST` — the PC/server IP.
- `read_game_memory` / `write_game_memory` — the `dmnt:cht` calls.
- Pointer-chain resolution so the region survives ASLR across reboots.

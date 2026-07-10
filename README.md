<div align="center">

# 🗡️ TOTK Multiplayer

**A network-protocol co-op mod for *The Legend of Zelda: Tears of the Kingdom* on modded Switch hardware.**
See each other roam Hyrule in real time — powered by a thin on-console memory pipe and an authoritative PC server.

<br />

<!-- Live GitHub badges (populate automatically as the repo gets releases/stars/etc.) -->
[![Downloads](https://img.shields.io/github/downloads/phyrobyte/totk-multiplayer/total?style=for-the-badge&logo=github&label=downloads&color=4fc3f7)](https://github.com/phyrobyte/totk-multiplayer/releases)
[![Release](https://img.shields.io/github/v/release/phyrobyte/totk-multiplayer?style=for-the-badge&logo=github&color=7fd6ff&include_prereleases)](https://github.com/phyrobyte/totk-multiplayer/releases)
[![Stars](https://img.shields.io/github/stars/phyrobyte/totk-multiplayer?style=for-the-badge&logo=github&color=ffb300)](https://github.com/phyrobyte/totk-multiplayer/stargazers)
[![License](https://img.shields.io/github/license/phyrobyte/totk-multiplayer?style=for-the-badge&color=4caf50)](LICENSE)

[![Forks](https://img.shields.io/github/forks/phyrobyte/totk-multiplayer?style=flat-square&logo=github)](https://github.com/phyrobyte/totk-multiplayer/network/members)
[![Issues](https://img.shields.io/github/issues/phyrobyte/totk-multiplayer?style=flat-square&logo=github)](https://github.com/phyrobyte/totk-multiplayer/issues)
[![Last commit](https://img.shields.io/github/last-commit/phyrobyte/totk-multiplayer?style=flat-square&logo=github)](https://github.com/phyrobyte/totk-multiplayer/commits)
[![Repo size](https://img.shields.io/github/repo-size/phyrobyte/totk-multiplayer?style=flat-square)](https://github.com/phyrobyte/totk-multiplayer)
[![Python](https://img.shields.io/badge/PC%20tools-Python%203.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pc-tools)
[![Switch](https://img.shields.io/badge/console-Atmosph%C3%A8re%20CFW-E60012?style=flat-square&logo=nintendoswitch&logoColor=white)](sysmodule)

</div>

> **Download badges** show live counts from GitHub Releases and populate once the
> first release is published. Stars/forks/issues/size update automatically.

---

## What this is

TOTK has no networking code. This project synchronizes two (or more) consoles by
**reading player state out of the game's RAM, relaying it over the network, and
writing it back as a visible "ghost"** — the same technique the Breath of the Wild
multiplayer mods use. The realistic v1 target is **ghost co-op**: you and your
brother see each other move, turn, and animate in your own worlds, with shared
HP/loose combat as a stretch goal. (Fully synced enemy AI/physics is explicitly out
of scope — see [`ROADMAP.md`](ROADMAP.md).)

### Architecture

```
   ┌──────────── AUTHORITATIVE PC SERVER ────────────┐
   │  validates state · relays · interpolation ·     │
   │  address config · hosts Switch-only clients      │
   └───────▲──────────────────────────────▲──────────┘
           │ UDP (wire-protocol v0)        │
     ┌─────┴──────┐                  ┌─────┴──────┐
     │  Switch A  │                  │  Switch B  │
     │ thin sysmod│                  │ thin sysmod│
     │ read/write │                  │ read/write │
     │  game RAM  │                  │  game RAM  │
     └────────────┘                  └────────────┘
```

The Switch stays dumb (just moves bytes); all logic lives on the PC where iteration
is fast. A single PC doubles as a **server**, so a friend needs only a modded Switch —
no PC of their own. Multiple servers can later **federate** (server interlink).

## Repo layout

```
totk-multiplayer/
├── ROADMAP.md          # the full phased, robustness-first plan
├── config/             # version pin, wire protocol, address-map schemas
├── pc-tools/           # Phase 0 pipeline — runnable NOW against a fake console
│   ├── protocol.py       shared wire-protocol v0
│   ├── fake_switch.py     synthetic console (streams fake telemetry)
│   ├── recorder.py        capture stream -> session file
│   ├── analyzer.py        offline address hunter
│   └── visualizer.py      live top-down map
├── sysmodule/          # thin Atmosphère memory-pipe (C/libnx skeleton)
└── pc-server/          # authoritative server (Phase 4+)
```

## Try it now — no console required

The entire PC pipeline runs today against a **fake Switch** with known ground truth,
so it's build *and* verify before hardware:

```bash
cd pc-tools

# watch a fake Link move live on a map
python3 fake_switch.py &
python3 visualizer.py

# or: record a session and hunt its addresses offline
python3 recorder.py --label demo &
python3 fake_switch.py --duration 60
python3 analyzer.py --verify ../config/sim_layout.json
```

See [`pc-tools/README.md`](pc-tools/README.md) for details.

## Status

Phase 0 (foundations / PC pipeline) — **✅ done & verified**: fake console →
recorder → analyzer (finds 6/6 planted fields) → live map, plus an authoritative PC
server relaying/validating two fake players. Console-dependent phases (real
addresses, ghost actor, two-player sync) begin once the hardware is modded. Target
game version is pinned to **1.4.2**.

## Requirements

- **PC tools:** Python 3.9+ (standard library only; `tkinter` for the visualizer).
- **Console (later):** a hackable Switch running **Atmosphère** CFW, TOTK **1.4.2**,
  EdiZon-SE, devkitPro/libnx to build the sysmodule.

## ⚠️ Legal / disclaimer

This repository contains **only original tooling and code** — no Nintendo assets,
no game dumps, no keys. It requires you to own and dump your own copy of the game.
This is a homebrew / reverse-engineering project for educational and personal use,
not affiliated with or endorsed by Nintendo. Nintendo, The Legend of Zelda, and
Tears of the Kingdom are trademarks of Nintendo. Use at your own risk.

## License

[MIT](LICENSE) © 2026 phyrobyte

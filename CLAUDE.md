# CLAUDE.md — project context & rules

Guidance for working in this repo. Read this first; it encodes the non-obvious
constraints. The full phased plan lives in [ROADMAP.md](ROADMAP.md).

## What this project is

A **network-protocol co-op mod for Zelda: Tears of the Kingdom** on modded Switch
hardware. TOTK has no networking; we synchronize consoles by reading player state
out of game RAM, relaying it through an authoritative PC server, and writing it back
as a visible "ghost." Realistic v1 = **ghost co-op** (see each other move/animate).
Full enemy-AI/physics sync is explicitly out of scope.

**Architecture:** thin on-console sysmodule (moves bytes) ⟷ authoritative PC server
(all logic, validation, relay) ⟷ other consoles. One PC server doubles as a host, so
Switch-only players can join. See ROADMAP for phases and the platform tier (Phase 7).

## Hard rules (do not violate)

1. **Game version is pinned to EXACTLY 1.4.2.** Every TOTK patch relocates memory
   addresses. Both/all consoles must run byte-identical 1.4.2. 1.4.3 exists — never
   "update to latest." Block auto-updates. Treat updating as project-ending.
2. **The Switch stays dumb; the PC holds the brains.** Keep the sysmodule tiny (read/
   write RAM + move bytes). All logic, validation, and state live on the PC.
3. **Never write unvalidated data into game RAM.** Range-check every value against
   the address config before writing/relaying. Bad writes crash the console. Fail
   safe (skip) rather than poke garbage.
4. **Everything is config-driven and versioned.** Addresses, pointer chains, and the
   wire protocol live in data files, never hardcoded. A game update = edit config,
   not a rebuild.
5. **Capture, don't watch.** Analysis is decoupled from play: record sessions to
   files, analyze offline. Claude never needs to be "live" on the console.
6. **Keep the wire protocol in sync.** `pc-tools/protocol.py`, `config/protocol.md`,
   and the C `totk_header_t` in `sysmodule/source/main.c` must stay byte-identical.
7. **PC tools are Python 3.9+, standard library only.** No pip deps (tkinter is
   stdlib). Don't add third-party requirements without a strong reason.

## Repo layout

- `config/` — version pin, wire-protocol v0 spec, address-map schemas (`sim_layout.json`
  is the fake console's ground truth; `addresses.1.4.2.example.json` is the real
  template).
- `pc-tools/` — Phase 0 pipeline, runnable now against a fake console:
  `fake_switch.py` (synthetic console), `recorder.py`, `analyzer.py` (address hunter),
  `visualizer.py` (live map), `protocol.py` (shared).
- `pc-server/` — `server.py`, the authoritative buffer/host (validates, tracks, relays).
- `sysmodule/` — thin Atmosphère memory-pipe skeleton (C/libnx), built on-console later.

## How to verify (there are two regimes)

- **Synthetic ground truth (now, no console):** `fake_switch.py` plants known values,
  so the PC code has a right answer to check. Analyzer must find the planted fields;
  server must relay with 0 rejected. This proves code logic.
- **Physical observation (only on hardware):** the game-integration truths are verified
  by watching the screen — poke an address → Link teleports; ghost actor → a second
  Link appears; co-op → the other player sees you move. These cannot be faked.

Quick checks:
```bash
# PC pipeline (terminal renderer auto-used on macOS system Python)
python3 pc-tools/fake_switch.py --duration 30 &
python3 pc-tools/recorder.py --label demo            # then Ctrl-C
python3 pc-tools/analyzer.py --verify config/sim_layout.json
python3 pc-tools/visualizer.py                        # live map (TUI fallback)
# server + N players
python3 pc-server/server.py &
python3 pc-tools/fake_switch.py --port 9920 --player-id 1 --seed 1 &
python3 pc-tools/fake_switch.py --port 9920 --player-id 2 --seed 2 &
```

---

## TOTK mod loader — how content mods work (for mod-hosting, Phase 7b)

Goal #2 (host mods on the server) must distribute mods compatible with the standard
TOTK modding pipeline. Two **separate** loading mechanisms are in play; don't conflate
them:

### A. Our multiplayer mod = a sysmodule (NOT LayeredFS)
Runs as an Atmosphère background process in `sd:/atmosphere/contents/<our-program-id>/`.
It touches RAM and networks. It is independent of, and coexists with, content mods.

### B. Content mods = RomFS asset swaps via Atmosphère LayeredFS
- **Mechanism:** [LayeredFS](https://switch.hacks.guide/extras/game_modding.html) (built
  into Atmosphère) transparently replaces game assets with modified ones while booted
  in CFW.
- **Install path:** `sd:/atmosphere/contents/0100F2C0115B6000/romfs/…`
  - **`0100F2C0115B6000` is TOTK's title ID.** exefs/IPS code patches go in
    `exefs/`; cheats in `cheats/`.
- **CFW requirement:** **Atmosphère ≥ 1.5.4** — it added TOTK-specific support to
  build RomFS for games with ~300,000 files without crashing. Older CFW cannot load
  TOTK mods.
- **THE critical rule — RESTBL / RSTB (Resource Size Table):** TOTK stores each
  resource's expected size in a table. If a mod changes an asset's size without
  patching the RSTB, the game **crashes**. Any mod distribution MUST ship a correct,
  merged RESTBL.
- **Multiple mods / priority:** LayeredFS resolves conflicts by folder ordering
  (underscore-delimited, descending alphabetical); files from higher-priority mods win.
  Unmergeable conflicts are decided by priority order.
- **Newer firmware:** LayeredFS can load directly from a folder renamed `romfslite`
  (used by TKMM) to speed loading.

### C. TKMM — the de-facto loader/merger (design our hosting around it)
[TKMM (TotK Mod Manager)](https://github.com/TKMM-Team/Tkmm) is what the community
uses. It **merges** individual mods into one conflict-free LayeredFS output:
- Merges: `.sarc`/`.pack` archives, `.bgyml` params, RSDB (resource database), Mals
  (localization/text), **RESTBL**, and `.ips`/`.pchtxt` patches → one merged IPS.
- Non-mergeable files: resolved by priority list (top = highest).
- Package/install formats: **`.tkcl`** (TKMM's own package format), plus `.zip`,
  `.rar`, `.7z`.
- Output: a merged mod folder to drop into `atmosphere/contents/0100F2C0115B6000/`
  (`romfs`/`romfslite`).

### Rules for OUR mod hosting (Phase 7b) — Minecraft-style modpack matching
Server is authoritative over *which* mods everyone runs. This is a **sync correctness
requirement**, not just a feature: divergent content mods make players' worlds diverge
and break state sync. It is NOT server-side mod *execution* — impossible, since TOTK
content mods are boot-time LayeredFS asset swaps with no runtime for the server to
simulate.

- A server defines **ONE canonical, pre-merged modpack**: merged once by the host via
  **TKMM** (RESTBL-correct, load-order-resolved), identified by a **hash**.
- **Version-lock everything to 1.4.2**; reject mismatches.
- On join, client reports its modpack hash; **mismatch → refuse to play** (kick) and
  offer the canonical pack.
- Distribute the **pre-merged bytes** (drop into `atmosphere/contents/0100F2C0115B6000/`,
  then **relaunch** the game). Pre-merging means **Switch-only players need no TKMM**.
- Always ship a **correct merged RESTBL** (size-changing assets without it = crash).
- Enforce **Atmosphère ≥ 1.5.4** on clients.
- **Mods can't hot-swap** (LayeredFS is boot-time): "match before you play," not live
  streaming; changing the pack = download + relaunch.
- Keep content-mod distribution separate from the multiplayer sysmodule; a server may
  serve both, but they install to different places and load by different mechanisms.

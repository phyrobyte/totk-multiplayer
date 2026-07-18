# HANDOFF — Continue Here (for the next assistant, e.g. Codex)

You are picking up an in-progress project from Claude. The human's Claude usage is
capped, so **you** are now the PC-side partner. This file orients you fast.

## 0. Read these first, in order
1. [`CLAUDE.md`](CLAUDE.md) — hard rules & project context (READ FULLY).
2. [`ROADMAP.md`](ROADMAP.md) — the phased plan and gates.
3. [`docs/re-notes.md`](docs/re-notes.md) — reverse-engineering intel + the `totk_syms` resource.
4. [`README.md`](README.md), [`pc-tools/README.md`](pc-tools/README.md), [`pc-server/README.md`](pc-server/README.md).

## 1. What this project is (1 paragraph)
A network co-op mod for **Zelda: Tears of the Kingdom** on modded Switch. TOTK has no
networking; we read player state from game RAM, relay it through an authoritative PC
server, and write it into a "ghost" actor on the other console. v1 target = **ghost
co-op** (see each other move/animate). The Switch stays dumb (a thin sysmodule that
moves bytes); all logic lives on the PC.

## 2. How this project OPERATES (critical — you are not live on the console)
- The **human** works the **Switch** (right now: EdiZon-SE memory search; later: runs
  the sysmodule). You **cannot** touch console RAM directly.
- **You** work the **PC**: write code, analyze recordings, maintain config, do Ghidra RE.
- The core loop is **capture → analyze → confirm**: the human records/searches on the
  console and hands you files; you analyze offline and propose addresses; the human
  confirms by poking them (poke value → Link visibly moves).

## 3. Current status (as of this handoff)
- ✅ **Phase 0 DONE & verified**: PC pipeline (`fake_switch`→`recorder`→`analyzer`→
  `visualizer`) + authoritative `pc-server/server.py`, all tested against synthetic
  ground truth (analyzer finds 6/6 planted fields; server relays N players, 0 rejected).
- ✅ **Console ready**: modded (Atmosphère), **TOTK downgraded to 1.2.1** (from 1.4.3,
  via Goldleaf), EdiZon-SE + Goldleaf installed, save backed up with JKSV, full-RAM
  homebrew working (`atmosphere/config/override_config.ini` set).
- ⏳ **Build ID**: the human has it from the EdiZon overlay — get it, confirm it matches
  the `totk_syms` build, and write it into `config/version.json` + `config/addresses.1.2.1.json`.
- ▶️ **NEXT: Gate 1** — help the human find **Link's Y coordinate** in EdiZon, poke it,
  watch Link launch upward. This is the whole-project feasibility proof.

## 4. Immediate next steps (do these in order)
1. **Gate 1 (now):** walk the human through EdiZon-SE: search type **Float (4 bytes)**,
   **Unknown initial value**, region **Heap**. Jump → filter "increased"; stand still →
   "unchanged"; repeat until a few candidates remain = Link's Y. Poke a big value →
   Link rises → **Gate 1 passed**. If this fails, STOP and reassess (see ROADMAP Gate 1).
2. **Record the confirmed address** into `config/addresses.1.2.1.json` (copy the schema
   from `config/addresses.1.2.1.example.json`; note it's `.gitignore`d so it stays local).
3. **Phase 2 — full map:** find pos X/Y/Z, rotation/yaw, animation/state, HP, and the
   **stable pointer chain** (raw addrs move per boot; pointer chains survive). Use BOTH:
   (a) the on-console EdiZon loop, and (b) **Ghidra + `totk_syms`** (see §5) to derive
   offsets from named functions — much faster than blind search.
4. **Build the sysmodule** (`sysmodule/`, devkitPro/libnx). Fill `REGION_BASE`/`REGION_SIZE`
   + pointer chain from the config; wire `read_game_memory`/`write_game_memory` to
   `dmnt:cht`. It streams the region to the PC in wire-protocol v0 (keep byte-identical
   to `pc-tools/protocol.py` + `config/protocol.md`).
5. **Phase 3 — the ghost actor** (hardest gate): use the named `totk_syms` functions
   `engine::actor::ActorBase::setPositionAndRotationDirect` / `PhysicsComponent::
   forceSetPosition` to write a hijacked actor. Isolate & test single-console first.
6. **Phase 4 — two players** through `pc-server/server.py` (already built). Then robustness
   (Phase 5), hosting/mods/server-list (Phase 7 — see ROADMAP + CLAUDE.md mod-loader rules).

## 5. The key resource: `totk_syms` (why we pinned 1.2.1)
[`github.com/dt-12345/totk_syms`](https://github.com/dt-12345/totk_syms) — **136k named
function symbols + Ghidra datatypes (`totk.gdt`) for TOTK 1.2.1** (engine syms by
watertoon). Workflow: load the 1.2.1 `main` NSO in Ghidra (Switch loader), import
`totk.gdt`, apply `exking_symbols.csv`, then read the player position struct offsets
straight from `ActorBase::setPosition` and trace `game::wm::WorldManagerModule` /
`game::component::Player` to the static base pointer. This de-risks BOTH the address
map (Phase 2) and the ghost (Phase 3). Full details + the function list in
`docs/re-notes.md`.

## 6. The tools you have (all Python 3.9 stdlib, no deps)
- `pc-tools/protocol.py` — wire-protocol v0 (shared). Keep in sync with the C sysmodule.
- `pc-tools/fake_switch.py` — synthetic console (planted ground truth) for testing.
- `pc-tools/recorder.py` — capture the UDP stream to `recordings/*.jsonl`.
- `pc-tools/analyzer.py` — offline address hunter; `--verify config/sim_layout.json`.
- `pc-tools/visualizer.py` — live map; auto-falls back to `--tui` (macOS system Tk 8.5
  renders blank — known; TUI works everywhere).
- `pc-server/server.py` — authoritative buffer/host; validates + relays; run with N
  `fake_switch` instances to test.
- Real addresses go in `config/addresses.1.2.1.json` (fill from `.example`); the
  visualizer/server read field offsets from there — everything downstream already works.

## 7. Hard rules (do not violate — full list in CLAUDE.md)
1. **Game pinned to EXACTLY 1.2.1.** Never update. Both consoles byte-identical.
2. Switch stays dumb; PC holds the brains.
3. **Never write unvalidated data to game RAM** (range-check vs the address config; bad
   writes crash the console — fail safe/skip).
4. Everything config-driven & versioned.
5. Capture, don't watch (offline analysis).
6. Keep the wire protocol byte-identical across `protocol.py` / `protocol.md` / `main.c`.
7. PC tools: Python 3.9+ stdlib only.

## 8. Environment
- Repo: `/Users/proha/totk-mods` — GitHub: **phyrobyte/totk-multiplayer** (public).
- Console: Atmosphère CFW, TOTK **1.2.1**, EdiZon-SE + Goldleaf + JKSV + HBAS installed.
- Commit style: end messages with `Co-Authored-By:` trailer; push to `main`.

## 9. First thing to say to the human
Ask for the **Build ID** (from the EdiZon overlay), then guide **Gate 1** (find Link's
Y, poke it, confirm he moves). That unblocks everything else.

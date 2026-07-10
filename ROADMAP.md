# TOTK Multiplayer Mod — Master Roadmap

A robustness-first plan for building a networked co-op mod for *The Legend of
Zelda: Tears of the Kingdom* on modded Switch hardware, with a PC acting as an
authoritative buffer/server.

> **Scope reality check.** The realistic target is **"ghost co-op"**: players see
> each other move, animate, and (later) share HP/loose combat in their own
> instances of Hyrule. Fully synchronized enemy AI, physics, and Ultrahand
> contraptions are a multi-year research effort and are **explicitly out of scope**
> for v1. We build the achievable version well, then climb.

---

## 0. Guiding principles (the "robustness" rules)

These apply to every phase. When in doubt, obey these.

1. **Fail fast at gates.** Each phase ends in a GO/NO-GO milestone that proves the
   *next* phase is possible before we invest in it. If a gate fails, we stop and
   rethink — we never build on an unproven layer.
2. **Pin the game version to EXACTLY 1.4.2. Never update.** Every TOTK patch
   relocates memory addresses and can break everything. **Target = 1.4.2**, chosen
   for being the most stable/bug-fixed/played build per the modding community.
   Record it in `config/version.json`. Treat updating as a project-ending event.
   **Critical 1.4.2 gotchas:**
   - 1.4.3 already exists and is "latest" — hitting *update* lands on 1.4.3, NOT
     1.4.2. Both consoles must install the *specific* 1.4.2 update file, then stop.
   - Hard-block auto-updates (via Atmosphère) so neither console drifts to 1.4.3.
   - 1.4.2 was the Switch 2 / "Zelda Notes" update — use the Switch 1 build and
     confirm Atmosphère + base firmware support it before committing.
   - Both consoles must be byte-identical 1.4.2 or the shared address config is
     invalid.
3. **The Switch stays dumb; the PC holds the brains.** The sysmodule only reads/
   writes RAM and moves bytes. All logic, state, and decisions live on the PC where
   we can iterate in seconds and debug freely.
4. **Everything is versioned and config-driven.** Addresses, pointer chains, and
   protocol schemas live in data files, never hardcoded. A game update should mean
   editing a config, not a rebuild.
5. **Capture, don't watch.** Because analysis (Claude/PC) is decoupled from play
   (human/Switch), every session is *recorded to a file* and analyzed offline. This
   is the core workflow, not an afterthought.
6. **Never trust a synced value blindly.** Writing bad data to game RAM crashes the
   console. Validate ranges, sanity-check, and fail safe (skip the write) rather
   than poke garbage.
7. **Save safety.** Back up saves (JKSV) before every RAM-poking session. Assume
   corruption is possible until proven otherwise.

---

## Architecture at a glance

```
            ┌─────────────────── AUTHORITATIVE PC SERVER ───────────────────┐
            │  - holds world/session state    - validates & relays          │
            │  - interpolation & smoothing     - address config per version  │
            └───────────────▲───────────────────────────▲───────────────────┘
                            │ UDP (thin protocol)        │
                   ┌────────┴────────┐          ┌────────┴────────┐
                   │  Switch A       │          │  Switch B       │
                   │  thin sysmodule │          │  thin sysmodule │
                   │  read/write RAM │          │  read/write RAM │
                   └─────────────────┘          └─────────────────┘

  SERVER-HOSTING MODEL (bigger picture):
   A single PC server can host many Switch-only clients — a player needs only a
   modded Switch + the sysmodule, no PC of their own.

  FEDERATION / DUAL-PC INTERLINK (later):
   Multiple PC servers link to each other ("server interlink") so populations on
   different hosts can share a world. Each PC remains authoritative for its local
   Switches; servers reconcile at the edges.
```

**Why a single PC buffer is the right default:** it doubles as a *server*. Switch-
only players (no PC) can join a hosted game. The dual-PC model is not an
alternative — it's the **federation layer** on top: PC servers interlinking so
separate hosts share players. We build single-server first, add federation last.

---

## Phase 0 — Foundations (NO console required)

Everything here is buildable today, before either Switch is modded. Goal: a
working end-to-end pipeline driven by **fake data**, so the moment real memory
exists we just plug it in.

**Build:**
- [ ] Repo layout: `sysmodule/`, `pc-server/`, `pc-tools/`, `config/`, `docs/`.
- [ ] **PC receiver/recorder** — listens on UDP, records incoming RAM snapshots to
      timestamped, tagged files. Test against a fake sender.
- [ ] **Offline analyzer** — loads a recording, diffs frames, flags candidate
      addresses (e.g. "smooth-changing 4-byte float"). Test against synthetic data.
- [ ] **Sysmodule source skeleton** (devkitPro/libnx): main loop, UDP socket, stub
      read/write calls. Won't do anything real yet; compiles and structurally sound.
- [ ] **Protocol v0** — define the packet format (header, version field, payload).
- [ ] **Address config schema** (`config/addresses.<version>.json`) — how we store
      addresses + pointer chains + validation ranges.
- [ ] **Version pin doc** — decide and record the exact TOTK version to target.

**GATE 0 — ✅ PASSED:** Fake sysmodule → PC receiver → recorder → analyzer →
visualizer all run end-to-end on synthetic data (analyzer finds 6/6 planted fields;
visualizer renders via terminal TUI). The **authoritative PC server** (Phase 4 core)
is also built early and verified relaying/validating two fake players. *We can now
onboard real memory instantly.*

---

## Phase 1 — Console bring-up & the "one value" milestone

The feasibility gate for the entire project. Cheap to reach; tells us if this is
real.

**Do:**
- [ ] Mod both Switches → Atmosphère CFW. Install EdiZon-SE, JKSV.
- [ ] Back up saves. Pin both consoles to the target version.
- [ ] Compile & run the memory-streamer sysmodule; confirm bytes reach the PC.
- [ ] Using the **record → diff → tag** loop, find **ONE** address: Link's Y
      (height) coordinate is easiest — it changes smoothly and distinctly when you
      jump/glide/climb.
- [ ] Confirm it: poke the value in EdiZon → Link visibly teleports vertically.

**GATE 1 (the big one):** We reliably read Link's live Y-coordinate on the PC and
prove it's correct by moving him. **If we cannot do this, the project is not
feasible on our setup — STOP and reassess.** Everything downstream assumes this
works.

---

## Phase 2 — Full self-telemetry (single Switch)

Expand from one value to the full "who is this player" state, still single-console.

**Find & validate (via the async loop):**
- [ ] Position X / Y / Z
- [ ] Rotation / facing
- [ ] Current animation or state ID
- [ ] Health
- [ ] The stable **pointer chains** to each (raw addresses move; pointers survive
      reloads within a version).

**Build:**
- [ ] **Live visualizer** — plot Link as a moving dot on a 2D map in real time.
      Walk around; the dot tracks you. This proves the full read pipeline.
- [ ] Populate `config/addresses.<version>.json` with everything found + validation
      ranges (e.g. plausible coordinate bounds) for the "never poke garbage" rule.

**GATE 2:** A live map mirrors your movement, facing, and health from real game RAM,
sourced entirely through the config. Read-path is done.

---

## Phase 3 — The Ghost (hardest reverse-engineering)

Making a *second visible Link* appear is the deepest unknown. Isolate it here,
single-machine, before any networking.

**Investigate & build:**
- [ ] Identify a hijackable actor slot — an NPC or spare entity we can repurpose as
      a second Link body. (This is where Ghidra + the BotW decomp as reference earn
      their keep: study the actor/`BaseProc` spawn path.)
- [ ] Write position/rotation/animation *into* that ghost actor via the sysmodule.
- [ ] **Loopback test:** feed the ghost a *recorded* movement trace of yourself.
      You should see a second Link retrace your steps — no second console involved.

**GATE 3:** A ghost actor renders in-game and follows scripted/recorded input
smoothly without crashing. **This is the make-or-break research gate** — if a
usable ghost is impossible, we fall back to a reduced design (e.g. a floating
marker/beacon instead of a full body) and re-scope.

**Fallback ladder if the full ghost proves too hard:**
1. Full second Link body (ideal)
2. Repurposed simple actor (e.g. a Koroks/NPC model)
3. A map marker / on-screen indicator only (co-op "presence" without a body)

---

## Phase 4 — Two-player co-op over the PC buffer

Wire the two proven halves (read from A, write ghost on B) through the
authoritative server.

**Build:**
- [ ] **Authoritative PC server**: receives each player's state, validates, relays to
      the other, timestamps for interpolation.
- [ ] **Interpolation & jitter smoothing** on the server/PC side so ghosts move
      smoothly despite network variance.
- [ ] Two Switches connected; each sees the other as a live ghost.
- [ ] LAN first (same house, sub-ms), then internet via relay/hole-punch.

**GATE 4 — v1 MILESTONE:** You and your brother run around Hyrule and **see each
other move, turn, and animate in real time.** This is a shippable, genuinely fun
result and the core promise of the project.

---

## Phase 5 — Robustness hardening & loose combat

Make it survive real-world use and add shared stakes.

**Robustness:**
- [ ] **Reconnection & crash recovery** — a console crash or dropped link recovers
      gracefully; server tolerates a peer vanishing.
- [ ] **Desync detection** — server notices when a client's state is implausible and
      resyncs or drops it rather than propagating garbage.
- [ ] **Version-mismatch guard** — clients report their address-config/game version
      on connect; the server refuses mismatches with a clear error (prevents the
      "one guy updated and now everything crashes" disaster).
- [ ] **Watchdog** — sysmodule self-checks; on repeated bad reads it stops writing
      rather than corrupt the game.

**Loose combat (optional stretch for v1.x):**
- [ ] Sync enemy HP so hits from either player register. (Enemies still walk
      independently per console — that's expected and acceptable.)

**GATE 5:** A multi-hour session survives crashes, reconnects, and network hiccups
without corrupting saves or requiring restarts.

---

## Phase 6 — Server hosting & federation (the bigger picture)

Turn the buffer into real infrastructure so **Switch-only players** can join.

**Server hosting model:**
- [ ] Lobby / session management — a host runs the PC server; clients discover and
      join with a code/address.
- [ ] Player identity & slots — support N players (start at 2, design for more).
- [ ] A player needs only a modded Switch + sysmodule — **no PC of their own.**

**Federation / dual-PC interlink:**
- [ ] Define a **server-to-server protocol** so multiple PC servers link ("server
      interlink"). Each PC stays authoritative for its local Switches; servers
      reconcile shared world state at the boundary.
- [ ] Handle the hard parts: clock sync between servers, conflict resolution, and
      graceful partition (one server dropping shouldn't kill the others).

**GATE 6:** Two independently-hosted PC servers interlink and their players see each
other — the federation vision realized.

---

## Cross-cutting: the address-hunting workflow (used in Phases 1–3, 5)

This is the engine of the whole project, so it's called out separately:

```
You (Switch):  record a short session — walk, jump, take damage —
               tapping the ACTION TAGGER at each event → produces a tagged file
      │ send file
      ▼
PC/Claude:     analyzer diffs the recording, correlates changes to your tags,
               proposes candidate addresses + pointer chains
      │ candidate
      ▼
You (Switch):  poke the candidate in EdiZon → observe the effect → confirm/reject
      │ confirmed
      ▼
PC/Claude:     commit it to config/addresses.<version>.json
```

Because analysis is offline and file-driven, **you never need Claude "live" on the
console** — you play and record; the PC crunches afterward.

---

## Risk register (top risks × mitigations)

| Risk | Impact | Mitigation |
|---|---|---|
| Neither/one Switch is patchable | Project can't start on HW | Verify hackability **before** anything else (Phase 1 step 1) |
| Can't find/build a working ghost actor | No visible co-op | Phase 3 is an isolated gate; fallback ladder to marker-only |
| Game update breaks addresses | Total breakage | Hard version pin; version-mismatch guard; config-driven addresses |
| Writing bad RAM crashes console | Instability, save loss | Validation ranges, fail-safe skips, watchdog, save backups |
| Switch CPU too weak for sysmodule + game | Lag/crashes | Keep sysmodule featherweight; all logic on PC |
| Latency ruins the feel | Poor experience | LAN-first; interpolation; keep Switch↔PC hop local in dual-PC model |
| Legal / takedown exposure | External pressure | Keep it private between known players; own dumps + keys only |

---

## Tooling index (what we build/use, by job)

- **On-console (find addresses):** Atmosphère + `dmnt`, EdiZon-SE, JKSV.
- **Static RE (when stuck):** Ghidra + Switch Loader (or IDA + nx2elf/ida-nso-loader),
  averne's ghidra-nn-stuff, `zeldaret/botw` + botw-re-notes as the symbol Rosetta Stone.
- **Build the mod:** devkitPro/libnx (sysmodule), any language for the PC server/tools
  (Python fastest to prototype), ldn_mitm source as a networked-sysmodule reference.
- **Our custom tooling (Phase 0):** memory streamer, snapshot/diff recorder, action
  tagger, live visualizer, address config, pointer-chain resolver.

---

## What can start *right now* (before the Switch is modded)

All of Phase 0. Specifically:
1. PC receiver/recorder/analyzer/visualizer (testable on fake data).
2. Sysmodule source skeleton (compiled later).
3. Protocol v0 + address config schema.

The only things that *must* wait for a modded console are the real address values
and the ghost research.

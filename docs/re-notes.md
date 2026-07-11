# Reverse-engineering notes

Head-start knowledge for the real address mapping (Phase 1–2) and the ghost actor
(Phase 3). **Target version: 1.2.1** — chosen specifically because a real symbol set
exists for it (below). Treat on-console specifics as **hypotheses to confirm**, not
gospel.

## ⭐ PRIMARY RESOURCE: `totk_syms` (1.2.1 symbols + Ghidra types)

[`github.com/dt-12345/totk_syms`](https://github.com/dt-12345/totk_syms) — symbols and
Ghidra datatypes for **TOTK 1.2.1** (engine syms largely by **watertoon**). This is
why we pin 1.2.1. Contents:

- `exking_symbols.csv` — **136,279 named functions** (`Address,Name`), e.g.
  `game::component::Player::calc`. Turns Ghidra from "unnamed blob" into a readable map.
- `totk.gdt` — **Ghidra Data Type archive**: struct definitions → player/actor struct
  field offsets are *defined*, not guessed.
- `data_section.map` — data-section base addresses per module/namespace (vtable/global
  locations), incl. `game::component`, `engine::actor`, `game::wm`, etc.
- `func_splits.csv` — function boundary splits.

Engine is **sead-based** (same framework family as BotW), so `zeldaret/botw` +
`botw-re-notes` knowledge cross-applies.

### The functions that matter for us (confirmed present in the symbols)

Position read/write — de-risks BOTH finding the player position AND the **ghost actor**:
```
engine::actor::ActorBase::setPosition
engine::actor::ActorBase::setPositionAndRotationDirect   <- ghost: write pos+rot
engine::component::PhysicsComponent::forceSetPosition
phive::RigidBodyBase::requestSetPosition
game::component::Player::calc                            <- player update entry
game::component::Player::preCalc / updateTimers / ...    <- 5,895 Player symbols total
game::wm::WorldManagerModule                             <- singleton -> base pointer lead
```

### How to use it (Phase 2–3 workflow)

1. Load TOTK 1.2.1 `main` NSO in **Ghidra** (Switch loader).
2. Import `totk.gdt` (datatypes) and apply `exking_symbols.csv` names (script).
3. Open `ActorBase::setPosition` / `setPositionAndRotationDirect` → read which struct
   offset the position vec3 is written to (cross-check with `totk.gdt` struct layout).
4. Trace a singleton (`WorldManagerModule` / an ActorSystem) → active player actor to
   derive the **static base → offset chain** (the ASLR-safe pointer chain).
5. Confirm on-console with EdiZon-SE (poke → Link moves), write into
   `config/addresses.1.2.1.json`.
6. For the **ghost** (Phase 3): the named `setPositionAndRotationDirect` /
   `forceSetPosition` are exactly the writes to replay onto a hijacked actor.

This makes address mapping + ghost a "read the map" job, not "reverse blind."

## Build-ID table (confirm region against your console)

NSO build IDs cheat tables/patches are keyed by; **region-specific** (US/EU/JP differ) —
verify against the BID atop the EdiZon-SE overlay in-game.

| Version | Build ID | Source |
|---------|----------|--------|
| 1.0.0 | `082CE09B06E33A12` | MaxLastBreath |
| 1.1.0 | `D5AD6AC71EF53E3E` | MaxLastBreath |
| 1.1.1 | `168DD518D925C7A3` (also `9B4E43650501A4D4`, other region) | MaxLastBreath / Arithon |
| 1.1.2 | `9A10ED9435C06733` | MaxLastBreath |
| 1.2.0 | `6F32C68DD3BC7D77AA714B80E92A096A737CDA77` | UltraCam pchtxt |
| **1.2.1 (TARGET)** | **TBD — confirm on console / from totk_syms author's dump** | — |
| 1.4.2 | `5CB42B1CF25469FB0635FD046453D843C18BC8AB` | (old target; historical) |

Our confirmed 1.2.1 build ID goes in `config/addresses.1.2.1.json` `build_id`. Cheat
`.txt` files must be named `<BID>.txt` in `atmosphere/contents/0100F2C0115B6000/cheats/`.

## Secondary lead: "Moon Jump" pointer-chain shape (older version)

Cross-check for the position struct shape (from an older cheat table, base offsets
differ; useful only as a structural sanity check now that we have real symbols):
```
[main + base] -> +0xC8 -> +0x178 -> +0x30 -> (+0xFC) -> [+0x1D0] = Y position/velocity
```
X/Z should sit adjacent to Y in the same vec3.

## Why 1.2.1 over 1.4.2

Public **code cheats** exist for many versions but are behavior patches, not data. Real
**data pointers** are emulator-only (FearLess CE, ≤1.2) or absent for 1.4.2. But
**named symbols + struct types exist for 1.2.1** (`totk_syms`), which is strictly better
than a raw pointer: we can *derive* the pointer chain and struct offsets directly, and
it also hands us the ghost-actor write functions. 1.2.1 wins decisively for an
RE-driven project.

### Sources
- ⭐ `github.com/dt-12345/totk_syms` — 1.2.1 symbols + Ghidra `.gdt` (PRIMARY).
- `github.com/zeldaret/botw` + `leoetlino/botw-re-notes` — sead-engine cross-reference.
- `github.com/MaxLastBreath/TOTK-mods`, `Fl4sh9174/TOTK-mods` (UltraCam) — code cheats.
- `fearlessrevolution.com` TOTK CE tables — emulator XYZ/health pointers (≤1.2).

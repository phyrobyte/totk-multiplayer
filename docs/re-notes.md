# Reverse-engineering notes (community intel)

Head-start knowledge for the real address mapping (Phase 1–2). Treat everything here
as **hypotheses to re-confirm on 1.4.2**, not confirmed facts.

## ⚠️ Version caveat

The cheat table these hints come from targets an **old version** (`v393216`,
~1.1.x/1.2.x, `BID=9B4E43650501A4D4`, `TID=0100F2C0115B6000`). **We are pinned to
1.4.2.** Base offsets (into the main NSO) WILL differ. Re-find the static base pointer
on 1.4.2; the **struct-internal offset chains usually survive** minor patches, so reuse
them as strong starting hypotheses.

## Cheat-code format primer (Atmosphère dmnt VM)

Same VM our sysmodule uses via `dmnt:cht`. Two kinds appear:

- **Code patches** — `04 0 M ...  <offset>  <ARM instruction>`. `M=0A`/`0` = the
  **executable (main NSO)** region; the value is an ARM instruction overwriting game
  *code* to change behavior (e.g. "inf. health" NOPs the HP-subtract routine).
  **Not useful for multiplayer** — we need data, not behavior patches.
- **Pointer-chain data ops** — `58` load pointer / `78` add offset / `64` store float /
  `80..20` key-conditional. These walk a pointer chain to a **data struct** and read/
  write a value. **These are what we need.**

## Player position struct (from the "Moon Jump" cheat)

The most valuable lead — reveals the pointer path to Link's position/velocity:

```
580F0000 0471DCB0   ; reg = [main + 0x471DCB0]   <- static base pointer (OLD version)
580F1000 000000C8   ; reg = [reg + 0xC8]
580F1000 00000178   ; reg = [reg + 0x178]
580F1000 00000030   ; reg = [reg + 0x30]
780F0000 000000FC   ; reg += 0xFC
640F01D0 .. 41200000 ; [reg + 0x1D0] = 10.0f      <- vertical position/velocity write
```

**Takeaways for our address hunt:**
- Player data sits behind a **~4-hop chain** from a static main-NSO pointer.
- A **Y position/velocity** float lives near `struct + 0xFC + 0x1D0`.
- Hypothesis for 1.4.2: re-find the static base (EdiZon-SE pointer scan / MopSec's
  1.4.2 table), then try the `C8 → 178 → 30` chain; X and Z should be adjacent to Y in
  the same struct (typically ±4/±8, or a nearby vec3).

## Inventory/equipment struct (from "Bow Durability")

Deep chain into equipment data (structure reference, lower priority for us):
```
580F0000 046B9AD8 → +0x480 → +0x228 → +0x230 → +0x70 → +0x40 → +0x228 → +0x2F8 ...
```

## Known 1.4.2 build ID (confirm against your console)

From an exefs IPS patch shared in the 1.4.2 cheats thread (IPS files are named by the
target NSO build ID):

```
build_id (1.4.2, region TBD): 5CB42B1CF25469FB0635FD046453D843C18BC8AB
```

- Goes in `config/addresses.1.4.2.json` `build_id` once confirmed.
- Build IDs are **region-specific** (US/EU/JP differ) — verify it matches the BID shown
  at the top of the EdiZon-SE overlay in-game before trusting it.
- Cheat `.txt` files must be named `<BID>.txt` in `atmosphere/contents/0100F2C0115B6000/cheats/`.
- Note: exefs IPS files are **code patches** (behavior mods), NOT data-address sources —
  the multiplayer data we need comes from `58`-type pointer-chain cheat codes or our own scan.

## Leads to chase when the console is modded

1. **MopSec's "ToTK Cheats – 1.4.2 only" (GBAtemp, Jun 2026)** — our exact version. If
   it exposes the player pointer, it may hand us position directly.
2. Check EdiZon-SE / Breeze cheat DBs for a **1.4.2 build ID** table (BID shows at the
   top of the EdiZon overlay in-game).
3. HP as *data* (not the code-patch "inf health") still needs finding — known max 3000,
   steps on damage; our analyzer's tag-correlation handles it.

## How this maps to our pipeline

- The sysmodule resolves the **pointer chain** each frame (ASLR-safe), reads the vec3 +
  rotation + HP, streams the region to the PC.
- `config/addresses.1.4.2.json` stores the confirmed base pointer + offset chain +
  field offsets — the schema already supports `pointer_chains`.
- Reading/writing uses the same `dmnt` primitives these cheats use.

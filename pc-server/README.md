# PC server (authoritative buffer)

The heart of the architecture — the "buffer" both consoles connect through, which
doubles as a **host** so Switch-only players (no PC of their own) can join.

`server.py` is runnable and tested **now** against fake consoles. It:

- **Tracks** each player by `player_id`.
- **Validates** every incoming state against the address-config ranges — never relays
  garbage into another player's game (ROADMAP robustness rule #6).
- **Relays** each player's region to all other players (the "ghost" feed).
- **Drops** players that go silent (timeout).
- Enforces a config/version tag (stub; hardened in Phase 5).

## Try it (no console needed)

```bash
# terminal 1 — the server
python3 server.py

# terminals 2 & 3 — two fake consoles, different players/seeds
python3 ../pc-tools/fake_switch.py --port 9920 --player-id 1 --seed 1
python3 ../pc-tools/fake_switch.py --port 9920 --player-id 2 --seed 2
```

The server prints a live dashboard of both validated players and the relay counters:

```
  2 players  P1(X1289 Y208 Z-339 HP3000) P2(X1287 Y173 Z-339 HP3000)  relayed=167 rejected=0 bad=0
```

## What's next (console-gated)

- The **client receive path**: the sysmodule writes relayed ghost data into a
  hijacked actor (Phase 3/4) so you actually *see* the other player.
- **Interpolation/jitter smoothing** on the client side.
- **Version/address-config match** enforced on connect (Phase 5).

## Later: federation (Phase 6)

A **server-to-server interlink** so multiple PC servers share players — each stays
authoritative for its local Switches and they reconcile at the edges.

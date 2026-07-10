# PC server (authoritative buffer) — Phase 4+

Placeholder. The authoritative server that both consoles connect through. Built in
Phase 4 once the Phase 0 pipeline and the ghost actor (Phase 3) are proven.

Responsibilities (see ROADMAP.md):
- Receive each player's state, **validate** it (range-check; never relay garbage).
- Relay to the other player, timestamped for interpolation / jitter smoothing.
- Hold session/lobby state so **Switch-only clients** (no PC of their own) can join.
- Enforce a **version/address-config match** on connect (reject mismatches).

Later (Phase 6): a **server-to-server interlink** so multiple PC servers federate —
each stays authoritative for its local Switches and they reconcile at the edges.

For now, all runnable code lives in `../pc-tools/`.

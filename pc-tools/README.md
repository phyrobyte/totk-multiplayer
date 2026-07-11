# PC-side tools (Phase 0 pipeline)

The PC half of the mod: a telemetry pipeline you can build and fully test **today**
against a fake console, before any hardware exists. When the real sysmodule is
ready, it emits the same wire-protocol v0 packets and every tool works unchanged.

| Tool | Role |
|------|------|
| `protocol.py` | Shared wire-protocol v0 pack/parse + field readers (imported by the others) |
| `fake_switch.py` | Stand-in console: streams synthetic Link telemetry + tags over UDP |
| `recorder.py` | Records the stream to a tagged `recordings/session_*.jsonl` file |
| `analyzer.py` | Offline address hunter: finds coordinate-like offsets, correlates with tags |
| `visualizer.py` | Live top-down map of the player (dot + heading + trail + HP bar) |

No third-party dependencies — Python 3.9+ standard library only (see `requirements.txt`).

## Try the whole pipeline (no console needed)

**A) Watch a fake Link move live:**
```bash
# terminal 1 — the fake console
python3 fake_switch.py

# terminal 2 — live map  (run only ONE UDP consumer at a time)
python3 visualizer.py
```

> **macOS note:** the system Python (`/usr/bin/python3`) ships a broken **Tk 8.5**
> whose canvas renders blank. `visualizer.py` detects this and automatically uses the
> **terminal map** (`--tui`) instead — no flags needed. To get the graphical window,
> install python.org or Homebrew Python (Tk 8.6+) and pass `--force-gui`, or just use
> `--tui` everywhere (works on any system, even headless/SSH).

**B) Record a session, then hunt addresses offline:**
```bash
# terminal 1
python3 recorder.py --label demo

# terminal 2 — stream 60s then stop
python3 fake_switch.py --duration 60

# after it stops, analyze the newest recording and check against ground truth
python3 analyzer.py --verify ../config/sim_layout.json
```

The analyzer should surface the planted coordinate offsets (pos_x/y/z at 0x10/0x14/0x18)
as "smooth-float (coordinate-like)", flag the frame counter and noise as decoys, and
mark HP as "stepped" — proving the record → analyze → confirm loop works before the
Switch is even modded.

## When the console arrives

1. Build & run the `sysmodule/` on the modded Switch (streams real RAM in the same format).
2. `recorder.py` captures real sessions; you tap the on-console action tagger at events.
3. `analyzer.py` proposes real offsets; you confirm them in EdiZon-SE.
4. Fill `config/addresses.1.2.1.json`; point `visualizer.py --config` at it for a live
   in-game position monitor. Everything downstream is already built.

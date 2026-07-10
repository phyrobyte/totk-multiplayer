#!/usr/bin/env python3
"""visualizer.py — live view of the player from the telemetry stream.

Two render modes:
  * GUI  (default) — a Tk top-down map: dot + heading + trail + HP bar.
  * --tui          — an ANSI terminal map. No GUI deps at all; works anywhere
                     (SSH, headless, or when macOS system-Python's flaky Tk canvas
                     refuses to repaint). Guaranteed to render.

Reads a layout/address config (which offsets hold pos_x/pos_z/yaw/hp), consumes the
raw-region stream, and shows the player live. With the fake simulator this proves the
read pipeline; with the real sysmodule + a filled addresses.<version>.json it becomes
your live in-game position monitor.

NOTE: only run ONE consumer on the UDP port at a time (recorder OR visualizer).

Usage:
    python3 fake_switch.py &
    python3 visualizer.py                 # Tk window
    python3 visualizer.py --tui           # terminal map (most robust)
    python3 visualizer.py --replay recordings/session_x.jsonl --tui
"""
import argparse
import json
import math
import os
import socket
import struct
import sys
import time

import protocol as P

W, H = 640, 520
MAP_H = 420
PAD = 30
TRAIL = 120
PORT = P.DEFAULT_PORT


# --------------------------------------------------------------------------- #
# shared: turn a raw region into (x, y, z, yaw, hp) using a layout config
# --------------------------------------------------------------------------- #
def read_state(buf, fields):
    return (
        P.read_field(buf, fields["pos_x"]),
        P.read_field(buf, fields["pos_y"]),
        P.read_field(buf, fields["pos_z"]),
        P.read_field(buf, fields["yaw"]),
        P.read_field(buf, fields["hp"]),
    )


class Fit:
    """Auto-fitting bounding box: world (x,z) -> unit square [0,1]x[0,1]."""
    def __init__(self):
        self.bbox = None

    def map(self, x, z):
        if self.bbox is None:
            self.bbox = [x, x, z, z]
        b = self.bbox
        b[0], b[1] = min(b[0], x), max(b[1], x)
        b[2], b[3] = min(b[2], z), max(b[3], z)
        rx = (b[1] - b[0]) or 1.0
        rz = (b[3] - b[2]) or 1.0
        return (x - b[0]) / rx, (z - b[2]) / rz


# --------------------------------------------------------------------------- #
# packet sources
# --------------------------------------------------------------------------- #
def live_source(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.setblocking(False)
    latest = {"buf": None}

    def pull():
        while True:
            try:
                data, _ = sock.recvfrom(65535)
            except (BlockingIOError, socket.error):
                break
            pkt = P.parse(data)
            if pkt and pkt["msg_type"] == P.MSG_RAW_REGION:
                latest["buf"] = pkt["payload"]
        return latest["buf"]

    return pull


def replay_source(path, rate):
    frames = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["type"] == "raw":
                frames.append(bytes.fromhex(rec["hex"]))
    state = {"i": 0, "t": time.monotonic()}
    step = 1.0 / rate

    def pull():
        now = time.monotonic()
        if frames and now - state["t"] >= step:
            state["t"] = now
            state["i"] = (state["i"] + 1) % len(frames)
        return frames[state["i"]] if frames else None

    return pull


# --------------------------------------------------------------------------- #
# TUI (terminal) renderer — robust, dependency-free
# --------------------------------------------------------------------------- #
def run_tui(source, layout, duration=0.0, fps=15.0):
    fields = layout["fields"]
    region_size = layout["region"]["size"]
    cols, rows = 62, 22
    fit = Fit()
    trail = []
    hpmax = fields["hp"].get("max", 3000) or 3000
    last = None

    sys.stdout.write("\033[2J\033[?25l")   # clear + hide cursor
    t0 = time.monotonic()
    try:
        while True:
            if duration and time.monotonic() - t0 >= duration:
                break
            buf = source()
            if buf is not None and len(buf) >= region_size:
                try:
                    last = read_state(buf, fields)
                    ux, uz = fit.map(last[0], last[2])
                    cx = min(cols - 1, max(0, int(ux * (cols - 1))))
                    cy = min(rows - 1, max(0, int(uz * (rows - 1))))
                    trail.append((cx, cy))
                    if len(trail) > 40:
                        trail.pop(0)
                except (struct.error, KeyError):
                    pass

            grid = [[" "] * cols for _ in range(rows)]
            for (tx, ty) in trail[:-1]:
                grid[ty][tx] = "·"          # trail dot
            if trail:
                px, py = trail[-1]
                grid[py][px] = "@"

            out = ["\033[H"]                       # cursor home
            out.append("  TOTK telemetry — live terminal map  (Ctrl-C to quit)\n")
            top = "  ┌" + "─" * cols + "┐\n"
            out.append(top)
            for r in range(rows):
                row = "".join(grid[r])
                # highlight the player glyph in cyan
                row = row.replace("@", "\033[96m@\033[0m")
                out.append("  │" + row + "│\n")
            out.append("  └" + "─" * cols + "┘\n")
            if last is None:
                out.append("  waiting for packets on :%d ...\n" % PORT)
            else:
                x, y, z, yaw, hp = last
                out.append("  X %-9.1f Y %-9.1f Z %-9.1f yaw %-6.2f\n" % (x, y, z, yaw))
                frac = max(0.0, min(1.0, hp / hpmax))
                barw = 40
                filled = int(frac * barw)
                bar = "█" * filled + "░" * (barw - filled)
                col = "92" if frac > 0.5 else ("93" if frac > 0.25 else "91")
                out.append("  HP \033[%sm%s\033[0m %d/%d      \n" % (col, bar, int(hp), int(hpmax)))
            sys.stdout.write("".join(out))
            sys.stdout.flush()
            time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")           # restore cursor
        sys.stdout.flush()


# --------------------------------------------------------------------------- #
# GUI (Tk) renderer — with macOS repaint workaround
# --------------------------------------------------------------------------- #
def run_gui(source, layout, topmost=False):
    import tkinter as tk

    fields = layout["fields"]
    region_size = layout["region"]["size"]
    hpmax = fields["hp"].get("max", 3000) or 3000

    root = tk.Tk()
    root.title("TOTK telemetry — live map")
    canvas = tk.Canvas(root, width=W, height=H, bg="#0e1116", highlightthickness=0)
    canvas.pack()

    state = {"last": None, "trail": [], "fit": Fit()}

    def tick():
        buf = source()
        if buf is not None and len(buf) >= region_size:
            try:
                st = read_state(buf, fields)
                ux, uz = state["fit"].map(st[0], st[2])
                cx = PAD + ux * (W - 2 * PAD)
                cy = PAD + uz * (MAP_H - 2 * PAD)
                state["last"] = st
                state["trail"].append((cx, cy))
                if len(state["trail"]) > TRAIL:
                    state["trail"].pop(0)
            except (struct.error, KeyError):
                pass
        draw()
        canvas.update_idletasks()          # force repaint (macOS Tk workaround)
        canvas.after(16, tick)

    def draw():
        c = canvas
        c.delete("all")
        # grid
        for gx in range(0, W, 40):
            c.create_line(gx, 0, gx, MAP_H, fill="#161c26")
        for gy in range(0, MAP_H, 40):
            c.create_line(0, gy, W, gy, fill="#161c26")
        c.create_rectangle(2, 2, W - 2, MAP_H, outline="#3a4657")
        c.create_text(10, 12, anchor="w", fill="#8b98a8",
                      text="top-down map (X / Z)", font=("Menlo", 10))
        trail = state["trail"]
        for i in range(1, len(trail)):
            x0, y0 = trail[i - 1]
            x1, y1 = trail[i]
            s = int(60 + 150 * i / len(trail))
            c.create_line(x0, y0, x1, y1, fill="#%02x%02x%02x" % (s // 2, s, s), width=2)
        if state["last"] is None:
            c.create_text(W / 2, MAP_H / 2, fill="#8b98a8",
                          text="waiting for packets on :%d ..." % PORT, font=("Menlo", 13))
        else:
            x, y, z, yaw, hp = state["last"]
            cx, cy = trail[-1]
            c.create_line(cx, cy, cx + 24 * math.cos(yaw), cy + 24 * math.sin(yaw),
                          fill="#7fd6ff", width=2)
            c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#4fc3f7", outline="#e3f2fd")
            c.create_text(10, MAP_H + 22, anchor="w", fill="#c8d2de", font=("Menlo", 12),
                          text="X %.1f   Y %.1f   Z %.1f   yaw %.2f" % (x, y, z, yaw))
            frac = max(0.0, min(1.0, hp / hpmax))
            bx, by, bw = 10, MAP_H + 48, W - 20
            c.create_rectangle(bx, by, bx + bw, by + 18, outline="#3a4657")
            col = "#4caf50" if frac > 0.5 else ("#ffb300" if frac > 0.25 else "#e53935")
            c.create_rectangle(bx, by, bx + bw * frac, by + 18, fill=col, outline="")
            c.create_text(bx + 6, by + 9, anchor="w", fill="#0e1116", font=("Menlo", 11, "bold"),
                          text="HP %d / %d" % (int(hp), int(hpmax)))

    # --- macOS system-Tk workaround: force the window to paint by nudging it ---
    def kick():
        root.update_idletasks()
        root.geometry("%dx%d" % (W, H + 1))
        root.after(40, lambda: root.geometry("%dx%d" % (W, H)))
    root.after(120, kick)
    root.lift()
    root.focus_force()
    try:
        root.attributes("-topmost", True)
        if not topmost:
            root.after(600, lambda: root.attributes("-topmost", False))
    except tk.TclError:
        pass

    tick()
    root.mainloop()


def main():
    global PORT
    ap = argparse.ArgumentParser(description="Live telemetry view (GUI or terminal)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=P.DEFAULT_PORT)
    ap.add_argument("--config", default=os.path.join(P.repo_config_dir(), "sim_layout.json"),
                    help="field offsets to read (sim_layout.json or addresses.<v>.json)")
    ap.add_argument("--replay", default=None, help="replay a recorded session instead of live UDP")
    ap.add_argument("--replay-rate", type=float, default=30.0)
    ap.add_argument("--tui", action="store_true", help="terminal renderer (most robust)")
    ap.add_argument("--force-gui", action="store_true",
                    help="use the Tk GUI even if a broken system Tk is detected")
    ap.add_argument("--topmost", action="store_true", help="keep GUI window always on top")
    ap.add_argument("--duration", type=float, default=0.0, help="auto-exit after N seconds (TUI)")
    args = ap.parse_args()
    PORT = args.port

    # macOS system Python ships the deprecated Tk 8.5, which renders a blank canvas.
    # Auto-fall back to the terminal renderer, which always works.
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    if not args.tui and not args.force_gui:
        try:
            import tkinter
            if tkinter.TkVersion < 8.6:
                print("visualizer: detected deprecated Tk %.1f (macOS system Python) — its "
                      "canvas renders blank." % tkinter.TkVersion)
                print("visualizer: using the terminal view instead. For the GUI window, install "
                      "python.org / Homebrew Python (Tk 8.6+) and pass --force-gui.")
                args.tui = True
        except Exception:
            pass

    layout = P.load_layout(args.config)
    if args.replay:
        source = replay_source(args.replay, args.replay_rate)
        print("visualizer: replaying %s" % args.replay)
    else:
        source = live_source(args.host, args.port)
        print("visualizer: live on %s:%d (run only one UDP consumer at a time)"
              % (args.host, args.port))

    if args.tui:
        run_tui(source, layout, duration=args.duration)
    else:
        run_gui(source, layout, topmost=args.topmost)


if __name__ == "__main__":
    main()

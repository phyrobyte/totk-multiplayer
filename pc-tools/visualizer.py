#!/usr/bin/env python3
"""visualizer.py — live top-down map of the player from the telemetry stream.

Reads a layout/address config (which offsets hold pos_x/pos_z/yaw/hp), consumes the
raw-region stream, and draws Link as a moving dot with a heading line and trail,
plus an HP bar. With the fake simulator this proves the read pipeline end-to-end;
with the real sysmodule + a filled addresses.<version>.json it becomes your live
in-game position monitor.

NOTE: only run ONE consumer on the UDP port at a time (recorder OR visualizer).
To watch a captured session instead of a live stream, use --replay.

Usage:
    python3 fake_switch.py &                 # in one terminal
    python3 visualizer.py                    # live view
    python3 visualizer.py --replay recordings/session_x.jsonl
"""
import argparse
import json
import math
import os
import socket
import struct
import time
import tkinter as tk

import protocol as P

W, H = 640, 520
MAP_H = 420
PAD = 30
TRAIL = 120


class Viz:
    def __init__(self, root, layout, source):
        self.layout = layout
        self.f = layout["fields"]
        self.source = source  # callable -> latest region bytes or None
        self.trail = []
        self.bbox = None      # [minx, maxx, minz, maxz]
        self.last = None

        self.canvas = tk.Canvas(root, width=W, height=H, bg="#0e1116", highlightthickness=0)
        self.canvas.pack()
        root.title("TOTK telemetry — live map")
        self.tick()

    def _fit(self, x, z):
        if self.bbox is None:
            self.bbox = [x, x, z, z]
        self.bbox[0] = min(self.bbox[0], x)
        self.bbox[1] = max(self.bbox[1], x)
        self.bbox[2] = min(self.bbox[2], z)
        self.bbox[3] = max(self.bbox[3], z)
        minx, maxx, minz, maxz = self.bbox
        rx = (maxx - minx) or 1.0
        rz = (maxz - minz) or 1.0
        cx = PAD + (x - minx) / rx * (W - 2 * PAD)
        cy = PAD + (z - minz) / rz * (MAP_H - 2 * PAD)
        return cx, cy

    def tick(self):
        buf = self.source()
        if buf is not None and len(buf) >= self.layout["region"]["size"]:
            try:
                x = P.read_field(buf, self.f["pos_x"])
                z = P.read_field(buf, self.f["pos_z"])
                y = P.read_field(buf, self.f["pos_y"])
                yaw = P.read_field(buf, self.f["yaw"])
                hp = P.read_field(buf, self.f["hp"])
                self.last = (x, y, z, yaw, hp)
                cx, cy = self._fit(x, z)
                self.trail.append((cx, cy))
                if len(self.trail) > TRAIL:
                    self.trail.pop(0)
            except (struct.error, KeyError):
                pass
        self.draw()
        self.canvas.after(16, self.tick)

    def draw(self):
        c = self.canvas
        c.delete("all")
        # map frame
        c.create_rectangle(2, 2, W - 2, MAP_H, outline="#2b3340")
        c.create_text(10, 12, anchor="w", fill="#5b6675", text="top-down map (X / Z)", font=("Menlo", 10))
        # trail
        for i in range(1, len(self.trail)):
            x0, y0 = self.trail[i - 1]
            x1, y1 = self.trail[i]
            shade = int(40 + 120 * i / len(self.trail))
            c.create_line(x0, y0, x1, y1, fill="#%02x%02x%02x" % (shade // 2, shade, shade), width=2)
        if self.last is None:
            c.create_text(W / 2, MAP_H / 2, fill="#5b6675",
                          text="waiting for packets on :%d ..." % PORT, font=("Menlo", 13))
        else:
            x, y, z, yaw, hp = self.last
            cx, cy = self.trail[-1]
            # heading line
            c.create_line(cx, cy, cx + 22 * math.cos(yaw), cy + 22 * math.sin(yaw),
                          fill="#7fd6ff", width=2)
            c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#4fc3f7", outline="#e3f2fd")
            # readouts
            c.create_text(10, MAP_H + 22, anchor="w", fill="#c8d2de", font=("Menlo", 12),
                          text="X %.1f   Y %.1f   Z %.1f   yaw %.2f" % (x, y, z, yaw))
            # hp bar
            hpmax = self.f["hp"].get("max", 3000) or 3000
            frac = max(0.0, min(1.0, hp / hpmax))
            bx, by, bw = 10, MAP_H + 48, W - 20
            c.create_rectangle(bx, by, bx + bw, by + 18, outline="#2b3340")
            col = "#4caf50" if frac > 0.5 else ("#ffb300" if frac > 0.25 else "#e53935")
            c.create_rectangle(bx, by, bx + bw * frac, by + 18, fill=col, outline="")
            c.create_text(bx + 6, by + 9, anchor="w", fill="#0e1116", font=("Menlo", 11, "bold"),
                          text="HP %d / %d" % (int(hp), int(hpmax)))


PORT = P.DEFAULT_PORT


def live_source(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.setblocking(False)
    latest = {"buf": None}

    def pull():
        # drain to the newest raw packet available this frame
        while True:
            try:
                data, _ = sock.recvfrom(65535)
            except BlockingIOError:
                break
            except socket.error:
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


def main():
    global PORT
    ap = argparse.ArgumentParser(description="Live telemetry map")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=P.DEFAULT_PORT)
    ap.add_argument("--config", default=os.path.join(P.repo_config_dir(), "sim_layout.json"),
                    help="which field offsets to read (sim_layout.json or addresses.<v>.json)")
    ap.add_argument("--replay", default=None, help="replay a recorded session instead of live UDP")
    ap.add_argument("--replay-rate", type=float, default=30.0)
    args = ap.parse_args()
    PORT = args.port

    layout = P.load_layout(args.config)
    if args.replay:
        source = replay_source(args.replay, args.replay_rate)
        print("visualizer: replaying %s" % args.replay)
    else:
        source = live_source(args.host, args.port)
        print("visualizer: live on %s:%d (run only one UDP consumer at a time)" % (args.host, args.port))

    root = tk.Tk()
    Viz(root, layout, source)
    root.mainloop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""fake_switch.py — a stand-in for the real Switch sysmodule.

Simulates a modded console running TOTK: it holds a block of "game RAM", moves a
fake Link around a path, and streams the raw region over UDP in wire-protocol v0 —
exactly the packets the real sysmodule will send. It also emits TAG packets on
jump/damage events, standing in for the human pressing the on-console action tagger.

Because we plant known values at the offsets in config/sim_layout.json, this lets us
build AND verify the entire PC pipeline (recorder, analyzer, visualizer) with a
known ground truth, before any hardware exists.

Usage:
    python3 fake_switch.py                 # stream to 127.0.0.1:9917 at 30 Hz forever
    python3 fake_switch.py --rate 60 --duration 120
"""
import argparse
import math
import os
import random
import socket
import struct
import time

import protocol as P


def main():
    ap = argparse.ArgumentParser(description="Fake Switch telemetry simulator")
    ap.add_argument("--host", default=P.DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=P.DEFAULT_PORT)
    ap.add_argument("--rate", type=float, default=30.0, help="packets per second")
    ap.add_argument("--duration", type=float, default=0.0, help="seconds (0 = forever)")
    ap.add_argument("--player-id", type=int, default=1)
    ap.add_argument("--layout", default=os.path.join(P.repo_config_dir(), "sim_layout.json"))
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    random.seed(args.seed)
    layout = P.load_layout(args.layout)
    size = layout["region"]["size"]
    f = layout["fields"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)
    region = bytearray(size)

    print("fake_switch: streaming %d-byte region to %s:%d at %.0f Hz (player %d)"
          % (size, args.host, args.port, args.rate, args.player_id))
    print("fake_switch: ground truth = %s" % args.layout)

    hp = 3000
    anim = 1               # 1 = run/idle
    jump_until = 0.0       # time the current jump arc ends
    next_jump = 3.0
    next_damage = 6.0
    period = 1.0 / args.rate
    seq = 0
    t0 = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            t = now - t0
            if args.duration and t >= args.duration:
                break

            # --- smooth ground motion (coordinates the analyzer should find) ---
            x = 1000.0 + 500.0 * math.sin(0.20 * t)
            z = -800.0 + 500.0 * math.cos(0.13 * t)
            y = 120.0 + 20.0 * math.sin(0.5 * t)           # gentle terrain
            yaw = math.atan2(math.cos(0.13 * t), math.cos(0.20 * t))  # ~facing of travel

            # --- jump: parabolic pop in Y, tagged like a human would ---
            if t >= next_jump and now >= jump_until:
                jump_until = now + 0.8
                next_jump = t + random.uniform(5.0, 9.0)
                anim = 2
                _send_tag(sock, dest, args.player_id, seq, "jump")
            if now < jump_until:
                jp = 1.0 - (jump_until - now) / 0.8          # 0..1
                y += 200.0 * (jp - jp * jp) * 4.0            # arc peak ~200
            else:
                if anim == 2:
                    anim = 1

            # --- damage: stepped HP drop, tagged ---
            if t >= next_damage:
                dmg = random.choice([100, 200, 300])
                hp = max(0, hp - dmg)
                next_damage = t + random.uniform(8.0, 14.0)
                _send_tag(sock, dest, args.player_id, seq, "damage")
            else:
                if hp < 3000 and int(t * 10) % 5 == 0:
                    hp = min(3000, hp + 1)                   # slow regen

            # --- write planted fields into the region ---
            P.write_f32(region, f["pos_x"]["offset"], x)
            P.write_f32(region, f["pos_y"]["offset"], y)
            P.write_f32(region, f["pos_z"]["offset"], z)
            P.write_f32(region, f["yaw"]["offset"], yaw)
            P.write_u32(region, f["anim"]["offset"], anim)
            P.write_u32(region, f["hp"]["offset"], hp)

            # --- decoys, so the analyzer has to actually discriminate ---
            struct.pack_into("<I", region, 0, seq)            # frame counter (monotonic)
            struct.pack_into("<I", region, 4, random.randint(0, 2**32 - 1))  # pure noise
            struct.pack_into("<f", region, 56, random.uniform(-1e6, 1e6))    # noisy float

            pkt = P.pack(P.MSG_RAW_REGION, bytes(region),
                         player_id=args.player_id, seq=seq, t_send=now, region_off=0)
            sock.sendto(pkt, dest)
            seq += 1

            sleep = period - (time.monotonic() - now)
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        pass

    print("\nfake_switch: sent %d packets over %.1fs" % (seq, time.monotonic() - t0))


def _send_tag(sock, dest, player_id, seq, label):
    sock.sendto(P.pack(P.MSG_TAG, label, player_id=player_id, seq=seq,
                       t_send=time.monotonic()), dest)


if __name__ == "__main__":
    main()

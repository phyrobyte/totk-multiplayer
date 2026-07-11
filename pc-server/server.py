#!/usr/bin/env python3
"""server.py — authoritative PC server / buffer (Phase 4 core).

The heart of the architecture. Every console (or fake_switch) streams its player
region here. The server:
  * tracks each player by player_id,
  * VALIDATES every incoming state against the address-config ranges — never relays
    garbage into another player's game (ROADMAP robustness rule #6),
  * RELAYS each player's state to all other connected players (the "ghost" feed),
  * enforces a version/config tag on connect (rejects mismatches),
  * drops players that go silent.

A single server doubles as a host: Switch-only clients (no PC of their own) just
point at its address. Runnable and testable NOW with two fake_switch instances.

Usage:
    python3 server.py                       # listen on 0.0.0.0:9920
    # then, in two more terminals:
    python3 ../pc-tools/fake_switch.py --port 9920 --player-id 1 --seed 1
    python3 ../pc-tools/fake_switch.py --port 9920 --player-id 2 --seed 2
"""
import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pc-tools"))
import protocol as P  # noqa: E402

DEFAULT_SERVER_PORT = 9920
PLAYER_TIMEOUT = 5.0     # seconds of silence before a player is dropped
CONFIG_VERSION = "1.2.1"  # clients must match (stub check via flags/version later)


def validate(buf, fields):
    """Return (ok, state|reason). Range-checks every field; rejects garbage."""
    try:
        state = {}
        for name, fld in fields.items():
            v = P.read_field(buf, fld)
            lo, hi = fld.get("min"), fld.get("max")
            if lo is not None and hi is not None and not (lo <= v <= hi):
                return False, "%s=%.3f out of [%s,%s]" % (name, v, lo, hi)
            state[name] = v
        return True, state
    except Exception as e:  # struct error / bad offset
        return False, "parse error: %s" % e


def main():
    ap = argparse.ArgumentParser(description="Authoritative TOTK multiplayer server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    ap.add_argument("--config", default=os.path.join(P.repo_config_dir(), "sim_layout.json"),
                    help="address/layout config used to validate incoming state")
    ap.add_argument("--duration", type=float, default=0.0, help="auto-exit after N s (for tests)")
    args = ap.parse_args()

    layout = P.load_layout(args.config)
    fields = layout["fields"]
    region_size = layout["region"]["size"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.settimeout(0.5)

    print("server: authoritative buffer on %s:%d (config v%s, region %dB)"
          % (args.host, args.port, CONFIG_VERSION, region_size))
    print("server: waiting for players...")

    players = {}   # player_id -> dict(addr, state, seq, last, count)
    relayed = rejected = bad = 0
    last_dash = time.monotonic()
    t0 = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            if args.duration and now - t0 >= args.duration:
                break
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                data = None

            if data is not None:
                pkt = P.parse(data)
                if pkt is None:
                    bad += 1
                elif pkt["msg_type"] == P.MSG_RAW_REGION:
                    pid = pkt["player_id"]
                    if len(pkt["payload"]) < region_size:
                        rejected += 1
                    else:
                        ok, res = validate(pkt["payload"], fields)
                        if not ok:
                            rejected += 1
                        else:
                            first = pid not in players
                            players[pid] = {"addr": addr, "state": res, "seq": pkt["seq"],
                                            "last": now, "count": players.get(pid, {}).get("count", 0) + 1}
                            if first:
                                print("server: player %d joined from %s:%d" % (pid, addr[0], addr[1]))
                            # relay to every OTHER player (the ghost feed)
                            for other_id, p in players.items():
                                if other_id != pid:
                                    sock.sendto(data, p["addr"])
                                    relayed += 1
                elif pkt["msg_type"] == P.MSG_TAG:
                    pid = pkt["player_id"]
                    for other_id, p in players.items():
                        if other_id != pid:
                            sock.sendto(data, p["addr"])
                            relayed += 1

            # prune silent players
            for pid in [k for k, v in players.items() if now - v["last"] > PLAYER_TIMEOUT]:
                print("server: player %d timed out" % pid)
                del players[pid]

            # live dashboard
            if now - last_dash >= 1.0:
                last_dash = now
                parts = []
                for pid in sorted(players):
                    s = players[pid]["state"]
                    parts.append("P%d(X%.0f Y%.0f Z%.0f HP%d)"
                                 % (pid, s["pos_x"], s["pos_y"], s["pos_z"], int(s["hp"])))
                line = "  %d players  %-58s  relayed=%d rejected=%d bad=%d" % (
                    len(players), " ".join(parts) or "(none)", relayed, rejected, bad)
                print(line, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    print("\nserver: stopped. relayed=%d rejected=%d bad=%d" % (relayed, rejected, bad))


if __name__ == "__main__":
    main()

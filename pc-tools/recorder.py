#!/usr/bin/env python3
"""recorder.py — receive the telemetry stream and record it to a session file.

Binds a UDP port, decodes wire-protocol v0 packets, and appends each one to a
timestamped JSONL session file under recordings/. RAW_REGION payloads are stored
hex-encoded; TAG packets are stored as labels. The analyzer consumes these files
offline, so you can play/record a session on the console and analyze it later.

Usage:
    python3 recorder.py                      # listen on 0.0.0.0:9917, write recordings/session_<ts>.jsonl
    python3 recorder.py --port 9917 --label climb_test
"""
import argparse
import json
import os
import socket
import time

import protocol as P


def main():
    ap = argparse.ArgumentParser(description="Record telemetry stream to a session file")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=P.DEFAULT_PORT)
    ap.add_argument("--label", default="", help="optional name baked into the filename")
    ap.add_argument("--outdir", default=None, help="recordings dir (default: ../recordings)")
    args = ap.parse_args()

    outdir = args.outdir or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recordings"))
    os.makedirs(outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = "session_%s%s.jsonl" % (stamp, ("_" + args.label) if args.label else "")
    path = os.path.join(outdir, name)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)

    print("recorder: listening on %s:%d" % (args.host, args.port))
    print("recorder: writing %s" % path)
    print("recorder: Ctrl-C to stop.")

    n_raw = n_tag = n_bad = 0
    last_report = time.monotonic()
    count_since = 0
    f = open(path, "w")
    try:
        while True:
            try:
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            t_recv = time.time()
            pkt = P.parse(data)
            if pkt is None:
                n_bad += 1
                continue

            if pkt["msg_type"] == P.MSG_RAW_REGION:
                rec = {"seq": pkt["seq"], "t_recv": t_recv, "t_send": pkt["t_send"],
                       "type": "raw", "player_id": pkt["player_id"],
                       "off": pkt["region_off"], "hex": pkt["payload"].hex()}
                n_raw += 1
            elif pkt["msg_type"] == P.MSG_TAG:
                rec = {"seq": pkt["seq"], "t_recv": t_recv, "t_send": pkt["t_send"],
                       "type": "tag", "player_id": pkt["player_id"],
                       "label": pkt["payload"].decode("utf-8", "replace")}
                n_tag += 1
            else:
                rec = {"seq": pkt["seq"], "t_recv": t_recv, "t_send": pkt["t_send"],
                       "type": "other", "msg_type": pkt["msg_type"],
                       "hex": pkt["payload"].hex()}

            f.write(json.dumps(rec) + "\n")
            count_since += 1

            now = time.monotonic()
            if now - last_report >= 1.0:
                pps = count_since / (now - last_report)
                print("  raw=%d tag=%d bad=%d  (%.0f pkt/s)" % (n_raw, n_tag, n_bad, pps),
                      end="\r", flush=True)
                last_report = now
                count_since = 0
    except KeyboardInterrupt:
        pass
    finally:
        f.close()
        sock.close()

    print("\nrecorder: saved %d raw + %d tag packets to %s" % (n_raw, n_tag, path))


if __name__ == "__main__":
    main()

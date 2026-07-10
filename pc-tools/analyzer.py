#!/usr/bin/env python3
"""analyzer.py — offline address hunter.

Loads a recorded session (from recorder.py), reconstructs the raw memory region as
a time series, and scores every 4-byte-aligned offset for how "coordinate-like" it
behaves — smooth, continuous float motion — versus counters, stepped values, and
noise. It also correlates big changes against TAG events so you can tell, e.g., that
the offset which spikes on every "jump" tag is a height coordinate.

This is the PC-side half of the record -> analyze -> confirm loop. With the fake
simulator it has a known ground truth, so `--verify` proves the heuristics work
before real memory ever exists.

Usage:
    python3 analyzer.py                                  # analyze newest recording
    python3 analyzer.py recordings/session_x.jsonl
    python3 analyzer.py --verify config/sim_layout.json  # check finds vs planted truth
"""
import argparse
import glob
import json
import math
import os
import struct

import protocol as P


def load_session(path):
    frames = []   # list of (t_send, bytes)
    tags = []     # list of (t_send, label)
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["type"] == "raw":
                frames.append((rec["t_send"], bytes.fromhex(rec["hex"])))
            elif rec["type"] == "tag":
                tags.append((rec["t_send"], rec["label"]))
    frames.sort(key=lambda r: r[0])
    tags.sort(key=lambda r: r[0])
    return frames, tags


def newest_recording():
    d = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "recordings"))
    files = sorted(glob.glob(os.path.join(d, "session_*.jsonl")))
    return files[-1] if files else None


def _series_f32(frames, off):
    out = []
    for _t, buf in frames:
        if off + 4 <= len(buf):
            v = struct.unpack_from("<f", buf, off)[0]
            out.append(v)
    return out


def _series_u32(frames, off):
    return [struct.unpack_from("<I", buf, off)[0]
            for _t, buf in frames if off + 4 <= len(buf)]


def classify_offset(frames, off):
    """Return a dict describing how the value at `off` behaves over time."""
    fv = _series_f32(frames, off)
    uv = _series_u32(frames, off)
    if len(fv) < 3:
        return None

    finite = [v for v in fv if math.isfinite(v)]
    distinct = len(set(fv))
    n = len(fv)

    # float smoothness metrics
    fmin, fmax = (min(finite), max(finite)) if finite else (0.0, 0.0)
    frange = fmax - fmin
    deltas = [abs(fv[i] - fv[i - 1]) for i in range(1, n)
              if math.isfinite(fv[i]) and math.isfinite(fv[i - 1])]
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    max_delta = max(deltas) if deltas else 0.0
    # smoothness = typical step is small relative to overall range
    smoothness = 1.0 - min(1.0, (mean_delta / frange)) if frange > 1e-6 else 0.0

    # u32 counter detection
    u_deltas = [uv[i] - uv[i - 1] for i in range(1, len(uv))]
    is_counter = len(u_deltas) > 2 and all(d == u_deltas[0] for d in u_deltas) and u_deltas[0] != 0

    # scoring
    plausible_coord = (
        len(finite) == n and                     # always a valid float
        frange > 1.0 and                          # actually moves
        distinct > n * 0.3 and                    # lots of distinct values
        smoothness > 0.9 and                      # small steps vs range
        abs(fmax) < 1e6 and abs(fmin) < 1e6       # sane magnitude
    )
    coord_score = smoothness * min(1.0, distinct / n) if plausible_coord else 0.0

    if is_counter:
        kind = "counter"
    elif plausible_coord:
        kind = "smooth-float (coordinate-like)"
    elif distinct <= max(6, n * 0.1) and distinct > 1:
        kind = "stepped (health/state-like)"
    elif frange > 1e5 or (len(finite) < n):
        kind = "noise/decoy"
    else:
        kind = "static/other"

    return {
        "off": off, "kind": kind, "coord_score": coord_score,
        "distinct": distinct, "n": n,
        "fmin": fmin, "fmax": fmax, "frange": frange,
        "mean_delta": mean_delta, "max_delta": max_delta,
        "smoothness": smoothness, "is_counter": is_counter,
        "last_f32": fv[-1], "last_u32": uv[-1] if uv else None,
    }


def correlate_tags(frames, tags, off, window=0.4):
    """How strongly do big changes at `off` line up with tag events? 0..1."""
    if not tags:
        return 0.0, []
    fv = _series_f32(frames, off)
    times = [t for t, _b in frames]
    labels_hit = []
    hits = 0
    for tt, label in tags:
        # find frame indices within +/- window of the tag
        idxs = [i for i, ft in enumerate(times) if abs(ft - tt) <= window]
        if len(idxs) < 2:
            continue
        seg = [fv[i] for i in idxs if math.isfinite(fv[i])]
        if len(seg) < 2:
            continue
        local_range = max(seg) - min(seg)
        overall = (max(v for v in fv if math.isfinite(v))
                   - min(v for v in fv if math.isfinite(v))) or 1.0
        if local_range > 0.15 * overall:      # notable local movement at the tag
            hits += 1
            labels_hit.append(label)
    return hits / len(tags), labels_hit


def main():
    ap = argparse.ArgumentParser(description="Offline memory address hunter")
    ap.add_argument("session", nargs="?", help="session .jsonl (default: newest)")
    ap.add_argument("--step", type=int, default=4, help="offset stride to scan")
    ap.add_argument("--top", type=int, default=12, help="how many candidates to show")
    ap.add_argument("--verify", default=None, help="layout/addresses json with ground truth")
    args = ap.parse_args()

    path = args.session or newest_recording()
    if not path or not os.path.exists(path):
        print("analyzer: no session file found. Run recorder.py + fake_switch.py first.")
        return
    frames, tags = load_session(path)
    if len(frames) < 3:
        print("analyzer: not enough frames in %s" % path)
        return
    size = len(frames[0][1])
    print("analyzer: %s" % path)
    print("analyzer: %d frames, %d tags, region size %d bytes\n" % (len(frames), len(tags), size))

    results = []
    for off in range(0, size - 3, args.step):
        c = classify_offset(frames, off)
        if c is None:
            continue
        corr, labels = correlate_tags(frames, tags, off)
        c["tag_corr"] = corr
        c["tag_labels"] = sorted(set(labels))
        results.append(c)

    ranked = sorted(results, key=lambda c: (c["coord_score"], c["tag_corr"]), reverse=True)

    print("Top candidate offsets (coordinate-like first):")
    print("  %-8s %-32s %-8s %-7s %-6s %s" %
          ("offset", "kind", "score", "tagcorr", "distinct", "last value"))
    for c in ranked[:args.top]:
        off_hex = "0x%02X" % c["off"]
        lastv = ("%.2f" % c["last_f32"]) if "coordinate" in c["kind"] else str(c["last_u32"])
        tags_s = ("<-" + ",".join(c["tag_labels"])) if c["tag_labels"] else ""
        print("  %-8s %-32s %-8.3f %-7.2f %-6d %s %s" %
              (off_hex, c["kind"], c["coord_score"], c["tag_corr"], c["distinct"], lastv, tags_s))

    if args.verify:
        _verify(ranked, args.verify)


def _verify(ranked, layout_path):
    layout = P.load_layout(layout_path)
    fields = layout["fields"]
    by_off = {c["off"]: c for c in ranked}
    print("\nVerify against ground truth (%s):" % layout_path)
    ok = 0
    for name, fld in fields.items():
        off = fld["offset"]
        c = by_off.get(off)
        if not c:
            print("  %-6s @0x%02X  MISSED (offset not scanned)" % (name, off))
            continue
        role = fld.get("role", "")
        # did we classify it in a sensible bucket for its true role?
        good = (
            (role == "coordinate" and "coordinate" in c["kind"]) or
            (role == "rotation" and ("coordinate" in c["kind"] or "smooth" in c["kind"])) or
            (role == "health" and "stepped" in c["kind"]) or
            (role == "state" and c["kind"] in ("stepped (health/state-like)", "counter", "static/other")) or
            (role not in ("coordinate", "rotation", "health", "state"))
        )
        mark = "OK " if good else "??"
        if good:
            ok += 1
        print("  %s %-6s @0x%02X  role=%-10s -> classified '%s'"
              % (mark, name, off, role, c["kind"]))
    print("  %d/%d planted fields classified sensibly." % (ok, len(fields)))


if __name__ == "__main__":
    main()

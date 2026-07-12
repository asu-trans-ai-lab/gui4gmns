#!/usr/bin/env python3
"""verify_semidynamic.py -- verify adapters/semidynamic_trajectories.py against FIRST PRINCIPLES.

The adapter's whole claim is that a synthesized vehicle traverses each link in exactly the
time-dependent travel time the link data prescribes at the moment it enters. When the 15-min data
carries a `speed` column, that travel time is unambiguous physics: tt = length / speed. So rather than
re-implementing (and risking drift from) the adapter's internal BPR/queue logic, this checks the
synthesized agent_trajectory.csv against distance/speed directly -- an independent ground truth (M-B).

Runs the adapter itself, then for every (ENB, EXB) pair on a link asserts
    exit_time - enter_time  ==  length_mi / speed_at(link, enter-bin) * 60   (minutes)

Usage: python qa/verify_semidynamic.py <gmns_folder>   (folder needs link + link_performance_15min
       with a speed column + path_flow/route_assignment). Exit 1 on any mismatch.
"""
import csv, os, re, subprocess, sys

def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm(s):
    m = re.match(r"(\d+):(\d+)", s or ""); return int(m[1]) * 60 + int(m[2]) if m else 0

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    d = sys.argv[1]
    # link length (mi) — mirror the adapter's own meters->miles guard so lengths agree
    LEN = {}
    for r in csv.DictReader(open(os.path.join(d, "link.csv"), encoding="utf-8-sig")):
        length = fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 0)
        if length > 50: length /= 1609.34
        LEN[str(int(fnum(r["link_id"])))] = length
    # speed table: SPD[lid] = sorted [(bin_start_min, speed)]
    tf = os.path.join(d, "link_performance_15min.csv")
    rows = list(csv.DictReader(open(tf, encoding="utf-8-sig"))) if os.path.exists(tf) else []
    if not rows or "speed" not in rows[0]:
        print("  NA: no link_performance_15min.csv with a speed column -> can't check against distance/speed")
        sys.exit(0)
    SPD = {}
    for r in rows:
        lid = str(int(fnum(r["link_id"])))
        if fnum(r.get("speed")) > 0:
            SPD.setdefault(lid, []).append((hhmm(r["time_bin_start"]), fnum(r["speed"])))
    for lid in SPD: SPD[lid].sort()
    def speed_at(lid, t):
        s = SPD.get(lid)
        if not s: return None
        best = s[0][1]
        for bs, v in s:
            if bs <= t: best = v
            else: break
        return best

    # run the adapter into a temp trajectory file
    out = os.path.join(d, "_verify_synth_traj.csv")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, os.path.join(root, "adapters", "semidynamic_trajectories.py"),
                        d, "-o", out], capture_output=True, text=True)
    print("  adapter:", (r.stdout.strip().splitlines() or ["(no output)"])[-1])
    if not os.path.exists(out):
        print("  FAIL: adapter produced no trajectory"); sys.exit(1)

    from collections import defaultdict
    ev = defaultdict(list)
    for row in csv.DictReader(open(out, encoding="utf-8-sig")):
        ev[row["agent_id"]].append((float(row["time_min"]), str(int(fnum(row["link_id"]))), row["buffer"]))
    checked = bad = 0; worst = 0.0; ex = ""
    for a, es in ev.items():
        es.sort(); i = 0
        while i + 1 < len(es):
            (t0, l0, b0), (t1, l1, b1) = es[i], es[i + 1]
            if b0 == "ENB" and b1 == "EXB" and l0 == l1 and l0 in LEN:
                sp = speed_at(l0, t0)
                if sp:
                    expect = LEN[l0] / sp * 60
                    checked += 1
                    diff = abs((t1 - t0) - expect)
                    if diff > 0.02:
                        bad += 1; worst = max(worst, diff)
                        if not ex: ex = f"agent {a} link {l0}: traversal {t1-t0:.3f} vs dist/speed {expect:.3f}"
                i += 2
            else: i += 1
    os.remove(out)
    ok = bad == 0 and checked > 0
    print(f"  {'PASS' if ok else 'FAIL'}: {checked-bad}/{checked} traversals == distance/speed"
          + (f"  ({bad} mismatch, worst {worst:.3f} min; {ex})" if bad else ""))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

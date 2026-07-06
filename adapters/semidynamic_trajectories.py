#!/usr/bin/env python3
"""Semi-dynamic trajectory synthesis — Eulerian (link) time-dependent performance -> Lagrangian (vehicle).

You often have paths + time-dependent LINK performance (speed or flow/queue per 15-min bin) but NO agent
trajectories (no micro-sim was run). This propagates vehicles along their paths using the time-dependent
link travel time at the moment each vehicle enters each link, producing an animatable agent_trajectory.csv
— vehicles that speed up / slow down / queue exactly as the semi-dynamic link results say.

Travel-time source per link/bin (first available wins):
  1. travel_time column      2. speed column (tt = length/speed)
  3. inflow/queue -> BPR(0.15,4) on 15-min v/c + point-queue delay      4. free-flow fallback

Usage: python semidynamic_trajectories.py <gmns_folder> [-o agent_trajectory.csv] [--n 2000] [--seed-jitter]
Reads link.csv, link_performance_15min.csv, path_flow.csv (or route_assignment.csv). Pure-Python.
"""
import csv, math, os, sys
csv.field_size_limit(1 << 24)

def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm2min(s):
    import re
    m = re.match(r"(\d+):(\d+)", s or ""); return int(m[1]) * 60 + int(m[2]) if m else 0

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    d = a[0]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(d, "agent_trajectory.csv")
    N = int(a[a.index("--n") + 1]) if "--n" in a else 2000

    # ---- links: fftt (min), capacity per min ----
    L = {}
    for r in csv.DictReader(open(os.path.join(d, "link.csv"), encoding="utf-8-sig")):
        lid = str(int(fnum(r["link_id"])))
        length = fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 0)
        # length may be meters in some GMNS; if huge relative to a link, treat >50 as meters->miles
        if length > 50: length /= 1609.34
        fs = fnum(r.get("free_speed") or 30) or 30
        cap = fnum(r.get("capacity") or 1800); lanes = max(1, fnum(r.get("lanes") or 1))
        L[lid] = {"len": length, "fftt": (length / fs * 60) if fs else 1.0,
                  "cap_min": cap * lanes / 60.0}

    # ---- time-dependent travel time table: TT[lid] = list of (bin_start_min, tt_min) ----
    TT = {}; bins = set()
    tf = os.path.join(d, "link_performance_15min.csv")
    src = "free-flow only"
    if os.path.exists(tf):
        rows = list(csv.DictReader(open(tf, encoding="utf-8-sig")))
        cols = rows[0].keys() if rows else []
        has_tt = "travel_time" in cols; has_spd = "speed" in cols
        has_flow = "inflow_veh" in cols or "volume" in cols
        src = ("travel_time" if has_tt else "speed" if has_spd else
               "inflow/queue->BPR" if has_flow else "free-flow")
        for r in rows:
            lid = str(int(fnum(r["link_id"]))); ln = L.get(lid)
            if not ln: continue
            b = hhmm2min(r["time_bin_start"]); bins.add(b); tt = ln["fftt"]
            if has_tt and fnum(r.get("travel_time")) > 0:
                tt = fnum(r["travel_time"])
            elif has_spd and fnum(r.get("speed")) > 0:
                tt = ln["len"] / fnum(r["speed"]) * 60
            elif has_flow:
                inflow = fnum(r.get("inflow_veh") or r.get("volume"))
                vc = (inflow * 4) / max(ln["cap_min"] * 60, 1)          # 15-min inflow -> hourly v/c
                tt = ln["fftt"] * (1 + 0.15 * vc ** 4)                    # BPR(0.15,4)
                q = fnum(r.get("queue_exb") or 0)
                if q > 0 and ln["cap_min"] > 0: tt += q / ln["cap_min"]  # point-queue delay (min)
            TT.setdefault(lid, []).append((b, tt))
    for lid in TT: TT[lid].sort()
    def tt_at(lid, t):
        ln = L.get(lid); series = TT.get(lid)
        if not ln: return 1.0
        if not series: return ln["fftt"]
        # pick the bin covering t (last bin with start <= t)
        best = series[0][1]
        for bs, v in series:
            if bs <= t: best = v
            else: break
        return max(0.05, best)

    # ---- paths (volume, [link_ids]) ----
    paths = []
    pf = os.path.join(d, "path_flow.csv")
    if os.path.exists(pf):
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")):
            ids = [x for x in (r.get("link_ids") or "").split(";") if x.strip() and x in L]
            vol = fnum(r.get("base_volume") or r.get("volume") or 1) * fnum(r.get("route_share") or 1)
            if len(ids) >= 1 and vol > 0: paths.append((vol, ids))
    else:
        ra = os.path.join(d, "route_assignment.csv")
        if os.path.exists(ra):
            for r in csv.DictReader(open(ra, encoding="utf-8-sig")):
                seq = r.get("link_sequence") or r.get("link_ids") or ""
                ids = [x for x in seq.replace(";", " ").split() if x in L]
                vol = fnum(r.get("volume") or r.get("agent_count") or 1)
                if len(ids) >= 1 and vol > 0: paths.append((vol, ids))
    if not paths: sys.exit("no paths found (need path_flow.csv or route_assignment.csv with link_ids)")

    # ---- departure window: --window HH:MM-HH:MM overrides the TD-bin span ----
    if "--window" in a:
        w = a[a.index("--window") + 1]; s, e = w.split("-")
        t0, t1 = hhmm2min(s), hhmm2min(e)
    else:
        t0 = min(bins) if bins else 420
        t1 = (max(bins) + 15) if bins else 540
    profile = a[a.index("--profile") + 1] if "--profile" in a else "peak"   # peak | uniform
    total_vol = sum(v for v, _ in paths)
    # peaked departures: inverse-CDF of a symmetric triangular over [0,1] concentrates the sample
    def shape(f):
        if profile != "peak": return f
        return math.sqrt(f * 0.5) if f <= 0.5 else 1 - math.sqrt((1 - f) * 0.5)
    print(f"paths={len(paths)} total_vol={total_vol:.0f} | TT source: {src} | depart window "
          f"{t0//60:02d}:{t0%60:02d}-{t1//60:02d}:{t1%60:02d} ({profile}) | synth {N} vehicles")

    # ---- allocate N vehicles across paths ∝ volume; spread departures (deterministic, no RNG) ----
    rows_out = []; aid = 0
    for vol, ids in paths:
        k = max(1, round(N * vol / total_vol))
        for j in range(k):
            if aid >= N: break
            frac = shape((j + 0.5) / k)
            dep = t0 + frac * (t1 - t0) + ((aid * 7) % 11 - 5) * 0.3   # small deterministic jitter
            t = dep
            for lid in ids:
                tt = tt_at(lid, t)
                rows_out.append((aid, lid, round(t, 2), "ENB"))
                rows_out.append((aid, lid, round(t + tt, 2), "EXB"))
                t += tt
            aid += 1
        if aid >= N: break

    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["agent_id", "link_id", "time_min", "buffer", "traffic_state"])
        for a2, lid, tm, buf in rows_out:
            w.writerow([a2, lid, tm, buf, "moving" if buf == "ENB" else "completed"])
    print(f"wrote {out}: {aid} vehicles, {len(rows_out)} events (semi-dynamic synthesis)")

if __name__ == "__main__":
    main()

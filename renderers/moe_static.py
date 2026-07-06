#!/usr/bin/env python3
"""Static MOE PNG renderer — publication-quality images for offline docs (no screen-copying).

Reproduces the classic NeXTA MOE gallery as saved PNGs with proper labels/legends:
  bandwidth   traffic-speed bandwidth map: width = volume, color = speed / free-flow
  spacetime   corridor space-time SPEED contour + space-time DENSITY contour (the gnuplot view),
              over a corridor = an ordered link sequence (auto: busiest path in path_flow.csv)

Time-dependent inputs come from link_performance_15min.csv (speed, or inflow->BPR-derived speed);
density k = flow/speed. Uses matplotlib (Agg, no display).

Usage: python moe_static.py <gmns_folder> [-o out_dir] [--moe bandwidth|spacetime|all] [--links "1;2;3"]
"""
import csv, math, os, re, sys
csv.field_size_limit(1 << 24)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm2min(s):
    m = re.match(r"(\d+):(\d+)", s or ""); return int(m[1]) * 60 + int(m[2]) if m else 0

def read(d):
    L = {}
    for r in csv.DictReader(open(os.path.join(d, "link.csv"), encoding="utf-8-sig")):
        lid = str(int(fnum(r["link_id"]))); pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
        poly = [(float(x), float(y)) for x, y in pts] if len(pts) >= 2 else None
        length = fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 0)
        if length > 50: length /= 1609.34
        fs = fnum(r.get("free_speed") or 30) or 30
        cap = fnum(r.get("capacity") or 1800); lanes = max(1, fnum(r.get("lanes") or 1))
        L[lid] = {"poly": poly, "len": length, "fs": fs, "cap": cap, "lanes": lanes,
                  "fftt": length / fs * 60 if fs else 1, "vol": 0.0, "spd": fs}
    pf = os.path.join(d, "link_performance.csv")
    if os.path.exists(pf):
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")):
            lid = str(int(fnum(r["link_id"]))); x = L.get(lid)
            if not x: continue
            x["vol"] = fnum(r.get("volume") or r.get("cum_departure"))
            if r.get("speed"): x["spd"] = fnum(r["speed"])
    # TD table
    TD = {}; bins = []
    tf = os.path.join(d, "link_performance_15min.csv")
    if os.path.exists(tf):
        rows = list(csv.DictReader(open(tf, encoding="utf-8-sig")))
        bset = sorted({hhmm2min(r["time_bin_start"]) for r in rows})
        bins = bset; bidx = {b: i for i, b in enumerate(bset)}
        has_spd = rows and "speed" in rows[0]
        for r in rows:
            lid = str(int(fnum(r["link_id"]))); x = L.get(lid)
            if not x: continue
            b = bidx[hhmm2min(r["time_bin_start"])]
            inflow = fnum(r.get("inflow_veh") or r.get("volume"))
            if has_spd and fnum(r.get("speed")) > 0:
                spd = fnum(r["speed"])
            else:  # derive speed from BPR travel time
                vc = inflow * 4 / max(x["cap"] * x["lanes"], 1)
                tt = x["fftt"] * (1 + 0.15 * vc ** 4)
                spd = x["len"] / (tt / 60) if tt > 0 else x["fs"]
            flow = inflow * 4 / max(x["lanes"], 1)          # per-lane hourly flow
            TD.setdefault(lid, {})[b] = (spd, flow)
    return L, TD, bins

def bandwidth_png(d, L, out):
    links = [x for x in L.values() if x["poly"]]
    if not links: print("bandwidth: no geometry"); return
    mv = max([x["vol"] for x in links] + [1])
    segs, ws, cs = [], [], []
    for x in links:
        p = x["poly"]; segs.append(p)
        ws.append(0.3 + 4 * x["vol"] / mv)
        r = max(0, min(1, x["spd"] / (x["fs"] or 60)))          # speed ratio
        cs.append((1 - r if r < 1 else 0, r, 0.15))             # red slow -> green fast
    fig, ax = plt.subplots(figsize=(11, 9), dpi=130)
    ax.add_collection(LineCollection(segs, linewidths=ws, colors=cs))
    ax.autoscale(); ax.set_aspect("equal"); ax.set_facecolor("#0e1116")
    ax.set_title("Traffic Speed — bandwidth = link volume/hr, color = speed / free-flow", color="#333")
    ax.set_xticks([]); ax.set_yticks([])
    import matplotlib.lines as ml
    leg = [ml.Line2D([], [], color=(0, 1, .15), lw=3, label="free-flow (100%)"),
           ml.Line2D([], [], color=(.5, .5, .15), lw=3, label="~50% of free-flow"),
           ml.Line2D([], [], color=(1, 0, .15), lw=3, label="congested (<33%)")]
    ax.legend(handles=leg, loc="upper left", fontsize=8, framealpha=.9)
    p = os.path.join(out, "moe_traffic_speed_bandwidth.png"); fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    print("  ", p)

def corridor_from_paths(d, L):
    pf = os.path.join(d, "path_flow.csv")
    best = None
    if os.path.exists(pf):
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")):
            ids = [x for x in (r.get("link_ids") or "").split(";") if x in L]
            v = fnum(r.get("base_volume") or 1) * fnum(r.get("route_share") or 1)
            if len(ids) >= 6 and (not best or v > best[0]): best = (v, ids)
    return best[1] if best else None

def spacetime_png(d, L, TD, bins, out, links=None):
    if not bins: print("spacetime: no time-dependent data"); return
    seq = links or corridor_from_paths(d, L)
    if not seq: print("spacetime: no corridor (need path_flow or --links)"); return
    seq = [s for s in seq if s in TD]                   # keep links with TD data
    if len(seq) < 3: print("spacetime: corridor too short after TD filter"); return
    # cumulative distance
    dist = [0.0]
    for s in seq[:-1]: dist.append(dist[-1] + L[s]["len"])
    tot = dist[-1] + L[seq[-1]]["len"]
    nb = len(bins)
    SP = np.full((len(seq), nb), np.nan); KD = np.full((len(seq), nb), np.nan)
    for i, s in enumerate(seq):
        for b, (spd, flow) in TD[s].items():
            SP[i, b] = spd; KD[i, b] = flow / spd if spd > 0 else np.nan
    t = [b / 60 for b in bins]
    for arr, ttl, cmap, unit, fname in [
        (SP, "Space-time SPEED contour", "RdYlGn", "mph", "moe_spacetime_speed.png"),
        (KD, "Space-time DENSITY contour", "RdYlGn_r", "veh/mi/lane", "moe_spacetime_density.png")]:
        fig, ax = plt.subplots(figsize=(9, 6), dpi=130)
        m = ax.pcolormesh(t, dist, arr, cmap=cmap, shading="nearest",
                          vmin=0, vmax=(70 if unit == "mph" else np.nanpercentile(arr, 95) or 1))
        ax.set_xlabel("time of day (h)"); ax.set_ylabel("distance along corridor (mi)")
        ax.set_title(f"{ttl}  —  {len(seq)} links, {tot:.1f} mi")
        fig.colorbar(m, ax=ax, label=unit)
        p = os.path.join(out, fname); fig.savefig(p, bbox_inches="tight"); plt.close(fig)
        print("  ", p)

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    src = a[0]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(src, "moe_png")
    moe = a[a.index("--moe") + 1] if "--moe" in a else "all"
    links = a[a.index("--links") + 1].split(";") if "--links" in a else None
    os.makedirs(out, exist_ok=True)
    L, TD, bins = read(src)
    print(f"read {len(L)} links, {len(TD)} with TD, {len(bins)} bins -> {out}/")
    if moe in ("bandwidth", "all"): bandwidth_png(src, L, out)
    if moe in ("spacetime", "all"): spacetime_png(src, L, TD, bins, out, links)

if __name__ == "__main__":
    main()

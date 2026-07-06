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

# DEFAULT = intuitive traffic ramp: speed fast=GREEN, slow=RED (what practitioners read instantly).
# Colorblind-safe (cividis / blue-red) is an opt-in via --cmap cb, not the default.
STYLE = {"cb": False}
def speed_color(ratio):        # ratio = speed/free-flow, 0..1
    r = max(0.0, min(1.0, ratio))
    if STYLE["cb"]:            # colorblind opt-in: RdYlBu (fast=blue, slow=red)
        c = plt.cm.RdYlBu(r); return (c[0], c[1], c[2])
    c = plt.cm.RdYlGn(r); return (c[0], c[1], c[2])   # DEFAULT green(fast)->yellow->red(slow)
def cmap_speed(): return "cividis" if STYLE["cb"] else "RdYlGn"     # speed: low=red, high=green
def cmap_density(): return "cividis_r" if STYLE["cb"] else "RdYlGn_r"  # density: low=green, high=red

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
                  "fftt": length / fs * 60 if fs else 1, "vol": 0.0, "spd": fs,
                  "name": (r.get("name") or "").strip(),
                  "fn": int(fnum(r["from_node_id"])), "tn": int(fnum(r["to_node_id"]))}
    pf = os.path.join(d, "link_performance.csv")
    if os.path.exists(pf):
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")):
            lid = str(int(fnum(r["link_id"]))); x = L.get(lid)
            if not x: continue
            # standard GMNS, or DTALite schema (vehicle_volume / speed_mph / travel_time)
            x["vol"] = fnum(r.get("volume") or r.get("cum_departure") or r.get("vehicle_volume"))
            sp = fnum(r.get("speed") or r.get("speed_mph") or 0)
            if sp <= 0:
                tt = fnum(r.get("travel_time") or r.get("avg_travel_time_in_min") or 0)
                if tt > 0 and x["len"] > 0: sp = x["len"] / (tt / 60)
            if sp > 0: x["spd"] = sp
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
        cs.append(speed_color(x["spd"] / (x["fs"] or 60)))       # colorblind-safe speed color
    fig, ax = plt.subplots(figsize=(11, 9), dpi=130)
    ax.add_collection(LineCollection(segs, linewidths=ws, colors=cs))
    ax.autoscale(); ax.set_aspect("equal"); ax.set_facecolor("#0e1116")
    ax.set_title("Traffic Speed — bandwidth = link volume/hr, color = speed / free-flow", color="#333")
    ax.set_xticks([]); ax.set_yticks([])
    import matplotlib.lines as ml
    leg = [ml.Line2D([], [], color=speed_color(1.0), lw=3, label="free-flow (100%)"),
           ml.Line2D([], [], color=speed_color(0.5), lw=3, label="~50% of free-flow"),
           ml.Line2D([], [], color=speed_color(0.2), lw=3, label="congested (<33%)")]
    ax.legend(handles=leg, loc="upper left", fontsize=8, framealpha=.9)
    p = os.path.join(out, "moe_traffic_speed_bandwidth.png"); fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    print("  ", p)

def corridor_by_name(L, name):
    """links whose name contains all tokens (e.g. 'I-10 WB'), chained into the longest connected
    sequence by node connectivity (from_node -> to_node) — a real corridor, not a spatial jumble."""
    toks = name.lower().split()
    sel = {lid: x for lid, x in L.items() if x["poly"] and all(t in x["name"].lower() for t in toks)}
    if len(sel) < 3: return None
    out_of = {}                                   # node -> link starting there
    for lid, x in sel.items(): out_of.setdefault(x["fn"], []).append(lid)
    starts = [x["fn"] for x in sel.values()]
    incoming = {x["tn"] for x in sel.values()}
    # greedy longest chain from each source node (a from_node that is nobody's to_node)
    best = []
    for lid0, x0 in sel.items():
        if x0["fn"] in incoming: continue         # not a source; skip (walk starts at sources)
        chain, node, seen = [lid0], x0["tn"], {lid0}
        while node in out_of:
            nxt = next((l for l in out_of[node] if l not in seen), None)
            if not nxt: break
            chain.append(nxt); seen.add(nxt); node = sel[nxt]["tn"]
        if len(chain) > len(best): best = chain
    if len(best) < 3:                             # no clean source -> fall back to a spatial sort
        mids = [((x["poly"][0][0] + x["poly"][-1][0]) / 2, (x["poly"][0][1] + x["poly"][-1][1]) / 2) for x in sel.values()]
        ids = list(sel); xs = [m[0] for m in mids]; ys = [m[1] for m in mids]
        axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        best = [ids[i] for i in sorted(range(len(ids)), key=lambda i: mids[i][axis])]
    return best

def corridor_profile_png(L, seq, out, tag):
    """static speed & volume vs distance along a corridor (the space profile; space-TIME needs TD)."""
    dist = [0.0]
    for s in seq[:-1]: dist.append(dist[-1] + L[s]["len"])
    spd = [L[s]["spd"] for s in seq]; vol = [L[s]["vol"] for s in seq]
    fig, ax1 = plt.subplots(figsize=(11, 4.5), dpi=130)
    ax1.plot(dist, spd, "-", color="#c62828", lw=1.5, label="speed")
    ax1.fill_between(dist, spd, color="#c62828", alpha=0.08)
    ax1.set_xlabel("distance along corridor (mi)"); ax1.set_ylabel("speed (mph)", color="#c62828")
    ax1.set_ylim(0, max(spd + [1]) * 1.15)
    ax2 = ax1.twinx(); ax2.plot(dist, vol, "-", color="#1565c0", lw=1, alpha=0.7, label="volume")
    ax2.set_ylabel("volume (veh)", color="#1565c0")
    ax1.set_title(f"Corridor profile — {tag}: {len(seq)} links, {dist[-1]+L[seq[-1]]['len']:.1f} mi (static)")
    p = os.path.join(out, f"moe_corridor_profile_{re.sub(r'[^A-Za-z0-9]+','_',tag)}.png")
    fig.tight_layout(); fig.savefig(p); plt.close(fig); print("  ", p)

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
        (SP, "Space-time SPEED contour", cmap_speed(), "mph", "moe_spacetime_speed.png"),
        (KD, "Space-time DENSITY contour", cmap_density(), "veh/mi/lane", "moe_spacetime_density.png")]:
        fig, ax = plt.subplots(figsize=(9, 6), dpi=130)
        m = ax.pcolormesh(t, dist, arr, cmap=cmap, shading="nearest",
                          vmin=0, vmax=(70 if unit == "mph" else np.nanpercentile(arr, 95) or 1))
        ax.set_xlabel("time of day (h)"); ax.set_ylabel("distance along corridor (mi)")
        ax.set_title(f"{ttl}  —  {len(seq)} links, {tot:.1f} mi")
        fig.colorbar(m, ax=ax, label=unit)
        p = os.path.join(out, fname); fig.savefig(p, bbox_inches="tight"); plt.close(fig)
        print("  ", p)

def spacetime_from_csv(path, out):
    """space-time SPEED contour straight from a corridor_speed.csv (per (seq,time) speed)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows: print("corridor_speed.csv empty"); return
    name = (rows[0].get("corridor") or "corridor")
    spcol = "speed_qvdf" if "speed_qvdf" in rows[0] else ("speed" if "speed" in rows[0] else "speed_inrix")
    seqs = sorted({int(fnum(r["seq"])) for r in rows})
    times = sorted({r["time"] for r in rows}, key=hhmm2min)
    dist = {int(fnum(r["seq"])): fnum(r.get("cum_dist_mi") or 0) for r in rows}
    cell = {(int(fnum(r["seq"])), r["time"]): fnum(r[spcol]) for r in rows}
    arr = np.full((len(seqs), len(times)), np.nan)
    for i, s in enumerate(seqs):
        for j, t in enumerate(times):
            v = cell.get((s, t))
            if v and v > 0: arr[i, j] = v
    y = [dist[s] for s in seqs]; x = [hhmm2min(t) / 60 for t in times]
    fig, ax = plt.subplots(figsize=(9, 6), dpi=130)
    m = ax.pcolormesh(x, y, arr, cmap=cmap_speed(), shading="nearest", vmin=0, vmax=max(70, np.nanmax(arr)))
    ax.set_xlabel("time of day (h)"); ax.set_ylabel("distance along corridor (mi)")
    ax.set_title(f"Space-time SPEED contour — {name} ({spcol})")
    fig.colorbar(m, ax=ax, label="mph")
    p = os.path.join(out, f"moe_spacetime_speed_{re.sub(r'[^A-Za-z0-9]+','_',name)}.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig); print("  ", p)

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    src = a[0]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(src, "moe_png")
    moe = a[a.index("--moe") + 1] if "--moe" in a else "all"
    links = a[a.index("--links") + 1].split(";") if "--links" in a else None
    cname = a[a.index("--corridor-name") + 1] if "--corridor-name" in a else None
    STYLE["cb"] = ("--cmap" in a and a[a.index("--cmap") + 1] == "cb")   # default green->red; --cmap cb opts in
    os.makedirs(out, exist_ok=True)
    # ready-made corridor space-time from corridor_speed.csv (seq, cum_dist_mi, time, speed[_qvdf/_inrix])
    cs_csv = os.path.join(src, "corridor_speed.csv")
    if os.path.exists(cs_csv) and moe in ("spacetime", "all", "corridor"):
        spacetime_from_csv(cs_csv, out)
        if moe != "all": return
    L, TD, bins = read(src)
    print(f"read {len(L)} links, {len(TD)} with TD, {len(bins)} bins -> {out}/ (cmap={'colorblind' if STYLE['cb'] else 'classic'})")
    if moe in ("bandwidth", "all"): bandwidth_png(src, L, out)
    if cname:
        seq = corridor_by_name(L, cname)
        if not seq: print(f"corridor '{cname}': <3 matching links")
        elif bins and any(s in TD for s in seq): spacetime_png(src, L, TD, bins, out, seq)
        else: corridor_profile_png(L, seq, out, cname)   # static profile when no TD
    elif moe in ("spacetime", "all"): spacetime_png(src, L, TD, bins, out, links)

if __name__ == "__main__":
    main()

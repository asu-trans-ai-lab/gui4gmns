#!/usr/bin/env python3
"""gmns_figures — native reimplementation of the plot4gmns figure catalog, integrated into gui4gmns.

Same figures plot4gmns produces (network nodes/links/zones/POI, by-attribute, distributions, demand
matrix + OD desire lines) but rewritten to fit this codebase: pure matplotlib + the same lightweight
WKT reader the rest of gui4gmns uses — no pandas / Shapely / keplergl, no hardcoded save paths, the
demand-OD bug fixed, and one automatable `export_all()`. Keeps plot4gmns's visual language (violet
links, orange/blue zones, yellow POI, blue demand, 'jet' OD heatmap).

Usage: python gmns_figures.py <gmns_folder> [-o out_dir] [--only nodes,links,demand,...]
"""
import csv, os, re, sys
csv.field_size_limit(1 << 24)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
import numpy as np

def fnum(v):
    try: return float(v)
    except: return 0.0
def wkt_pts(g):
    return [(float(x), float(y)) for x, y in re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", g or "")]

# ---- read (no pandas): only what the figures need ----
def read(d):
    rd = lambda f: (list(csv.DictReader(open(os.path.join(d, f), encoding="utf-8-sig")))
                    if os.path.exists(os.path.join(d, f)) else [])
    nodes = {}
    for r in rd("node.csv"):
        nodes[str(int(fnum(r["node_id"])))] = (fnum(r["x_coord"]), fnum(r["y_coord"]),
                                                (r.get("ctrl_type") or r.get("control_type") or "").strip(),
                                                (r.get("zone_id") or "").strip())
    links = []
    for r in rd("link.csv"):
        pts = wkt_pts(r.get("geometry"))
        if len(pts) < 2:
            a = nodes.get(str(int(fnum(r.get("from_node_id") or 0)))); b = nodes.get(str(int(fnum(r.get("to_node_id") or 0))))
            if a and b: pts = [(a[0], a[1]), (b[0], b[1])]
        if len(pts) < 2: continue
        links.append({"pts": pts, "type": (r.get("link_type_name") or r.get("link_type") or r.get("facility_type") or "").strip(),
                      "fs": fnum(r.get("free_speed") or r.get("free_speed_mph") or 0),
                      "lanes": fnum(r.get("lanes") or 0), "cap": fnum(r.get("capacity") or 0),
                      "len": fnum(r.get("length") or r.get("vdf_length_mi") or 0),
                      "uses": (r.get("allowed_uses") or "").strip()})
    zones, zpts = [], {}
    for r in rd("zone.csv"):
        g = r.get("geometry") or ""; poly = wkt_pts(g)
        zid = (r.get("zone_id") or r.get("activity_zone_id") or r.get("name") or "").strip()
        cx, cy = fnum(r.get("centroid_x") or 0), fnum(r.get("centroid_y") or 0)
        zones.append({"poly": poly if "POLYGON" in g else None, "id": zid, "cx": cx, "cy": cy})
    for n in nodes.values():
        if n[3]: zpts.setdefault(n[3], []).append((n[0], n[1]))
    pois = []
    for r in rd("poi.csv"):
        pts = wkt_pts(r.get("geometry"))
        if pts: pois.append({"pts": pts, "type": (r.get("building") or r.get("poi_type") or r.get("amenity") or "").strip()})
    demand = []
    for r in rd("demand.csv"):
        o = (r.get("o_zone_id") or "").strip(); dd = (r.get("d_zone_id") or "").strip(); v = fnum(r.get("volume"))
        if o and dd: demand.append((o, dd, v))
    return {"nodes": nodes, "links": links, "zones": zones, "zpts": zpts, "pois": pois, "demand": demand}

def _fig():
    f, ax = plt.subplots(figsize=(10, 8), dpi=120, facecolor="white")
    ax.set_aspect("equal"); ax.set_facecolor("white"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_edgecolor("#ccc")
    return f, ax
def _save(f, out, name):
    p = os.path.join(out, f"gmns_{name}.png"); f.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(f)
    print("  ", p); return p

# ---- figures (plot4gmns visual language) ----
def fig_links(N, out):
    f, ax = _fig()
    ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="violet", linewidths=0.8))
    ax.autoscale(); ax.set_title(f"Network links ({len(N['links']):,})"); _save(f, out, "links")

def fig_nodes(N, out):
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#ddd", linewidths=0.4))
    xs = [v[0] for v in N["nodes"].values()]; ys = [v[1] for v in N["nodes"].values()]
    ax.scatter(xs, ys, s=6, c="#1f77b4", edgecolors="none")
    ax.autoscale(); ax.set_title(f"Network nodes ({len(N['nodes']):,})"); _save(f, out, "nodes")

def fig_zones(N, out):
    if not N["zones"] and not N["zpts"]: return
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e0e0e0", linewidths=0.4))
    polys = [z["poly"] for z in N["zones"] if z["poly"]]
    if polys:
        ax.add_collection(PolyCollection(polys, facecolors="orange", edgecolors="blue", alpha=0.25, linewidths=1))
    else:  # centroids
        for zid, pts in N["zpts"].items():
            cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
            ax.plot(cx, cy, "s", color="orange", markeredgecolor="blue", ms=6)
    ax.autoscale(); ax.set_title(f"Network zones ({len(N['zones']) or len(N['zpts'])})"); _save(f, out, "zones")

def fig_poi(N, out):
    if not N["pois"]: return
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e0e0e0", linewidths=0.4))
    ax.add_collection(PolyCollection([p["pts"] for p in N["pois"] if len(p["pts"]) >= 3],
                                     facecolors="y", edgecolors="black", linewidths=0.4, alpha=0.6))
    ax.autoscale(); ax.set_title(f"Points of interest ({len(N['pois']):,})"); _save(f, out, "poi")

def fig_by_categorical(N, out, key, name, title):
    vals = sorted({L[key] for L in N["links"] if L[key]})
    if len(vals) < 2: return
    cmap = plt.cm.tab10; cix = {v: cmap(i % 10) for i, v in enumerate(vals)}
    f, ax = _fig()
    ax.add_collection(LineCollection([L["pts"] for L in N["links"]],
                                     colors=[cix.get(L[key], "#ccc") for L in N["links"]], linewidths=0.9))
    import matplotlib.lines as ml
    ax.legend(handles=[ml.Line2D([], [], color=cix[v], lw=2, label=str(v)[:18]) for v in vals[:12]],
              fontsize=7, loc="upper right")
    ax.autoscale(); ax.set_title(title); _save(f, out, name)

def fig_by_range(N, out, key, name, title, lo, hi):
    sel = [L for L in N["links"] if lo <= L[key] <= hi]
    if not sel: return
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e5e5e5", linewidths=0.4))
    ax.add_collection(LineCollection([L["pts"] for L in sel], colors="crimson", linewidths=1.1))
    ax.autoscale(); ax.set_title(f"{title}  [{lo}-{hi}] — {len(sel):,} links"); _save(f, out, name)

def fig_distribution(N, out, key, name, unit):
    vals = [L[key] for L in N["links"] if L[key] > 0]
    if not vals: return
    f, ax = plt.subplots(figsize=(8, 5), dpi=120, facecolor="white")
    ax.hist(vals, bins=20, color="#4c78a8", edgecolor="white")
    ax.set_xlabel(unit); ax.set_ylabel("link count"); ax.set_title(f"{name.replace('_',' ').title()} distribution")
    p = os.path.join(out, f"gmns_dist_{name}.png"); f.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(f); print("  ", p)

def fig_demand_heatmap(N, out):
    if not N["demand"]: return
    zids = sorted({o for o, d, v in N["demand"]} | {d for o, d, v in N["demand"]},
                  key=lambda z: int(z) if z.isdigit() else z)
    zi = {z: i for i, z in enumerate(zids)}; n = len(zids)
    if n > 200: zids = zids[:200]; zi = {z: i for i, z in enumerate(zids)}; n = 200
    M = np.zeros((n, n))
    for o, d, v in N["demand"]:
        if o in zi and d in zi: M[zi[o], zi[d]] += v
    f, ax = plt.subplots(figsize=(9, 7.5), dpi=120, facecolor="white")
    im = ax.imshow(M, cmap="jet", aspect="auto")
    ax.set_xlabel("d_zone_id"); ax.set_ylabel("o_zone_id"); ax.set_title("Demand OD matrix heatmap")
    f.colorbar(im, ax=ax, label="volume")
    p = os.path.join(out, "gmns_demand_matrix_heatmap.png"); f.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(f); print("  ", p)

def fig_demand_OD(N, out):   # the plot4gmns figure that crashed on ZoneStyle.edgecolors — fixed here
    if not N["demand"] or not N["zpts"]: return
    zc = {z: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) for z, pts in N["zpts"].items()}
    agg = {}
    for o, d, v in N["demand"]:
        if v > 0 and o in zc and d in zc and o != d: agg[(o, d)] = agg.get((o, d), 0) + v
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:400]
    if not top: return
    mx = max(v for _, v in top)
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e8e8e8", linewidths=0.4))
    segs = [[zc[o], zc[d]] for (o, d), v in top]
    ws = [0.3 + 2.5 * v / mx for _, v in top]
    ax.add_collection(LineCollection(segs, colors="b", linewidths=ws, alpha=0.5))
    for z, (x, y) in zc.items(): ax.plot(x, y, "s", color="orange", markeredgecolor="blue", ms=4)
    ax.autoscale(); ax.set_title(f"Demand OD desire lines (top {len(top)})"); _save(f, out, "demand_OD")

def export_all(d, out, only=None):
    N = read(d); os.makedirs(out, exist_ok=True)
    print(f"read {len(N['nodes'])} nodes, {len(N['links'])} links, {len(N['zones']) or len(N['zpts'])} zones, "
          f"{len(N['pois'])} POI, {len(N['demand'])} OD -> {out}/")
    jobs = {
        "links": lambda: fig_links(N, out), "nodes": lambda: fig_nodes(N, out),
        "zones": lambda: fig_zones(N, out), "poi": lambda: fig_poi(N, out),
        "by_link_type": lambda: fig_by_categorical(N, out, "type", "by_link_type", "Network by link type"),
        "by_free_speed": lambda: fig_by_range(N, out, "fs", "by_free_speed", "Links by free-flow speed", 10, 40),
        "by_lanes": lambda: fig_by_range(N, out, "lanes", "by_lanes", "Links by lanes", 2, 4),
        "by_length": lambda: fig_by_range(N, out, "len", "by_length", "Links by length", 0.1, 2),
        "dist_capacity": lambda: fig_distribution(N, out, "cap", "capacity", "capacity (veh/h)"),
        "dist_free_speed": lambda: fig_distribution(N, out, "fs", "free_speed", "free-flow speed"),
        "dist_lanes": lambda: fig_distribution(N, out, "lanes", "lanes", "lanes"),
        "demand_heatmap": lambda: fig_demand_heatmap(N, out), "demand_OD": lambda: fig_demand_OD(N, out),
    }
    names = only or list(jobs); ok = 0
    for nm in names:
        try: jobs[nm](); ok += 1
        except Exception as e: print(f"  --  {nm}: {type(e).__name__}: {str(e)[:50]}")
    print(f"\n{ok} native gmns figures exported.")

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    d = a[0]; out = a[a.index("-o") + 1] if "-o" in a else os.path.join(d, "gmns_figures")
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    export_all(d, out, only)

if __name__ == "__main__":
    main()

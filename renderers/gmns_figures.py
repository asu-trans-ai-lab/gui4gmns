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
        lanes_n = fnum(r.get("lanes") or 0)
        cap_raw = fnum(r.get("capacity") or 0)
        links.append({"id": str(int(fnum(r["link_id"]))), "pts": pts,
                      "fn": str(int(fnum(r.get("from_node_id") or 0))), "tn": str(int(fnum(r.get("to_node_id") or 0))),
                      "type": (r.get("link_type_name") or r.get("link_type") or r.get("facility_type") or "").strip(),
                      "fs": fnum(r.get("free_speed") or r.get("free_speed_mph") or 0),
                      "lanes": lanes_n, "cap": cap_raw,
                      # vdf_length_mi is explicitly mile-labeled; prefer it over the bare "length" column,
                      # which in some GMNS exports (e.g. Chicago Sketch) is actually in meters — using it
                      # first silently mixed units into anything that assumes miles (gui4gmns.py's dashboard
                      # generator already prefers vdf_length_mi for the same reason).
                      "len": fnum(r.get("vdf_length_mi") or r.get("length") or 0),
                      # centroid connectors carry a per-lane capacity sentinel (same >=40000 threshold the
                      # main dashboard generator uses) -> not a real road; exclude from road-stat figures.
                      "is_conn": cap_raw * max(1, lanes_n) >= 40000,
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
    lanes = [{"link": str(int(fnum(r["link_id"]))), "num": int(fnum(r.get("lane_num") or 1)),
              "width": fnum(r.get("width") or 12)} for r in rd("lane.csv") if r.get("link_id")]
    moves = [{"node": str(int(fnum(r.get("node_id") or 0))), "ib": str(int(fnum(r.get("ib_link_id") or 0))),
              "ob": str(int(fnum(r.get("ob_link_id") or 0))), "type": (r.get("type") or "").strip()}
             for r in rd("movement.csv") if r.get("ib_link_id")]
    return {"nodes": nodes, "links": links, "zones": zones, "zpts": zpts, "pois": pois, "demand": demand,
            "lanes": lanes, "moves": moves, "lbyid": {L["id"]: L for L in links}}

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
    ax.autoscale(); ax.set_title(f"Network links ({len(N['links']):,})"); return _save(f, out, "links")

def fig_nodes(N, out):
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#ddd", linewidths=0.4))
    xs = [v[0] for v in N["nodes"].values()]; ys = [v[1] for v in N["nodes"].values()]
    ax.scatter(xs, ys, s=6, c="#1f77b4", edgecolors="none")
    ax.autoscale(); ax.set_title(f"Network nodes ({len(N['nodes']):,})"); return _save(f, out, "nodes")

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
    ax.autoscale(); ax.set_title(f"Network zones ({len(N['zones']) or len(N['zpts'])})"); return _save(f, out, "zones")

def fig_poi(N, out):
    if not N["pois"]: return
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e0e0e0", linewidths=0.4))
    ax.add_collection(PolyCollection([p["pts"] for p in N["pois"] if len(p["pts"]) >= 3],
                                     facecolors="y", edgecolors="black", linewidths=0.4, alpha=0.6))
    ax.autoscale(); ax.set_title(f"Points of interest ({len(N['pois']):,})"); return _save(f, out, "poi")

def fig_by_categorical(N, out, key, name, title):
    # centroid connectors aren't a real road "type" — excluding them keeps the legend to the actual
    # road classes the data defines (a connector-inflated legend was hiding the real category count).
    real = [L for L in N["links"] if not L["is_conn"]]
    vals = sorted({L[key] for L in real if L[key]})
    if len(vals) < 2:
        print(f"   -- {name}: skipped (fewer than 2 distinct '{key}' values among {len(real)} non-connector links)")
        return None
    cmap = plt.cm.tab10; cix = {v: cmap(i % 10) for i, v in enumerate(vals)}
    f, ax = _fig()
    ax.add_collection(LineCollection([L["pts"] for L in real],
                                     colors=[cix.get(L[key], "#ccc") for L in real], linewidths=0.9))
    import matplotlib.lines as ml
    ax.legend(handles=[ml.Line2D([], [], color=cix[v], lw=2, label=str(v)[:18]) for v in vals[:12]],
              fontsize=7, loc="upper right")
    ax.autoscale(); ax.set_title(f"{title} ({len(real):,} non-connector links)"); return _save(f, out, name)

def fig_by_range(N, out, key, name, title, lo=None, hi=None, pct=None):
    # centroid connectors carry synthetic sentinel values (see read()), never real road attributes.
    real = [L for L in N["links"] if not L["is_conn"]]
    if pct is not None:
        # unit-agnostic default: highlight the bottom `pct` of REAL links by this metric, computed from
        # this dataset's own data. A fixed absolute threshold (e.g. "10-40 mph") silently matched ~0% or
        # ~100% of links depending on the dataset's speed/length units and scale — never a meaningful
        # subset. A percentile band adapts automatically and sidesteps unit ambiguity entirely.
        vals = sorted(L[key] for L in real if L[key] > 0)
        if len(vals) < 5 or vals[0] == vals[-1]:
            print(f"   -- {name}: skipped (not enough variation in '{key}' across {len(vals)} non-connector links)")
            return None
        lo, hi = vals[0], vals[max(0, min(len(vals) - 1, int(pct * len(vals))))]
    sel = [L for L in real if lo <= L[key] <= hi]
    if not sel:
        print(f"   -- {name}: skipped (0 non-connector links with {key} in [{lo:.2g}-{hi:.2g}])")
        return None
    f, ax = _fig()
    if N["links"]: ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#e5e5e5", linewidths=0.4))
    ax.add_collection(LineCollection([L["pts"] for L in sel], colors="crimson", linewidths=1.1))
    ax.autoscale(); ax.set_title(f"{title}  [{lo:.2g}-{hi:.2g}] — {len(sel):,} links"); return _save(f, out, name)

def fig_distribution(N, out, key, name, unit):
    # exclude connector sentinel values (e.g. a synthetic 49,500 veh/h capacity or a fixed 96.5 mph
    # free-speed baked into every connector) — they aren't real road attributes and previously produced
    # an isolated, misleading spike/gap in what's meant to describe the real road network.
    vals = [L[key] for L in N["links"] if not L["is_conn"] and L[key] > 0]
    if not vals: return None
    import numpy as np
    f, ax = plt.subplots(figsize=(8, 5), dpi=120, facecolor="white")
    # robust display range: a few genuinely anomalous source values (e.g. a handful of Chicago links
    # with a nominal 200-500 mph free-flow speed — a data quality issue we don't alter) can stretch the
    # x-axis so far that the real distribution collapses into a sliver. Clip the VIEW to the 1st-99th
    # percentile and note how many links fall outside it, rather than dropping or editing any data.
    lo, hi = np.percentile(vals, 1), np.percentile(vals, 99)
    off_scale = sum(1 for v in vals if v < lo or v > hi)
    rng = (lo, hi) if hi > lo and off_scale else None
    ax.hist(vals, bins=20, range=rng, color="#4c78a8", edgecolor="white")
    ax.set_xlabel(unit); ax.set_ylabel("link count")
    title = f"{name.replace('_',' ').title()} distribution ({len(vals):,} non-connector links)"
    if rng: title += f"\n{off_scale} link(s) outside [{lo:.0f}, {hi:.0f}] not shown (view clipped, data unchanged)"
    ax.set_title(title)
    p = os.path.join(out, f"gmns_dist_{name}.png"); f.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(f)
    print("  ", p); return p

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
    p = os.path.join(out, "gmns_demand_matrix_heatmap.png"); f.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(f)
    print("  ", p); return p

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
    ax.autoscale(); ax.set_title(f"Demand OD desire lines (top {len(top)})"); return _save(f, out, "demand_OD")

def _lerp(p0, p1, t):
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)

def _perp(pts):   # unit perpendicular of a polyline's overall direction
    import math
    dx, dy = pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]
    n = math.hypot(dx, dy) or 1
    return (-dy / n, dx / n)

def fig_lanes(N, out):
    if not N["lanes"]: return
    xs = [p[0] for L in N["links"] for p in L["pts"]]; ys = [p[1] for L in N["links"] for p in L["pts"]]
    off = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5 * 0.004   # per-lane offset scale
    f, ax = _fig()
    ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#dddddd", linewidths=0.5))
    segs = []
    for ln in N["lanes"]:
        L = N["lbyid"].get(ln["link"])
        if not L: continue
        px, py = _perp(L["pts"]); k = (ln["num"] - 0.5) * off
        segs.append([(x + px * k, y + py * k) for x, y in L["pts"]])
    ax.add_collection(LineCollection(segs, colors="green", linewidths=1.4))   # LaneStyle green
    ax.autoscale(); ax.set_title(f"Network lanes ({len(N['lanes'])} lanes on {len({l['link'] for l in N['lanes']})} links)")
    return _save(f, out, "lanes")

def fig_movements(N, out):
    if not N["moves"]: return
    col = {"left": "#8B4513", "right": "#cd853f", "through": "#a0522d"}
    f, ax = _fig()
    ax.add_collection(LineCollection([L["pts"] for L in N["links"]], colors="#dddddd", linewidths=0.5))
    segs, cs, nx, ny = [], [], [], []
    for m in N["moves"]:
        ib = N["lbyid"].get(m["ib"]); ob = N["lbyid"].get(m["ob"])
        nd = N["nodes"].get(m["node"])
        if not ib or not ob or len(ib["pts"]) < 2 or len(ob["pts"]) < 2: continue
        # In GMNS, a link's endpoints ARE its from/to node coordinates -- so ib's last point and ob's
        # first point are both exactly the shared node, and so is `via`. Using them directly collapses
        # every turning path to a zero-length segment (drawn, but invisible). Set the approach/depart
        # points back 15% along each link instead, so the turn renders as a visible V through the node.
        node_pt = (nd[0], nd[1]) if nd else ib["pts"][-1]
        a = _lerp(ib["pts"][-1], ib["pts"][-2], 0.15)
        b = _lerp(ob["pts"][0], ob["pts"][1], 0.15)
        segs.append([a, node_pt]); segs.append([node_pt, b])
        c = col.get(m["type"], "brown"); cs += [c, c]
        nx.append(node_pt[0]); ny.append(node_pt[1])
    ax.add_collection(LineCollection(segs, colors=cs, linewidths=1.6))   # MovementStyle brown
    ax.scatter(nx, ny, s=14, c="k", zorder=3)
    import matplotlib.lines as ml
    ax.legend(handles=[ml.Line2D([], [], color=c, lw=2, label=t) for t, c in col.items()], fontsize=8, loc="upper right")
    ax.autoscale(); ax.set_title(f"Intersection movements ({len(N['moves'])} at {len({m['node'] for m in N['moves']})} nodes)")
    return _save(f, out, "movements")

def export_all(d, out, only=None):
    N = read(d); os.makedirs(out, exist_ok=True)
    print(f"read {len(N['nodes'])} nodes, {len(N['links'])} links, {len(N['zones']) or len(N['zpts'])} zones, "
          f"{len(N['pois'])} POI, {len(N['demand'])} OD -> {out}/")
    jobs = {
        "links": lambda: fig_links(N, out), "nodes": lambda: fig_nodes(N, out),
        "zones": lambda: fig_zones(N, out), "poi": lambda: fig_poi(N, out),
        "by_link_type": lambda: fig_by_categorical(N, out, "type", "by_link_type", "Network by link type"),
        # bottom-third-by-value bands, computed per dataset (see fig_by_range) — a fixed absolute
        # threshold (e.g. "10-40 mph") matched ~0% of links on some datasets and ~100% on others,
        # depending on that dataset's speed/length scale and units; a percentile band adapts automatically.
        "by_free_speed": lambda: fig_by_range(N, out, "fs", "by_free_speed", "Links by free-flow speed (slowest third)", pct=1/3),
        # lane count is a meaningful physical category regardless of dataset -> keep an absolute range.
        "by_lanes": lambda: fig_by_range(N, out, "lanes", "by_lanes", "Links by lanes", lo=2, hi=4),
        "by_length": lambda: fig_by_range(N, out, "len", "by_length", "Links by length (shortest third)", pct=1/3),
        "dist_capacity": lambda: fig_distribution(N, out, "cap", "capacity", "capacity (veh/h)"),
        "dist_free_speed": lambda: fig_distribution(N, out, "fs", "free_speed", "free-flow speed (mph)"),
        "dist_lanes": lambda: fig_distribution(N, out, "lanes", "lanes", "lanes"),
        "demand_heatmap": lambda: fig_demand_heatmap(N, out), "demand_OD": lambda: fig_demand_OD(N, out),
        "lanes": lambda: fig_lanes(N, out), "movements": lambda: fig_movements(N, out),
    }
    names = only or list(jobs); made, skipped = [], []
    for nm in names:
        try:
            p = jobs[nm]()
            (made if p else skipped).append(nm)
        except Exception as e:
            skipped.append(nm); print(f"  --  {nm}: {type(e).__name__}: {str(e)[:50]}")
    print(f"\n{len(made)} figure(s) written: {', '.join(made) or '(none)'}")
    if skipped: print(f"{len(skipped)} skipped (no applicable data for this dataset): {', '.join(skipped)}")

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    d = a[0]; out = a[a.index("-o") + 1] if "-o" in a else os.path.join(d, "gmns_figures")
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    export_all(d, out, only)

if __name__ == "__main__":
    main()

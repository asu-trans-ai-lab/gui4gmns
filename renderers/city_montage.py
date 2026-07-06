#!/usr/bin/env python3
"""Global data-store coverage montage — render many GMNS city networks as one figure.

Scans a multi-city GMNS store (e.g. GMNS_Plus_Dataset_City0907: TransportationNetworks benchmark
cities) and draws each network as a grid thumbnail: line width ~ capacity, color ~ free-flow speed
(network hierarchy — freeways stand out). Shows gui4gmns reading the whole global store at once.

Usage: python city_montage.py <store_dir> [-o montage.png] [--cols 4] [--max 16] [--max-links 60000]
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

def find_cities(store):
    cities = []
    for root, dirs, files in os.walk(store):
        if "link.csv" in files and root != store:
            cities.append(root)
            dirs[:] = [d for d in dirs if d.upper() != "TNTP"]   # don't double-count TNTP subcopies
    # de-dup: prefer the shallower path per city name
    seen = {}
    for c in sorted(cities):
        name = os.path.basename(c) if os.path.basename(c).upper() != "TNTP" else os.path.basename(os.path.dirname(c))
        if name not in seen: seen[name] = c
    return seen   # name -> dir

def read_links(d, cap_n):
    segs, ws, sp = [], [], []
    n = 0
    with open(os.path.join(d, "link.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
            if len(pts) < 2: continue
            segs.append([(float(x), float(y)) for x, y in pts])
            cap = fnum(r.get("capacity") or 1000) * max(1, fnum(r.get("lanes") or 1))
            ws.append(0.15 + 0.9 * min(1, cap / 6000))
            sp.append(fnum(r.get("free_speed") or r.get("free_speed_mph") or 30))
            n += 1
            if n >= cap_n: break
    return segs, ws, sp

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    store = a[0]
    out = a[a.index("-o") + 1] if "-o" in a else "city_montage.png"
    cols = int(a[a.index("--cols") + 1]) if "--cols" in a else 4
    mx = int(a[a.index("--max") + 1]) if "--max" in a else 16
    cap_n = int(a[a.index("--max-links") + 1]) if "--max-links" in a else 60000
    cities = find_cities(store)
    names = list(cities)[:mx]
    print(f"store has {len(cities)} city networks; rendering {len(names)}")
    rows = math.ceil(len(names) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.0, rows * 3.0), dpi=130)
    axes = np.array(axes).reshape(-1)
    smin, smax = 15, 70
    for i, name in enumerate(names):
        ax = axes[i]; segs, ws, sp = read_links(cities[name], cap_n)
        if not segs:
            ax.set_title(name[:22], fontsize=8); ax.axis("off"); continue
        cs = [plt.cm.plasma(max(0, min(1, (s - smin) / (smax - smin)))) for s in sp]
        ax.add_collection(LineCollection(segs, linewidths=ws, colors=cs))
        ax.autoscale(); ax.set_aspect("equal"); ax.set_facecolor("#0c0f13")
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{re.sub(r'^[0-9]+_','',name)[:24]}  ({len(segs):,} links)", fontsize=8)
    for j in range(len(names), len(axes)): axes[j].axis("off")
    fig.suptitle(f"GMNS global data-store coverage — {len(names)} city networks "
                 f"(width = capacity, color = free-flow speed)", fontsize=12, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98]); fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print("wrote", out)

if __name__ == "__main__":
    main()

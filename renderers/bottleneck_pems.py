#!/usr/bin/env python3
"""Bottleneck & congestion analytics — PeMS / RITIS Probe-Data-Analytics design language.

Two panels, the way Caltrans PeMS ("Bottlenecks", time-space diagram) and UMD CATT Lab RITIS PDA
("Congestion Scan", "Bottleneck Ranking") present corridor congestion:

  (1) Congestion Scan   space-time SPEED heatmap: distance (postmile) x time, speed color (green free,
                        red congested) — the classic PeMS/RITIS time-space diagram.
  (2) Bottleneck Ranking  horizontal bars ranking corridor locations by TOTAL DELAY (veh-min/veh
                        summed over the period), with active-bottleneck duration — PeMS-style.

Input: corridor_speed.csv (corridor, seq, cum_dist_mi, length_mi, time, speed[_qvdf/_inrix], free_flow).
Usage: python bottleneck_pems.py <folder_or_corridor_csv> [-o out.png] [--congested-frac 0.6]
"""
import csv, os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import numpy as np

def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm2min(s):
    m = re.match(r"(\d+):(\d+)", s or ""); return int(m[1]) * 60 + int(m[2]) if m else 0

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    src = a[0]
    path = src if src.endswith(".csv") else os.path.join(src, "corridor_speed.csv")
    if not os.path.exists(path): sys.exit(f"need corridor_speed.csv (not found at {path})")
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(os.path.dirname(path) or ".", "bottleneck_pems.png")
    cfrac = float(a[a.index("--congested-frac") + 1]) if "--congested-frac" in a else 0.6

    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    name = rows[0].get("corridor") or "corridor"
    spcol = "speed_qvdf" if "speed_qvdf" in rows[0] else ("speed" if "speed" in rows[0] else "speed_inrix")
    seqs = sorted({int(fnum(r["seq"])) for r in rows})
    times = sorted({r["time"] for r in rows}, key=hhmm2min)
    dist = {int(fnum(r["seq"])): fnum(r.get("cum_dist_mi") or 0) for r in rows}
    length = {int(fnum(r["seq"])): fnum(r.get("length_mi") or 0.1) for r in rows}
    ff = {int(fnum(r["seq"])): fnum(r.get("free_flow") or 60) or 60 for r in rows}
    cell = {(int(fnum(r["seq"])), r["time"]): fnum(r[spcol]) for r in rows}
    ti = {t: j for j, t in enumerate(times)}
    S = np.full((len(seqs), len(times)), np.nan)
    for i, s in enumerate(seqs):
        for t in times:
            v = cell.get((s, t))
            if v and v > 0: S[i, t and ti[t]] = v
    dt = (hhmm2min(times[1]) - hhmm2min(times[0])) if len(times) > 1 else 15   # bin length (min)

    # ---- per-location total delay (veh-min per vehicle) + active-bottleneck duration ----
    stats = []
    for i, s in enumerate(seqs):
        fftt = length[s] / ff[s] * 60 if ff[s] else 0
        delay = 0.0; active = 0
        for j, t in enumerate(times):
            v = S[i, j]
            if not np.isfinite(v) or v <= 0: continue
            tt = length[s] / v * 60
            delay += max(0.0, tt - fftt) * (dt / dt)     # per-vehicle delay accrued over each bin
            if v < cfrac * ff[s]: active += dt           # minutes in congested state
        stats.append({"seq": s, "mi": dist[s], "delay": delay, "active_min": active, "ff": ff[s]})
    ranked = sorted(stats, key=lambda x: -x["delay"])
    topN = [r for r in ranked if r["delay"] > 0][:12]

    # ---- figure: congestion scan (top) + bottleneck ranking (bottom) ----
    fig = plt.figure(figsize=(11, 9), dpi=130)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 2], hspace=0.32)
    ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1])
    x = [hhmm2min(t) / 60 for t in times]; y = [dist[s] for s in seqs]
    m = ax1.pcolormesh(x, y, S, cmap="RdYlGn", shading="nearest", vmin=0, vmax=max(70, np.nanmax(S)))
    ax1.set_title(f"Congestion Scan — {name} ({spcol})   [PeMS / RITIS style]", fontsize=11)
    ax1.set_xlabel("time of day (h)"); ax1.set_ylabel("distance / postmile (mi)")
    cb = fig.colorbar(m, ax=ax1, label="speed (mph)")
    # mark the worst bottleneck heads with a triangle at their postmile
    for r in topN[:5]:
        ax1.annotate("", xy=(x[0], r["mi"]), xytext=(x[0] - (x[-1]-x[0])*0.03, r["mi"]),
                     arrowprops=dict(arrowstyle="-|>", color="k"))
    if topN:
        labels = [f'mi {r["mi"]:.1f}' for r in topN]
        vals = [r["delay"] for r in topN]
        acts = [r["active_min"] for r in topN]
        ypos = range(len(topN))
        bars = ax2.barh(ypos, vals, color=plt.cm.RdYlGn_r([min(1, v / max(vals)) for v in vals]))
        ax2.set_yticks(list(ypos)); ax2.set_yticklabels(labels, fontsize=9); ax2.invert_yaxis()
        ax2.set_xlabel("total delay (veh-min per vehicle, summed over period)")
        ax2.set_title("Bottleneck Ranking — corridor locations by total delay", fontsize=11)
        for k, (v, act) in enumerate(zip(vals, acts)):
            ax2.text(v, k, f"  {v:.0f} min  ({act:.0f} min congested)", va="center", fontsize=8)
    else:
        ax2.text(0.5, 0.5, "no congested cells (all >= free-flow)", ha="center"); ax2.axis("off")
    fig.suptitle(f"Bottleneck & Congestion Analytics — {name}", fontsize=13, y=0.995)
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"wrote {out}")
    # ---- ranking table (CSV) ----
    tp = out.replace(".png", "_ranking.csv")
    with open(tp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank", "postmile", "total_delay_min", "active_congested_min", "free_flow"])
        for k, r in enumerate(ranked, 1):
            if r["delay"] <= 0: break
            w.writerow([k, round(r["mi"], 2), round(r["delay"], 1), r["active_min"], r["ff"]])
    print(f"wrote {tp}")
    if topN:
        print(f"  worst bottleneck: postmile {topN[0]['mi']:.1f} — {topN[0]['delay']:.0f} veh-min delay, "
              f"{topN[0]['active_min']:.0f} min congested")

if __name__ == "__main__":
    main()

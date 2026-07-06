"""
render_tiers.py -- Facility/volume tiering + percentile scaling experiment
for the ARC Atlanta network (145,971 links).

Renders two offscreen PNGs (1600x1000, dark bg #101418):
  arc_baseline.png : all links 1px, color = green->red by volume/max (outlier-dominated)
  arc_tiers.png    : 3-tier render
      minor  (bottom 60% by volume, plus all centroid connectors) -> drawn FIRST,
             0.6px dim gray-green
      middle (60-90 pct)                                          -> 1.5px muted green
      major  (top 10 pct, connectors excluded)                    -> drawn LAST,
             width 2.5-6px  = 2.5 + 3.5*sqrt(percentile-rank among majors)
             color green->yellow->red on the SAME percentile rank (not vol/max)

Prints metrics for both images:
  (a) % of lit pixels in green / yellow / red hue classes (+ lit % of image)
  (b) count of visually distinct wide corridors (connected components of the
      width>=3px major-link mask, components >= 30 px)
  (c) contrast score = stddev of lit-pixel hues (degrees)

Standalone; only creates files under ai-gen/variants/. Run:
  QT_QPA_PLATFORM=offscreen python render_tiers.py
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import ndimage
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPen, QColor, QPainterPath

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "datasets", "04_arc_atlanta"))
W, H = 1600, 1000
MARGIN = 20
BG = (0x10, 0x14, 0x18)

# ----- tier / style parameters (the "winning" knobs) -----
P_MINOR = 60.0          # bottom 60% by volume -> minor
P_MAJOR = 90.0          # top 10% -> major
W_MINOR, W_MIDDLE = 0.6, 1.5
W_MAJ_LO, W_MAJ_SPAN = 2.5, 3.5   # major width = 2.5 + 3.5*sqrt(rank)
C_MINOR = QColor(44, 60, 52)      # dim gray-green
C_MIDDLE = QColor(58, 118, 82)    # muted green
CONNECTOR_CAP = 99000             # capacity >= this => centroid connector => minor
N_COLOR_BINS = 24                 # style batching resolution


def major_color(rank):
    """green -> yellow -> red on percentile rank in [0,1]."""
    if rank < 0.5:
        t = rank / 0.5
        r, g, b = int(60 + t * (250 - 60)), int(215 + t * (220 - 215)), int(90 + t * (60 - 90))
    else:
        t = (rank - 0.5) / 0.5
        r, g, b = int(250 + t * (255 - 250)), int(220 + t * (55 - 220)), int(60 + t * (50 - 60))
    return QColor(r, g, b)


def baseline_color(frac):
    """green -> red linear on volume/max (the failing status quo)."""
    hue = 120.0 * (1.0 - frac)  # 120=green .. 0=red
    c = QColor()
    c.setHsvF(hue / 360.0, 0.85, 0.85)
    return c


def parse_and_project():
    t0 = time.time()
    lk = pd.read_csv(os.path.join(DATA, "link.csv"),
                     usecols=["link_id", "capacity", "lanes", "geometry"])
    lp = pd.read_csv(os.path.join(DATA, "link_performance.csv"),
                     usecols=["link_id", "volume"])
    df = lk.merge(lp, on="link_id", how="left")
    df["volume"] = df["volume"].fillna(0.0)

    # parse WKT LINESTRING into flat coord arrays + per-link offsets
    xs, ys, offsets = [], [], [0]
    for g in df["geometry"].values:
        body = g[g.index("(") + 1: g.rindex(")")]
        pts = body.split(",")
        for p in pts:
            a = p.split()
            xs.append(float(a[0]))
            ys.append(float(a[1]))
        offsets.append(offsets[-1] + len(pts))
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    offsets = np.asarray(offsets)

    # EPSG:2240 (GA West, ftUS) -> EPSG:3857 to mirror dashboard geometry
    tr = Transformer.from_crs("EPSG:2240", "EPSG:3857", always_xy=True)
    mx, my = tr.transform(xs, ys)

    # fit to canvas (uniform scale, y-flip)
    x0, x1 = mx.min(), mx.max()
    y0, y1 = my.min(), my.max()
    s = min((W - 2 * MARGIN) / (x1 - x0), (H - 2 * MARGIN) / (y1 - y0))
    px = (mx - x0) * s + (W - (x1 - x0) * s) / 2.0
    py = H - ((my - y0) * s + (H - (y1 - y0) * s) / 2.0)
    print(f"parsed+projected {len(df)} links / {len(xs)} pts in {time.time()-t0:.1f}s")
    return df, px, py, offsets


def build_paths(px, py, offsets, idx_groups):
    """idx_groups: list of (style_key, link_index_array) -> dict key->QPainterPath"""
    paths = {}
    for key, idx in idx_groups:
        path = QPainterPath()
        for i in idx:
            a, b = offsets[i], offsets[i + 1]
            path.moveTo(px[a], py[a])
            for j in range(a + 1, b):
                path.lineTo(px[j], py[j])
        paths[key] = path
    return paths


def new_canvas(color=BG):
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor(*color))
    return img


def painter_for(img):
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    return p


def draw_path(p, path, color, width):
    pen = QPen(color, width, Qt.SolidLine, Qt.FlatCap, Qt.BevelJoin)
    p.setPen(pen)
    p.drawPath(path)


def img_to_np(img):
    b = img.constBits()
    arr = np.frombuffer(b, np.uint8).reshape(H, W, 4)  # BGRA
    return arr[:, :, :3][:, :, ::-1].astype(np.float32)  # -> RGB


def metrics(img, wide_mask_img, label):
    rgb = img_to_np(img)
    bg = np.array(BG, np.float32)
    lit = np.abs(rgb - bg).sum(axis=2) > 30  # meaningfully different from bg
    n_lit = int(lit.sum())
    r, g, b = rgb[..., 0][lit], rgb[..., 1][lit], rgb[..., 2][lit]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    hue = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r); hue[rm] = (60 * ((g[rm] - b[rm]) / d[rm]) + 360) % 360
    gm = m & (mx == g) & ~rm; hue[gm] = 60 * ((b[gm] - r[gm]) / d[gm]) + 120
    bm = m & (mx == b) & ~rm & ~gm; hue[bm] = 60 * ((r[bm] - g[bm]) / d[bm]) + 240
    green = ((hue >= 70) & (hue <= 170)).sum()
    yellow = ((hue >= 35) & (hue < 70)).sum()
    red = ((hue <= 25) | (hue >= 345)).sum()
    hue_std = float(hue.std())

    # wide corridors: connected components of the width>=3 mask
    wm = img_to_np(wide_mask_img).sum(axis=2) > 200
    lab, n = ndimage.label(wm, structure=np.ones((3, 3)))
    if n:
        sizes = np.bincount(lab.ravel())[1:]
        n_corr = int((sizes >= 30).sum())
        wide_px = int(wm.sum())
    else:
        n_corr, wide_px = 0, 0

    pct = lambda k: 100.0 * k / max(n_lit, 1)
    print(f"\n[{label}]")
    print(f"  lit pixels          : {n_lit} ({100.0*n_lit/(W*H):.1f}% of image)")
    print(f"  green / yellow / red: {pct(green):.1f}% / {pct(yellow):.1f}% / {pct(red):.1f}% of lit")
    print(f"  wide corridors (w>=3px, comp>=30px): {n_corr}  (wide px: {wide_px})")
    print(f"  contrast (hue stddev, deg): {hue_std:.1f}")
    return dict(lit=n_lit, green=pct(green), yellow=pct(yellow), red=pct(red),
                corridors=n_corr, wide_px=wide_px, hue_std=hue_std)


def main():
    app = QGuiApplication(sys.argv)
    df, px, py, offsets = parse_and_project()
    vol = df["volume"].values
    cap = df["capacity"].values
    n = len(df)
    connector = cap >= CONNECTOR_CAP

    # ---------------- tier classification (volume percentile) ----------------
    real = ~connector
    v_real = vol[real]
    p60 = np.percentile(v_real, P_MINOR)
    p90 = np.percentile(v_real, P_MAJOR)
    tier = np.zeros(n, np.int8)                    # 0=minor
    tier[real & (vol >= p60)] = 1                  # middle
    tier[real & (vol >= p90)] = 2                  # major
    tier[connector] = 0
    print(f"tier thresholds: p60={p60:.0f} veh, p90={p90:.0f} veh | "
          f"minor={int((tier==0).sum())} middle={int((tier==1).sum())} major={int((tier==2).sum())}")

    # percentile rank among majors (0..1), for width and color
    maj = np.where(tier == 2)[0]
    order = vol[maj].argsort().argsort()
    rank = order / max(len(maj) - 1, 1)
    maj_width = W_MAJ_LO + W_MAJ_SPAN * np.sqrt(rank)
    rank_bin = np.minimum((rank * N_COLOR_BINS).astype(int), N_COLOR_BINS - 1)

    t0 = time.time()
    # ---------------- TIERS render ----------------
    groups = [("minor", np.where(tier == 0)[0]), ("middle", np.where(tier == 1)[0])]
    for k in range(N_COLOR_BINS):
        groups.append((("maj", k), maj[rank_bin == k]))
    paths = build_paths(px, py, offsets, groups)

    img_t = new_canvas()
    p = painter_for(img_t)
    draw_path(p, paths["minor"], C_MINOR, W_MINOR)
    draw_path(p, paths["middle"], C_MIDDLE, W_MIDDLE)
    for k in range(N_COLOR_BINS):                  # low volume first, hottest last
        rk = (k + 0.5) / N_COLOR_BINS
        draw_path(p, paths[("maj", k)], major_color(rk), W_MAJ_LO + W_MAJ_SPAN * np.sqrt(rk))
    p.end()
    img_t.save(os.path.join(HERE, "arc_tiers.png"))

    # width>=3 mask for corridor counting (same widths, white on black)
    mask_t = new_canvas((0, 0, 0))
    p = painter_for(mask_t)
    for k in range(N_COLOR_BINS):
        rk = (k + 0.5) / N_COLOR_BINS
        w = W_MAJ_LO + W_MAJ_SPAN * np.sqrt(rk)
        if w >= 3.0:
            draw_path(p, paths[("maj", k)], QColor(255, 255, 255), w)
    p.end()

    # ---------------- BASELINE render ----------------
    vmax = vol.max()
    frac = vol / vmax
    fbin = np.minimum((frac * N_COLOR_BINS).astype(int), N_COLOR_BINS - 1)
    bgroups = [(k, np.where(fbin == k)[0]) for k in range(N_COLOR_BINS)]
    bpaths = build_paths(px, py, offsets, bgroups)
    img_b = new_canvas()
    p = painter_for(img_b)
    for k in range(N_COLOR_BINS):
        draw_path(p, bpaths[k], baseline_color((k + 0.5) / N_COLOR_BINS), 1.0)
    p.end()
    img_b.save(os.path.join(HERE, "arc_baseline.png"))
    mask_b = new_canvas((0, 0, 0))  # baseline has no width>=3 links -> empty mask
    print(f"rendered both in {time.time()-t0:.1f}s")

    mb = metrics(img_b, mask_b, "BASELINE  (1px, color=vol/max)")
    mt = metrics(img_t, mask_t, "TIERS     (3-tier, percentile color)")

    print("\n=== comparison (baseline -> tiers) ===")
    for k in ("green", "yellow", "red", "corridors", "hue_std"):
        print(f"  {k:10s}: {mb[k]:8.1f} -> {mt[k]:8.1f}")


if __name__ == "__main__":
    main()

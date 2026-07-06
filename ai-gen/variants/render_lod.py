#!/usr/bin/env python3
"""render_lod.py — LEVEL-OF-DETAIL + FILTER LAYERS + DATA-CHECK overlay prototype
for the 145,971-link ARC Atlanta network (gui4gmns).

Produces 1600x1000 PNGs next to this script:
  arc_lod_overview.png  zoom-out LOD: only tier-1 links (top 15% capacity*lanes,
                        centroid connectors excluded), width by volume rank
  arc_lod_mid.png       regional zoom (downtown Atlanta bbox), tiers 1-2 (top 50%)
  arc_checks.png        DATA-CHECK layer: volume==0 & capacity>=3000*lanes links
                        in magenta 2px over the dimmed full network

Prints per-view metrics: links drawn, % pixel coverage (clutter measure),
zero-volume-major-link count + lane-miles.  Rendering approach follows
desktop-qt/nexta_qt.py (PySide6 QPainter, QT_QPA_PLATFORM=offscreen).
"""
import csv, os, re, sys, time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import QPointF, Qt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "datasets", "04_arc_atlanta"))
W, H = 1600, 1000
BG = (16, 20, 24)  # same dark background as nexta_qt.py


def fnum(v):
    try:
        return float(v)
    except Exception:
        return 0.0


# ---------------------------------------------------------------- load data
def load():
    t0 = time.time()
    vol = {}
    with open(os.path.join(DATA, "link_performance.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            vol[r["link_id"].strip()] = fnum(r.get("volume"))
    links = []
    num = re.compile(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)")
    with open(os.path.join(DATA, "link.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            g = r.get("geometry") or ""
            pts = num.findall(g)
            if len(pts) < 2:
                continue
            poly = [(float(a), float(b)) for a, b in pts]
            lanes = max(1.0, fnum(r.get("lanes") or 1))
            cap = fnum(r.get("capacity") or 0)
            name = (r.get("name") or "").upper()
            is_conn = "CENTROID" in name or cap >= 50000  # artificial connectors
            links.append({
                "id": r["link_id"], "poly": poly, "lanes": lanes, "cap": cap,
                "cap_tot": cap * lanes, "conn": is_conn,
                "mi": fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 0) / 5280.0,
                "vol": vol.get(r["link_id"].strip(), 0.0),
            })
    print(f"loaded {len(links)} links with geometry in {time.time()-t0:.1f}s "
          f"({sum(1 for L in links if L['conn'])} centroid connectors excluded from tiering)")
    return links


# ---------------------------------------------------------------- tiers
def assign_tiers(links):
    """tier 1 = top 15% cap*lanes, tier 2 = top 50%, tier 3 = rest, tier 4 = connectors."""
    real = sorted((L["cap_tot"] for L in links if not L["conn"]), reverse=True)
    n = len(real)
    thr1 = real[int(n * 0.15) - 1]  # capacity*lanes cutoffs
    thr2 = real[int(n * 0.50) - 1]
    for L in links:
        if L["conn"]:
            L["tier"] = 4
        elif L["cap_tot"] >= thr1:
            L["tier"] = 1
        elif L["cap_tot"] >= thr2:
            L["tier"] = 2
        else:
            L["tier"] = 3
    c = [sum(1 for L in links if L["tier"] == t) for t in (1, 2, 3, 4)]
    print(f"tier cutoffs: tier1 cap*lanes>={thr1:.0f}, tier2 >={thr2:.0f}; "
          f"counts t1={c[0]} t2={c[1]} t3={c[2]} connectors={c[3]}")
    return thr1, thr2


# ---------------------------------------------------------------- view math
def bbox_of(links, pred):
    x0 = y0 = 1e18; x1 = y1 = -1e18
    for L in links:
        if not pred(L):
            continue
        for x, y in L["poly"]:
            x0 = min(x0, x); y0 = min(y0, y); x1 = max(x1, x); y1 = max(y1, y)
    return x0, y0, x1, y1


def transform(bb):
    """fit bbox into W x H preserving aspect, y flipped (state-plane feet -> px)."""
    x0, y0, x1, y1 = bb
    sx, sy = (x1 - x0) or 1, (y1 - y0) or 1
    s = min(W * 0.96 / sx, H * 0.96 / sy)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return lambda x, y: QPointF((x - cx) * s + W / 2, -(y - cy) * s + H / 2)


def coverage(img):
    """% of pixels touched by ink (differ from background)."""
    b = img.constBits().tobytes()  # Format_RGB32 -> BGRA
    bg = bytes((BG[2], BG[1], BG[0]))
    hit = sum(1 for i in range(0, len(b), 4) if b[i:i + 3] != bg)
    return 100.0 * hit / (W * H)


def render(path, draws, bb):
    """draws = list of (links, pen_fn) layers, painted in order."""
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor(*BG))
    qp = QPainter(img)
    T = transform(bb)
    total = 0
    for layer, pen_fn, aa in draws:
        qp.setRenderHint(QPainter.Antialiasing, aa)
        for L in layer:
            qp.setPen(pen_fn(L))
            qp.drawPolyline(QPolygonF([T(x, y) for x, y in L["poly"]]))
            total += 1
    qp.end()
    img.save(path)
    cov = coverage(img)
    print(f"{os.path.basename(path)}: {total} links drawn, pixel coverage {cov:.1f}%")
    return total, cov


def vol_rank_width(subset, wmin=0.7, wmax=4.5):
    """width by volume rank (percentile within the drawn set)."""
    vs = sorted(L["vol"] for L in subset)
    n = max(1, len(vs) - 1)
    import bisect
    def width(L):
        return wmin + (wmax - wmin) * (bisect.bisect_left(vs, L["vol"]) / n)
    return width


def vol_color(subset):
    vmax = max((L["vol"] for L in subset), default=1) or 1
    def col(L):
        t = min(1.0, L["vol"] / vmax)
        r = int(min(255, 510 * t)); g = int(min(255, 255 if t < .5 else 255 - (t - .5) * 510))
        return QColor(r, g, 60)
    return col


# ---------------------------------------------------------------- main
def main():
    app = QGuiApplication(sys.argv)
    links = load()
    thr1, thr2 = assign_tiers(links)
    full_bb = bbox_of(links, lambda L: not L["conn"])

    # baseline clutter: everything drawn 1px (the current dashboard behaviour)
    pen_all = lambda L: QPen(QColor(70, 100, 130), 1)
    base_n, base_cov = render(os.path.join(HERE, "arc_baseline_all.png"),
                              [(links, pen_all, False)], full_bb)

    # ---- view 1: overview LOD (tier 1 only, width by volume rank) ----
    t1 = [L for L in links if L["tier"] == 1]
    wf, cf = vol_rank_width(t1), vol_color(t1)
    pen1 = lambda L: QPen(cf(L), wf(L), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    ov_n, ov_cov = render(os.path.join(HERE, "arc_lod_overview.png"),
                          [(t1, pen1, True)], full_bb)

    # ---- view 2: regional zoom, downtown Atlanta, tiers 1-2 ----
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 2240, always_xy=True)
    bx0, by0 = tr.transform(-84.55, 33.6)
    bx1, by1 = tr.transform(-84.25, 33.9)
    mid_bb = (min(bx0, bx1), min(by0, by1), max(bx0, bx1), max(by0, by1))
    def in_bb(L):
        return any(mid_bb[0] <= x <= mid_bb[2] and mid_bb[1] <= y <= mid_bb[3]
                   for x, y in L["poly"])
    mid = [L for L in links if L["tier"] <= 2 and in_bb(L)]
    wf2, cf2 = vol_rank_width(mid, 0.6, 3.5), vol_color(mid)
    pen2 = lambda L: QPen(cf2(L), wf2(L), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    mid_n, mid_cov = render(os.path.join(HERE, "arc_lod_mid.png"),
                            [(mid, pen2, True)], mid_bb)

    # ---- view 3: DATA-CHECK layer (suspicious zero-volume major links) ----
    # literal check: volume==0 & capacity>=3000*lanes  (in ARC, capacity is
    # per-lane, so this only fires on capacity=99999 centroid connectors)
    sus = [L for L in links if L["vol"] <= 0 and L["cap"] >= 3000 * L["lanes"]]
    lane_mi = sum(L["mi"] * L["lanes"] for L in sus)
    # recalibrated real-road check: zero volume on a tier-1 (top 15% cap*lanes) link
    sus2 = [L for L in links if L["vol"] <= 0 and not L["conn"] and L["tier"] == 1]
    lane_mi2 = sum(L["mi"] * L["lanes"] for L in sus2)
    print(f"CHECK-A zero-volume majors (volume==0 & capacity>=3000*lanes): "
          f"{len(sus)} links, {lane_mi:.1f} lane-miles -- ALL are centroid connectors")
    print(f"CHECK-B zero-volume tier-1 real roads (volume==0 & cap*lanes>={thr1:.0f}): "
          f"{len(sus2)} links, {lane_mi2:.1f} lane-miles")
    dim = lambda L: QPen(QColor(46, 54, 62), 1)
    mag = lambda L: QPen(QColor(255, 0, 200), 2, Qt.SolidLine, Qt.RoundCap)
    org = lambda L: QPen(QColor(255, 150, 0), 3, Qt.SolidLine, Qt.RoundCap)
    ck_n, ck_cov = render(os.path.join(HERE, "arc_checks.png"),
                          [(links, dim, False), (sus, mag, True), (sus2, org, True)],
                          full_bb)

    # ---- metric summary ----
    print("\n=== METRICS ===")
    print(f"baseline (all links, current behaviour): {base_n} links, {base_cov:.1f}% coverage")
    print(f"overview LOD (tier1, top15% cap*lanes>= {thr1:.0f}): {ov_n} links "
          f"({100*ov_n/len(links):.1f}% of net), {ov_cov:.1f}% coverage")
    print(f"mid zoom (tiers1-2, cap*lanes>= {thr2:.0f}, downtown bbox): {mid_n} links, "
          f"{mid_cov:.1f}% coverage")
    print(f"checks view: {ck_n} links ({len(sus)} magenta, {len(sus2)} orange), "
          f"{ck_cov:.1f}% coverage")
    print(f"zero-volume majors: literal check {len(sus)} links / {lane_mi:.1f} lane-mi "
          f"(all connectors); real tier-1 {len(sus2)} links / {lane_mi2:.1f} lane-mi")


if __name__ == "__main__":
    main()

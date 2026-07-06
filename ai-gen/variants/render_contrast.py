#!/usr/bin/env python3
"""render_contrast.py — COLOR SCIENCE variant test for the 145,971-link ARC Atlanta
network over real map backgrounds (gui4gmns).

Problem: thin green 1px lines vanish over OSM/satellite imagery, and linear
volume normalization (v = vol/max, max = outlier) makes every link green.

Produces four 1600x1000 PNGs next to this script:
  arc_osm_plain.png   linear v=vol/max ramp, no casing, OSM dimmed 40%
  arc_osm_tuned.png   LOG ramp v=log1p(vol)/log1p(p99), 1.5px #000 a180 casing,
                      OSM dimmed 55% + desaturated 60%
  arc_sat_plain.png   same plain style over ESRI World_Imagery satellite tiles
  arc_sat_tuned.png   same tuned style over satellite tiles

Metrics per image:
  - mean local contrast: |luminance(link px) - mean luminance of non-network px
    in its 11x11 (5 px radius) neighborhood| / 255, 2000 random link pixels
  - % class-distinguishable: of pixels on true yellow/red links (vol >= p85),
    share whose DISPLAYED hue is clearly non-green
  - overall % red+yellow: share of all network pixels displaying non-green hue

Rendering follows desktop-qt/nexta_qt.py (PySide6 QPainter, offscreen).
OSM tiles cached in desktop-qt/tile_cache (z_x_y.png); satellite tiles cached
under ai-gen/variants/sat_cache/.
"""
import csv, math, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import QPointF, QRectF, Qt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "datasets", "04_arc_atlanta"))
OSM_CACHE = os.path.normpath(os.path.join(HERE, "..", "..", "desktop-qt", "tile_cache"))
SAT_CACHE = os.path.join(HERE, "sat_cache")
W, H = 1600, 1000
UA = {"User-Agent": "gui4gmns/1.0 (research; ASU trans+AI lab)"}

# tuned-style parameters under test
DIM_PLAIN = 0.40          # 40% dim (blend toward black)
DIM_TUNED = 0.55          # 55% dim
DESAT_TUNED = 0.60        # 60% desaturation (tuned only)
CASING_W = 1.5            # px each side
CASING_RGBA = (0, 0, 0, 180)
WMAX_TUNED = 2.2          # tuned width = 1 + WMAX_TUNED*v_log (template uses 1+5*v)


def fnum(v):
    try:
        return float(v)
    except Exception:
        return 0.0


# ------------------------------------------------------------------ data load
def load_links():
    vol = {}
    with open(os.path.join(DATA, "link_performance.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            vol[r["link_id"].strip()] = fnum(r.get("volume"))
    num = re.compile(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)")
    links = []
    with open(os.path.join(DATA, "link.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            pts = num.findall(r.get("geometry") or "")
            if len(pts) < 2:
                continue
            name = (r.get("name") or "").upper()
            conn = "CENTROID" in name or fnum(r.get("capacity") or 0) >= 50000
            links.append({"poly": [(float(a), float(b)) for a, b in pts],
                          "vol": vol.get(r["link_id"].strip(), 0.0), "conn": conn})
    return links


# ------------------------------------------------------------------ projection
def project(links):
    """EPSG:2240 -> lon/lat -> web-mercator global px; pick zoom; screen coords."""
    from pyproj import Transformer
    tr = Transformer.from_crs(2240, 4326, always_xy=True)
    flat_x, flat_y, idx = [], [], []
    for L in links:
        idx.append(len(flat_x))
        for x, y in L["poly"]:
            flat_x.append(x); flat_y.append(y)
    idx.append(len(flat_x))
    lon, lat = tr.transform(np.array(flat_x), np.array(flat_y))
    lat = np.clip(lat, -85.05, 85.05)
    # global px at zoom z: unit coords * 256 * 2^z
    ux = (lon + 180.0) / 360.0
    lr = np.radians(lat)
    uy = (1.0 - np.log(np.tan(lr) + 1.0 / np.cos(lr)) / math.pi) / 2.0
    # bbox on real (non-connector) links
    keep = np.zeros(len(flat_x), bool)
    for i, L in enumerate(links):
        if not L["conn"]:
            keep[idx[i]:idx[i + 1]] = True
    bx0, bx1 = ux[keep].min(), ux[keep].max()
    by0, by1 = uy[keep].min(), uy[keep].max()
    for z in range(7, 15):
        n = 256.0 * (1 << z)
        s = min(W * 0.96 / max((bx1 - bx0) * n, 1), H * 0.96 / max((by1 - by0) * n, 1))
        if s <= 1.0:
            break
    n = 256.0 * (1 << z)
    gcx, gcy = (bx0 + bx1) / 2 * n, (by0 + by1) / 2 * n
    ox, oy = gcx - (W / 2) / s, gcy - (H / 2) / s        # viewport origin, global px
    sx = (ux * n - ox) * s
    sy = (uy * n - oy) * s
    polys = []
    for i, L in enumerate(links):
        polys.append(QPolygonF([QPointF(sx[j], sy[j]) for j in range(idx[i], idx[i + 1])]))
    print(f"projection: zoom z={z}, tile scale {s:.3f}, "
          f"viewport global px origin ({ox:.0f},{oy:.0f})")
    return polys, z, s, ox, oy


# ------------------------------------------------------------------ basemaps
def fetch(url, path):
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
        open(path, "wb").write(data)
    except Exception as e:
        print(f"  tile fetch failed {url}: {e}")


def basemap(kind, z, s, ox, oy):
    """compose 1600x1000 background from tiles (kind='osm'|'sat')."""
    n = 1 << z
    tx0, tx1 = int(ox // 256), int((ox + W / s) // 256)
    ty0, ty1 = int(oy // 256), int((oy + H / s) // 256)
    jobs = []
    for tx in range(max(0, tx0), min(n - 1, tx1) + 1):
        for ty in range(max(0, ty0), min(n - 1, ty1) + 1):
            if kind == "osm":
                p = os.path.join(OSM_CACHE, f"{z}_{tx}_{ty}.png")
                u = f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png"
            else:
                p = os.path.join(SAT_CACHE, f"{z}_{tx}_{ty}.jpg")
                u = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
                     f"World_Imagery/MapServer/tile/{z}/{ty}/{tx}")   # note z/y/x
            jobs.append((tx, ty, p, u))
    missing = [(u, p) for _, _, p, u in jobs if not os.path.exists(p)]
    if missing:
        print(f"  fetching {len(missing)} {kind} tiles ...")
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda a: fetch(*a), missing))
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor(200, 204, 208) if kind == "osm" else QColor(40, 44, 40))
    qp = QPainter(img)
    qp.setRenderHint(QPainter.SmoothPixmapTransform, True)
    ok = 0
    for tx, ty, p, _ in jobs:
        t = QImage(p)
        if t.isNull():
            continue
        qp.drawImage(QRectF((tx * 256 - ox) * s, (ty * 256 - oy) * s, 256 * s, 256 * s), t)
        ok += 1
    qp.end()
    print(f"  basemap {kind}: {ok}/{len(jobs)} tiles composed at z{z}")
    return img


# ------------------------------------------------------------------ np <-> QImage
def qimg_to_np(img):
    img = img.convertToFormat(QImage.Format_RGB32)
    b = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
    return b[:, :img.width(), 2::-1].copy()          # BGRX -> RGB


def np_to_qimg(arr):
    h, w, _ = arr.shape
    bgra = np.empty((h, w, 4), np.uint8)
    bgra[..., 0] = arr[..., 2]; bgra[..., 1] = arr[..., 1]
    bgra[..., 2] = arr[..., 0]; bgra[..., 3] = 255
    return QImage(bgra.tobytes(), w, h, w * 4, QImage.Format_RGB32).copy()


def gray_to_np(img):
    b = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())
    return b[:, :img.width()].copy()


def adjust(arr, dim, desat):
    a = arr.astype(np.float32)
    if desat > 0:
        g = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
        a = a * (1 - desat) + g[..., None] * desat
    a *= (1 - dim)
    return np.clip(a, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ ramps
def ramp_qcolor(t):
    t = max(0.0, min(1.0, t))
    r = min(255, int(510 * t)); g = 255 if t < .5 else max(0, int(255 - (t - .5) * 510))
    return QColor(r, g, 60)


# ------------------------------------------------------------------ overlay + masks
def draw_pass(fmt, order, polys, pen_of, fill=None):
    img = QImage(W, H, fmt)
    img.fill(fill if fill is not None else 0)
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing, True)
    for i in order:
        qp.setPen(pen_of(i))
        qp.drawPolyline(polys[i])
    qp.end()
    return img


def build_variant(tag, polys, vols, order, hot, v_of, w_of, casing):
    """returns overlay(ARGB), net_mask, ink_mask, hot_mask (np uint8)."""
    t0 = time.time()
    over = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    over.fill(0)
    qp = QPainter(over)
    qp.setRenderHint(QPainter.Antialiasing, True)
    if casing:
        cc = QColor(*CASING_RGBA)
        for i in order:
            qp.setPen(QPen(cc, w_of(i) + 2 * CASING_W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            qp.drawPolyline(polys[i])
    for i in order:
        qp.setPen(QPen(ramp_qcolor(v_of(i)), w_of(i), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        qp.drawPolyline(polys[i])
    qp.end()
    white = QColor(255, 255, 255)
    pen_net = lambda i: QPen(white, w_of(i), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    net = gray_to_np(draw_pass(QImage.Format_Grayscale8, order, polys, pen_net))
    if casing:
        pen_ink = lambda i: QPen(white, w_of(i) + 2 * CASING_W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        ink = gray_to_np(draw_pass(QImage.Format_Grayscale8, order, polys, pen_ink))
    else:
        ink = net
    hot_order = [i for i in order if hot[i]]
    hotm = gray_to_np(draw_pass(QImage.Format_Grayscale8, hot_order, polys, pen_net))
    print(f"  overlay+masks [{tag}] drawn in {time.time()-t0:.1f}s")
    return over, net, ink, hotm


# ------------------------------------------------------------------ metrics
def hue_classify(rgb):
    """rgb Nx3 float -> (nongreen bool, green bool). Requires chroma to count."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = rgb.max(1); mn = rgb.min(1); d = mx - mn
    h = np.zeros(len(rgb))
    m = d > 1e-6
    i = m & (mx == r); h[i] = (60.0 * ((g - b) / np.where(d == 0, 1, d)) % 360)[i]
    i = m & (mx == g) & (mx != r); h[i] = (60.0 * ((b - r) / np.where(d == 0, 1, d)) + 120)[i]
    i = m & (mx == b) & (mx != r) & (mx != g); h[i] = (60.0 * ((r - g) / np.where(d == 0, 1, d)) + 240)[i]
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    vivid = (sat > 0.25) & (mx > 60)
    nongreen = vivid & ((h < 95) | (h >= 300))
    green = vivid & (h >= 95) & (h < 180)
    return nongreen, green


def metrics(final_np, net, ink, hotm, n_samples=2000, seed=42):
    lum = final_np[..., 0] * 0.299 + final_np[..., 1] * 0.587 + final_np[..., 2] * 0.114
    core = net >= 180
    ys, xs = np.nonzero(core)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(ys), size=min(n_samples, len(ys)), replace=False)
    bgm = ink < 64
    tot = cnt = 0.0
    for k in pick:
        y, x = int(ys[k]), int(xs[k])
        y0, y1 = max(0, y - 5), min(H, y + 6); x0, x1 = max(0, x - 5), min(W, x + 6)
        wb = bgm[y0:y1, x0:x1]
        if not wb.any():
            continue
        tot += abs(lum[y, x] - lum[y0:y1, x0:x1][wb].mean()) / 255.0
        cnt += 1
    contrast = tot / max(cnt, 1)
    # displayed hue classes on core network pixels
    px = final_np[core].astype(np.float64)
    nongreen, _ = hue_classify(px)
    pct_ry = 100.0 * nongreen.mean()
    hotcore = core & (hotm >= 180)
    pxh = final_np[hotcore].astype(np.float64)
    ngh, _ = hue_classify(pxh)
    pct_dist = 100.0 * ngh.mean() if len(pxh) else 0.0
    return contrast, pct_dist, pct_ry


# ------------------------------------------------------------------ main
def main():
    app = QGuiApplication(sys.argv)
    os.makedirs(SAT_CACHE, exist_ok=True)
    t0 = time.time()
    links = load_links()
    vols = np.array([L["vol"] for L in links])
    pos = vols[vols > 0]
    vmax = float(vols.max()); p99 = float(np.percentile(pos, 99))
    p85 = float(np.percentile(pos, 85)); p25 = float(np.percentile(pos, 25))
    p50 = float(np.percentile(pos, 50))
    print(f"loaded {len(links)} links; volume max={vmax:.0f} p99={p99:.0f} p85={p85:.0f} "
          f"p50={p50:.0f} p25={p25:.0f} ({100*len(pos)/len(links):.1f}% links with volume>0)")
    polys, z, s, ox, oy = project(links)
    order = list(np.argsort(vols))                    # low volume first, hot links on top
    hot = vols >= p85                                 # true yellow/red class (data-driven)
    lo, hi = math.log1p(p25), math.log1p(p99)         # anchored log ramp: p25 -> 0, p99 -> 1

    # style closures ------------------------------------------------------
    v_lin = lambda i: vols[i] / vmax
    w_lin = lambda i: 1.0 + 5.0 * (vols[i] / vmax)                 # template rule
    v_log = lambda i: max(0.0, min(1.0, (math.log1p(vols[i]) - lo) / (hi - lo)))
    w_log = lambda i: 1.0 + WMAX_TUNED * v_log(i)

    print("building network overlays and masks ...")
    ov_plain, net_p, ink_p, hot_p = build_variant("plain/linear", polys, vols, order, hot,
                                                  v_lin, w_lin, casing=False)
    ov_tuned, net_t, ink_t, hot_t = build_variant("tuned/log+casing", polys, vols, order, hot,
                                                  v_log, w_log, casing=True)

    rows = []
    for kind in ("osm", "sat"):
        bm = qimg_to_np(basemap(kind, z, s, ox, oy))
        for style, ov, net, ink, hotm, dim, desat in (
                ("plain", ov_plain, net_p, ink_p, hot_p, DIM_PLAIN, 0.0),
                ("tuned", ov_tuned, net_t, ink_t, hot_t, DIM_TUNED, DESAT_TUNED)):
            base = np_to_qimg(adjust(bm, dim, desat))
            qp = QPainter(base)
            qp.drawImage(0, 0, ov)
            qp.end()
            out = os.path.join(HERE, f"arc_{kind}_{style}.png")
            base.save(out)
            fin = qimg_to_np(base)
            c, d, ry = metrics(fin, net, ink, hotm)
            rows.append((os.path.basename(out), c, d, ry))
            print(f"  wrote {out}")

    print(f"\n=== METRICS (2000-sample local contrast r=5px; hot = vol>=p85={p85:.0f}) ===")
    print(f"{'image':<22}{'mean local contrast':>20}{'% class distinguishable':>25}{'% red+yellow overall':>22}")
    for name, c, d, ry in rows:
        print(f"{name:<22}{c:>20.3f}{d:>25.1f}{ry:>22.1f}")
    print(f"\nparameters: plain dim={DIM_PLAIN:.0%}; tuned dim={DIM_TUNED:.0%} desat={DESAT_TUNED:.0%}, "
          f"casing {CASING_W}px/side rgba{CASING_RGBA}, "
          f"v=(log1p(vol)-log1p(p25))/(log1p(p99)-log1p(p25)) clamp [0,1], "
          f"width=1+{WMAX_TUNED}*v; total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

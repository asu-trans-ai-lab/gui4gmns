import csv, os, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
app = QApplication([])
D = "datasets/01_sioux_falls"
def f(v):
    try: return float(v)
    except: return 0.0
nodes = {int(f(r["node_id"])): (f(r["x_coord"]), f(r["y_coord"]), (r.get("zone_id") or "").strip())
         for r in csv.DictReader(open(D + "/node.csv"))}
zpts = {}
for i, (x, y, z) in nodes.items():
    if z: zpts.setdefault(z, []).append((x, y))
zc = {z: (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)) for z, ps in zpts.items()}
links = []
for r in csv.DictReader(open(D + "/link.csv")):
    a = nodes.get(int(f(r["from_node_id"]))); b = nodes.get(int(f(r["to_node_id"])))
    if a and b: links.append(((a[0], a[1]), (b[0], b[1])))
od = {}
for r in csv.DictReader(open(D + "/demand.csv")):
    oz = (r.get("o_zone_id") or "").strip(); dz = (r.get("d_zone_id") or "").strip(); v = f(r.get("volume"))
    if v > 0 and oz in zc and dz in zc and oz != dz: od[(oz, dz)] = od.get((oz, dz), 0) + v
top = sorted(od.items(), key=lambda kv: -kv[1])[:400]
mercy = lambda lat: math.degrees(math.log(math.tan(math.radians(45 + lat / 2))))
xs = [p[0] for l in links for p in l]; ys = [mercy(p[1]) for l in links for p in l]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
W, H = 900, 900; pad = 30
s = min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0))
def P(x, y): return (pad + (x - x0) * s, H - pad - (mercy(y) - y0) * s)
img = QImage(W, H, QImage.Format_RGB32); img.fill(QColor(16, 20, 24))
p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
p.setPen(QPen(QColor(42, 59, 51), 1))
for a, b in links:
    pa, pb = P(*a), P(*b); p.drawLine(int(pa[0]), int(pa[1]), int(pb[0]), int(pb[1]))
mx = max(v for _, v in top)
for (o, d), v in sorted(top, key=lambda kv: kv[1]):
    t = v / mx; pa, pb = P(*zc[o]), P(*zc[d])
    p.setPen(QPen(QColor(255, int(180 - 120 * t), int(80 - 60 * t), int(90 + 130 * t)), 0.6 + 4 * t))
    p.drawLine(int(pa[0]), int(pa[1]), int(pb[0]), int(pb[1]))
for z, (x, y) in zc.items():
    px, py = P(x, y); p.fillRect(int(px) - 3, int(py) - 3, 6, 6, QColor(255, 210, 87))
p.setPen(QColor(140, 150, 163)); p.setFont(QFont("Arial", 12))
p.drawText(pad, 22, "gui4gmns demand OD desire lines (learned from plot4gmns) - Sioux Falls")
p.setFont(QFont("Arial", 9)); p.setPen(QColor(120, 130, 143))
p.drawText(pad, H - 10, f"{len(od)} OD pairs  total {sum(od.values()):.0f} veh  top 400 desire lines  "
                        f"gold=zone centroids  width/red=volume")
p.end(); img.save("ai-gen/variants/demand_desirelines_sioux.png")
print("wrote demand_desirelines_sioux.png", W, "x", H, "| OD pairs", len(od))

import csv, os, math, re, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtWidgets import QApplication
app = QApplication([])
D = sys.argv[1]; CLK = int(sys.argv[2]) if len(sys.argv) > 2 else 1050  # minute of day (17:30)
def f(v):
    try: return float(v)
    except: return 0.0
my = lambda lat: math.degrees(math.log(math.tan(math.radians(45+lat/2))))
links = {}
for r in csv.DictReader(open(D+"/network/link.csv", encoding="utf-8-sig")):
    pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
    if len(pts) >= 2: links[r["link_id"]] = [(float(x), my(float(y))) for x, y in pts]
def curbin():
    return f"{CLK//60:02d}:{(CLK%60)//15*15:02d}"
b = curbin()
tmc = {}
for r in csv.DictReader(open(D+"/tmc_speed_15min.csv", encoding="utf-8-sig")):
    if r["time"] == b: tmc[r["link_id"]] = f(r["speed"])
sens = {r["zone_id"]: (f(r["longitude"]), my(f(r["latitude"]))) for r in csv.DictReader(open(D+"/sensor_points.csv", encoding="utf-8-sig"))}
sts = {}
for r in csv.DictReader(open(D+"/sensor_15min.csv", encoding="utf-8-sig")):
    if r["time"] == b: sts[r["zone_id"]] = (f(r["speed"]), f(r["volume"]))
wp = []
for r in csv.DictReader(open(D+"/waypoints.csv", encoding="utf-8-sig")):
    t = int(((f(r.get("t_unix"))-14400) % 86400)//60)
    if abs(((t-CLK+720) % 1440)-720) <= 25: wp.append((f(r["longitude"]), my(f(r["latitude"])), f(r.get("speed_mph"))))
xs = [p[0] for g in links.values() for p in g]; ys = [p[1] for g in links.values() for p in g]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
W, H, pad = 1400, 1000, 40
s = min((W-2*pad)/(x1-x0), (H-2*pad)/(y1-y0))
P = lambda x, y: (pad+(x-x0)*s, H-pad-(y-y0)*s)
img = QImage(W, H, QImage.Format_RGB32); img.fill(QColor(16, 20, 24))
p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
def ramp(v, ff=70):
    r = max(0, min(1, 1-v/ff)); return QColor(int(510*r) if r < .5 else 255, 255 if r < .5 else int(255-(r-.5)*510), 60)
# network
p.setPen(QPen(QColor(58, 69, 81), 1))
for g in links.values():
    for i in range(len(g)-1): a, c = P(*g[i]), P(*g[i+1]); p.drawLine(int(a[0]), int(a[1]), int(c[0]), int(c[1]))
# GPS waypoints
for x, y, sp in wp:
    a = P(x, y); r = max(0, min(1, 1-sp/65))
    p.fillRect(int(a[0])-1, int(a[1])-1, 3, 3, QColor(int(510*r) if r < .5 else 255, 255 if r < .5 else int(255-(r-.5)*510), 80))
# TMC speed
for lid, v in tmc.items():
    g = links.get(lid)
    if not g: continue
    p.setPen(QPen(ramp(v), 4))
    for i in range(len(g)-1): a, c = P(*g[i]), P(*g[i+1]); p.drawLine(int(a[0]), int(a[1]), int(c[0]), int(c[1]))
# sensors
for z, (x, y) in sens.items():
    a = P(x, y); ts = sts.get(z); vol = ts[1] if ts else 0
    p.setBrush(QBrush(ramp(ts[0], 65) if ts else QColor(91, 107, 125))); p.setPen(QPen(QColor(255, 255, 255), 1))
    rr = int(5+min(10, vol/40)); p.drawEllipse(int(a[0])-rr, int(a[1])-rr, 2*rr, 2*rr)
p.setPen(QColor(150, 160, 173)); p.setFont(QFont("Arial", 13))
p.drawText(pad, 26, f"ITS I-95 (VA) data hub  {CLK//60:02d}:{CLK%60:02d}  -  network + TMC speed + loop sensors + GPS waypoints")
p.setFont(QFont("Arial", 10)); p.setPen(QColor(120, 130, 143))
p.drawText(pad, H-14, f"{len(links)} links . {len(tmc)} TMC-speed links . {len(sens)} sensors (size=volume) . {len(wp)} live GPS pts . green=free-flow red=slow  |  2.3GB source -> 1.2MB sample")
p.end(); img.save(D+"/its_render.png"); print("wrote its_render.png at", curbin(), "|", len(tmc), "tmc,", len(wp), "gps")

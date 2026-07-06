import csv, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication
app = QApplication([])
rows = list(csv.DictReader(open("datasets/06_nvta_am_PRIVATE/corridor_speed.csv")))
def f(v):
    try: return float(v)
    except: return 0.0
seqs = sorted({int(f(r["seq"])) for r in rows})
bins = sorted({r["time"] for r in rows}, key=lambda s: int(s[:2]) * 60 + int(s[3:5]))
dist = {int(f(r["seq"])): f(r["cum_dist_mi"]) for r in rows}
cell = {(int(f(r["seq"])), r["time"]): (f(r["speed_inrix"]), f(r["speed_qvdf"])) for r in rows}
ff = 70.0
def spd(sp):
    rr = max(0, min(1, 1 - sp / ff))
    return QColor(int(510 * rr) if rr < .5 else 255, 255 if rr < .5 else int(255 - (rr - .5) * 510), 60)
def dif(d):
    t = max(-15, min(15, d)) / 15
    return QColor(int(120 + 135 * t), int(120 - 100 * t), 80) if t > 0 else QColor(80, int(120 + 100 * -t), int(160 + 95 * -t))
cw, ch = 26, 15; nb, ns = len(bins), len(seqs); pw, ph = nb * cw, ns * ch
gap, lab = 46, 34; W, H = gap + (pw + gap) * 3, lab + ph + 60
img = QImage(W, H, QImage.Format_RGB32); img.fill(QColor(20, 24, 29))
p = QPainter(img); p.setFont(QFont("Arial", 11))
for title, pi in [("INRIX observed", 0), ("QVDF model", 1), ("model minus observed (bias)", 2)]:
    x0 = gap + (pw + gap) * pi
    p.setPen(QColor(140, 150, 163)); p.drawText(x0, lab - 14, title)
    for yi, s in enumerate(seqs):
        for xi, tb in enumerate(bins):
            v = cell.get((s, tb))
            if not v: continue
            io, iq = v
            if pi == 0: col = spd(io) if io > 0 else QColor(27, 32, 39)
            elif pi == 1: col = spd(iq) if iq > 0 else QColor(27, 32, 39)
            else: col = dif(iq - io) if (io > 0 and iq > 0) else QColor(27, 32, 39)
            p.fillRect(x0 + xi * cw, lab + yi * ch, cw - 1, ch - 1, col)
    p.setPen(QColor(120, 130, 143)); p.setFont(QFont("Arial", 8))
    p.drawText(x0, lab + ph + 13, bins[0]); p.drawText(x0 + pw - 30, lab + ph + 13, bins[-1])
    p.setFont(QFont("Arial", 11))
p.setPen(QColor(120, 130, 143)); p.setFont(QFont("Arial", 9))
p.drawText(gap, H - 16, "I-395 NB AM  .  distance down (0.0 to 10.5 mi)  .  time right (05:00 to 09:45)  ."
                        "  green=free-flow(70)  red=breakdown  .  validation RMSE 8.47 mph  R2 0.615  bias +3.5 mph")
p.setFont(QFont("Arial", 8)); p.drawText(4, lab + 8, "0mi"); p.drawText(4, lab + ph, f"{dist[seqs[-1]]:.1f}mi")
p.end(); img.save("ai-gen/variants/nvta_corridor_contour.png")
print("wrote nvta_corridor_contour.png", W, "x", H)

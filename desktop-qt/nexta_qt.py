#!/usr/bin/env python3
"""NeXTA-X desktop (Qt) — cross-platform desktop viewer for DTALite / TAPLite / ODME / DLSim.

Implements SHARED_CONTRACT.md with classic-NEXTA UI structure (Users Guide terms):
Layer Control Panel (dock) · MOE Toolbar · Animation View (time slider + play) · Inspector ·
Summary Statistics · live-follow of a run folder · Run Engine (QProcess: dlsim_run.exe) with log tail.

Usage:
  python nexta_qt.py [dataset_folder]
  python nexta_qt.py <folder> --snapshot out.png [--moe td] [--time 07:30]   # headless render (CI)
PySide6 (Qt 6). C++ port follows this widget/data design 1:1 (see README).
"""
import csv, json, math, os, re, sys, urllib.request
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QProcess
from PySide6.QtGui import (QAction, QColor, QPainter, QPen, QPolygonF, QBrush, QImage)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QDockWidget, QVBoxLayout, QLabel,
    QCheckBox, QComboBox, QSlider, QPushButton, QFileDialog, QToolBar, QTextEdit, QHBoxLayout)

# ---------------- model (contract §1) ----------------
def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm_to_min(s):
    m = re.match(r"(\d+):(\d+)", s or "")
    return int(m[1])*60+int(m[2]) if m else 0
def min_to_hhmm(m): return f"{int(m//60)%24:02d}:{int(m%60):02d}"

class Model:
    def __init__(self):
        self.nodes={}; self.links={}; self.link_list=[]
        self.bins=[]; self.td={}; self.paths=[]; self.trajs={}
        self.run=None; self.max_vol=1.0; self.max_q=1.0
        self.tmin, self.tmax = 420, 480

    def load_folder(self, d):
        self.__init__()
        log=[]
        def rd(name):
            p=os.path.join(d,name)
            if not os.path.exists(p): return None
            with open(p, encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
        n=rd("node.csv")
        if n:
            for r in n:
                self.nodes[int(fnum(r["node_id"]))]=(fnum(r["x_coord"]),fnum(r["y_coord"]),
                                                     (r.get("zone_id") or "").strip())
            log.append(f"nodes x{len(n)}")
        l=rd("link.csv")
        if l:
            for r in l:
                lid=int(fnum(r["link_id"])); poly=None
                g=r.get("geometry") or ""
                if "LINESTRING" in g:
                    pts=re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)",g)
                    if len(pts)>=2: poly=[(float(a),float(b)) for a,b in pts]
                self.links[lid]=dict(id=lid,f=int(fnum(r["from_node_id"])),t=int(fnum(r["to_node_id"])),
                    poly=poly,attrs=r,lanes=max(1,fnum(r.get("lanes") or 1)),
                    cap=fnum(r.get("capacity") or 1800),
                    ln=fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 1),
                    vol=0.0,voc=0.0,q=0.0)
            log.append(f"links x{len(l)}")
        p=rd("link_performance.csv")
        if p:
            volcol="cum_departure" if "cum_departure" in p[0] else "volume"
            for r in p:
                L=self.links.get(int(fnum(r["link_id"])))
                if not L: continue
                L["vol"]=fnum(r.get(volcol)); L["q"]=fnum(r.get("max_queue_exb") or r.get("queue") or 0)
                L["voc"]=L["vol"]/(L["cap"]*L["lanes"]*8) if L["cap"]*L["lanes"]>0 else 0
            log.append(f"MOE x{len(p)}")
        t=rd("link_performance_15min.csv")
        if t:
            bins=sorted({r["time_bin_start"] for r in t}, key=hhmm_to_min)
            self.bins=bins; bidx={b:i for i,b in enumerate(bins)}
            for r in t:
                self.td.setdefault(int(fnum(r["link_id"])),{})[bidx[r["time_bin_start"]]]= \
                    (fnum(r.get("inflow_veh")), fnum(r.get("queue_exb") or 0))
            log.append(f"TD x{len(t)}")
        pf=rd("path_flow.csv")
        if pf:
            for r in pf:
                ids=[int(x) for x in (r.get("link_ids") or "").split(";") if x.strip().isdigit()]
                if ids: self.paths.append((fnum(r.get("base_volume") or r.get("volume") or 1),ids))
            self.paths.sort(reverse=True); log.append(f"paths x{len(pf)}")
        tr=rd("agent_trajectory.csv")
        if tr:
            for r in tr:
                self.trajs.setdefault(int(fnum(r["agent_id"])),[]).append(
                    (fnum(r["time_min"]), int(fnum(r["link_id"])), r.get("buffer"), r.get("traffic_state")))
            for ev in self.trajs.values(): ev.sort()
            ts=[e[0] for ev in self.trajs.values() for e in ev]
            if ts: self.tmin,self.tmax=int(min(ts)),int(max(ts))+1
            log.append(f"traj agents x{len(self.trajs)}")
        if self.bins and not tr:
            self.tmin=hhmm_to_min(self.bins[0]); self.tmax=hhmm_to_min(self.bins[-1])+15
        rj=os.path.join(d,"run_summary.json")
        if os.path.exists(rj):
            self.run=json.load(open(rj)); log.append("run")
        # optional CRS reprojection (crs.txt = EPSG code) -> lon/lat, enabling the basemap layer
        crs=os.path.join(d,"crs.txt")
        if os.path.exists(crs):
            try:
                import pyproj
                epsg=int(open(crs).read().strip().upper().replace("EPSG:",""))
                tr=pyproj.Transformer.from_crs(epsg,4326,always_xy=True)
                for nid,(x,y,z) in list(self.nodes.items()):
                    lon,lat=tr.transform(x,y); self.nodes[nid]=(lon,lat,z)
                for L in self.links.values():
                    if L["poly"]:
                        xs=[p[0] for p in L["poly"]]; ys=[p[1] for p in L["poly"]]
                        lo,la=tr.transform(xs,ys); L["poly"]=list(zip(lo,la))
                log.append(f"reprojected EPSG:{epsg}")
            except Exception as e: print("crs transform failed:",e)
        for L in self.links.values():
            if not L["poly"]:
                a=self.nodes.get(L["f"]); b=self.nodes.get(L["t"])
                if a and b: L["poly"]=[(a[0],a[1]),(b[0],b[1])]
        self.link_list=[L for L in self.links.values() if L["poly"]]
        # geographic? -> convert lat to Web-Mercator degrees so OSM tiles align linearly
        xs=[p[0] for L in self.link_list for p in L["poly"]]
        ys=[p[1] for L in self.link_list for p in L["poly"]]
        self.geo=bool(xs) and -181<min(xs)<max(xs)<181 and -85<min(ys)<max(ys)<85
        if os.path.exists(os.path.join(d,"crs.txt")) and open(os.path.join(d,"crs.txt")).read().strip().lower()=="none": self.geo=False
        if self.geo:
            my=lambda lat: math.degrees(math.log(math.tan(math.radians(45+lat/2))))
            for L in self.link_list: L["poly"]=[(x,my(y)) for x,y in L["poly"]]
            self.nodes={nid:(x,my(y),z) for nid,(x,y,z) in self.nodes.items()}
        self.max_vol=max([L["vol"] for L in self.link_list]+[1])
        self.max_q=max([L["q"] for L in self.link_list]+[1])
        return log

def ramp(t):
    t=max(0.0,min(1.0,t))
    return QColor(int(510*t) if t<.5 else 255, 255 if t<.5 else int(255-(t-.5)*510), 60)

# ---------------- canvas ----------------
class Canvas(QWidget):
    def __init__(self, M, win):
        super().__init__(); self.M=M; self.win=win
        self.zoom=1.0; self.panx=0.0; self.pany=0.0; self.bbox=None; self.sel=None
        self.clock=420.0; self.setMouseTracking(False); self._drag=None
    def fit(self):
        pts=[p for L in self.M.link_list for p in L["poly"]]
        if not pts: return
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        self.bbox=(min(xs),min(ys),max(xs),max(ys)); self.zoom=1; self.panx=self.pany=0
        self.prepare_tiles(); self.update()
    # ---- OSM basemap (background image layer; tiles cached on disk) ----
    def prepare_tiles(self):
        self.tiles=[]
        if not (self.bbox and getattr(self.M,"geo",False) and self.win.ly_base.isChecked()): return
        x0,y0,x1,y1=self.bbox
        z=max(1,min(16,int(math.log2(360*5/max(x1-x0,1e-6)))))
        n=2**z
        tx0=int((x0+180)/360*n); tx1=int((x1+180)/360*n)
        ty0=int((1-y1/180)/2*n); ty1=int((1-y0/180)/2*n)
        cache=os.path.join(os.path.dirname(os.path.abspath(__file__)),"tile_cache")
        os.makedirs(cache,exist_ok=True)
        for tx in range(max(0,tx0-1),min(n-1,tx1+1)+1):
            for ty in range(max(0,ty0-1),min(n-1,ty1+1)+1):
                p=os.path.join(cache,f"{z}_{tx}_{ty}.png")
                if not os.path.exists(p):
                    try:
                        req=urllib.request.Request(
                            f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png",
                            headers={"User-Agent":"NeXTA-X/1.0 (research; ASU trans+AI lab)"})
                        open(p,"wb").write(urllib.request.urlopen(req,timeout=15).read())
                    except Exception: continue
                img=QImage(p)
                if img.isNull(): continue
                wx0=tx/n*360-180; wx1=(tx+1)/n*360-180
                wy1=180*(1-2*ty/n); wy0=180*(1-2*(ty+1)/n)      # mercator degrees, north = wy1
                self.tiles.append((img,(wx0,wy0,wx1,wy1)))
    def w2s(self):
        if not self.bbox: return None
        x0,y0,x1,y1=self.bbox; w=max(self.width(),1); h=max(self.height(),1)
        s=min(w/max(x1-x0,1e-9), h/max(y1-y0,1e-9))*0.94*self.zoom
        cx,cy=(x0+x1)/2,(y0+y1)/2
        return (s, w/2-cx*s+self.panx, h/2+cy*s+self.pany)   # y flipped
    def bin_of(self):
        b=0
        for i,t in enumerate(self.M.bins):
            if hhmm_to_min(t)<=self.clock: b=i
        return b
    def moe(self,L,binidx,mode):
        if mode=="volume": return L["vol"]/self.M.max_vol, 1+5*L["vol"]/self.M.max_vol
        if mode=="voc":    return min(1,L["voc"]), 1+4*min(1.4,L["voc"])
        if mode=="queue":  return L["q"]/self.M.max_q, 1+5*L["q"]/self.M.max_q
        d=self.M.td.get(L["id"],{}).get(binidx)
        inf,q=(d if d else (0,0))
        v=min(1.0, 0.55+0.45*min(1,q/60)) if q>0 else min(1.0, inf*4/max(L["cap"]*L["lanes"],1))
        return v, 1+4*min(1.0,inf/450)
    def paintEvent(self,ev):
        qp=QPainter(self); qp.fillRect(self.rect(),QColor(16,20,24))
        tr=self.w2s()
        if not tr: qp.end(); return
        s,tx,ty=tr; W=lambda x,y:QPointF(x*s+tx,-y*s+ty)
        ui=self.win
        if ui.ly_base.isChecked() and getattr(self,"tiles",None):
            for img,(wx0,wy0,wx1,wy1) in self.tiles:
                p0=W(wx0,wy1); p1=W(wx1,wy0)
                qp.drawImage(QRectF(p0.x(),p0.y(),p1.x()-p0.x(),p1.y()-p0.y()),img)
            qp.fillRect(self.rect(),QColor(10,14,18,105))   # dim so MOE colors read clearly
        mode=ui.moe.currentText(); binidx=self.bin_of()
        if ui.ly_links.isChecked():
            qp.setRenderHint(QPainter.Antialiasing, len(self.M.link_list)<8000)
            for L in self.M.link_list:
                v,w=self.moe(L,binidx,mode)
                col=QColor(77,184,255) if L is self.sel else ramp(v)
                qp.setPen(QPen(col,w))
                pts=[W(x,y) for x,y in L["poly"]]
                qp.drawPolyline(QPolygonF(pts))
        if ui.ly_paths.isChecked():
            for i,(vol,ids) in enumerate(self.M.paths[:20]):
                qp.setPen(QPen(QColor.fromHsv((i*47)%360,220,255,220),2.5))
                pts=[]
                for lid in ids:
                    L=self.M.links.get(lid)
                    if L and L["poly"]: pts+=[W(x,y) for x,y in L["poly"]]
                if pts: qp.drawPolyline(QPolygonF(pts))
        if ui.ly_nodes.isChecked():
            for nid,(x,y,z) in self.M.nodes.items():
                qp.fillRect(W(x,y).x()-(2.5 if z else 1.2),W(x,y).y()-(2.5 if z else 1.2),
                            5 if z else 2.4,5 if z else 2.4, QColor(255,210,87) if z else QColor(91,107,125))
        if ui.ly_veh.isChecked() and self.M.trajs:
            gr=QBrush(QColor(87,217,119)); rd=QBrush(QColor(255,95,95)); T=self.clock
            for ev in self.M.trajs.values():
                if not ev or T<ev[0][0] or T>ev[-1][0]: continue
                i=0
                while i+1<len(ev) and ev[i+1][0]<=T: i+=1
                t0,lid,buf,st=ev[i]
                L=self.M.links.get(lid)
                if not L or not L["poly"] or st=="completed": continue
                if buf=="ENB" and i+1<len(ev) and ev[i+1][1]==lid and ev[i+1][0]>t0:
                    f=(T-t0)/(ev[i+1][0]-t0); br=gr
                else: f=1.0; br=rd
                a=L["poly"][0]; b=L["poly"][-1]
                p=W(a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f)
                qp.setBrush(br); qp.setPen(Qt.NoPen); qp.drawEllipse(p,3,3)
        qp.setPen(QColor(77,184,255)); qp.drawText(12,self.height()-14, min_to_hhmm(self.clock))
        qp.end()
    # interaction
    def wheelEvent(self,e):
        self.zoom*=1.25 if e.angleDelta().y()>0 else 0.8
        if self.bbox:   # refetch tiles for the new scale (visible extent around center)
            x0,y0,x1,y1=self.bbox; cx,cy=(x0+x1)/2,(y0+y1)/2
            hw=(x1-x0)/2/self.zoom; hh=(y1-y0)/2/self.zoom
            keep=self.bbox; self.bbox=(cx-hw,cy-hh,cx+hw,cy+hh)
            self.prepare_tiles(); self.bbox=keep
        self.update()
    def mousePressEvent(self,e): self._drag=(e.position().x(),e.position().y(),False)
    def mouseMoveEvent(self,e):
        if not self._drag: return
        x,y,_=self._drag
        self.panx+=e.position().x()-x; self.pany+=e.position().y()-y
        self._drag=(e.position().x(),e.position().y(),True); self.update()
    def mouseReleaseEvent(self,e):
        if self._drag and not self._drag[2]: self.pick(e.position().x(),e.position().y())
        self._drag=None
    def pick(self,mx,my):
        tr=self.w2s()
        if not tr: return
        s,tx,ty=tr; best=None; bd=8.0
        for L in self.M.link_list:
            pts=[(x*s+tx,-y*s+ty) for x,y in L["poly"]]
            for i in range(len(pts)-1):
                ax,ay=pts[i]; bx,by=pts[i+1]
                dx,dy=bx-ax,by-ay; l2=dx*dx+dy*dy
                t=max(0,min(1,((mx-ax)*dx+(my-ay)*dy)/l2)) if l2 else 0
                d=((mx-ax-t*dx)**2+(my-ay-t*dy)**2)**0.5
                if d<bd: bd,best=d,L
        self.sel=best; self.win.show_inspector(best); self.update()

# ---------------- main window ----------------
class Win(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("NeXTA-X desktop (Qt) — AMS viewer")
        self.M=Model(); self.canvas=Canvas(self.M,self); self.setCentralWidget(self.canvas)
        self.resize(1280,780); self.folder=None; self.proc=None; self.sizes={}
        tb=QToolBar("MOE Toolbar"); self.addToolBar(tb)
        a=QAction("Open folder…",self); a.triggered.connect(self.open_dialog); tb.addAction(a)
        self.moe=QComboBox(); self.moe.addItems(["volume","voc","queue","td"])
        self.moe.currentIndexChanged.connect(lambda:self.canvas.update()); tb.addWidget(self.moe)
        self.play=QPushButton("▶ Play"); self.play.clicked.connect(self.toggle_play); tb.addWidget(self.play)
        self.slider=QSlider(Qt.Horizontal); self.slider.setFixedWidth(280)
        self.slider.valueChanged.connect(self.set_time); tb.addWidget(self.slider)
        self.speed=QComboBox(); self.speed.addItems(["2 min/s","10 min/s","30 min/s"])
        self.speed.setCurrentIndex(1); tb.addWidget(self.speed)
        b=QPushButton("Fit"); b.clicked.connect(self.canvas.fit); tb.addWidget(b)
        self.run_btn=QPushButton("Run engine"); self.run_btn.clicked.connect(self.run_engine); tb.addWidget(self.run_btn)
        self.live=QCheckBox("live-follow"); tb.addWidget(self.live)
        # Layer Control Panel
        dock=QDockWidget("Layer Control Panel",self); pnl=QWidget(); v=QVBoxLayout(pnl)
        self.ly_base=QCheckBox("background map (OSM)"); self.ly_base.setChecked(True)
        self.ly_base.stateChanged.connect(lambda *_:(self.canvas.prepare_tiles(),self.canvas.update()))
        v.addWidget(self.ly_base)
        self.ly_nodes=QCheckBox("nodes"); self.ly_links=QCheckBox("links"); self.ly_links.setChecked(True)
        self.ly_paths=QCheckBox("paths"); self.ly_veh=QCheckBox("vehicles"); self.ly_veh.setChecked(True)
        for c in (self.ly_nodes,self.ly_links,self.ly_paths,self.ly_veh):
            c.stateChanged.connect(lambda *_:self.canvas.update()); v.addWidget(c)
        v.addWidget(QLabel("<b>Summary Statistics</b>")); self.stats=QLabel("load a dataset…")
        self.stats.setWordWrap(True); v.addWidget(self.stats)
        v.addWidget(QLabel("<b>Inspector</b>")); self.insp=QLabel("click a link"); self.insp.setWordWrap(True)
        v.addWidget(self.insp); v.addStretch()
        dock.setWidget(pnl); self.addDockWidget(Qt.RightDockWidgetArea,dock)
        # engine log dock
        ld=QDockWidget("Engine log",self); self.logw=QTextEdit(); self.logw.setReadOnly(True)
        ld.setWidget(self.logw); self.addDockWidget(Qt.BottomDockWidgetArea,ld); ld.hide(); self.logdock=ld
        # timers
        self.anim=QTimer(self); self.anim.timeout.connect(self.tick)
        self.poll=QTimer(self); self.poll.timeout.connect(self.poll_folder); self.poll.start(5000)
    def open_dialog(self):
        d=QFileDialog.getExistingDirectory(self,"Open dataset folder")
        if d: self.open_folder(d)
    def open_folder(self,d):
        self.folder=d; log=self.M.load_folder(d)
        self.slider.setMinimum(self.M.tmin); self.slider.setMaximum(self.M.tmax)
        self.slider.setValue(self.M.tmin); self.canvas.clock=self.M.tmin
        self.canvas.fit(); self.refresh_stats()
        self.statusBar().showMessage(" · ".join(log))
    def refresh_stats(self):
        M=self.M; zones=sum(1 for _,_,z in M.nodes.values() if z)
        vmt=sum(L["vol"]*L["ln"] for L in M.link_list)
        top=sorted(M.link_list,key=lambda L:-L["q"])[:5]
        s=(f"nodes {len(M.nodes):,} / zones {zones}<br>links {len(M.link_list):,}"
           f"<br>VMT {vmt:,.0f} veh·mi<br>TD bins {len(M.bins)} · agents {len(M.trajs):,}"
           f"<br>clock {min_to_hhmm(M.tmin)}–{min_to_hhmm(M.tmax)}")
        if M.run:
            g=M.run.get("gridlock",{})
            s+=(f"<br><b>run</b>: {M.run.get('engine')} · {M.run.get('agents',0):,} agents · "
                f"{'conserved' if M.run.get('conserved') else '<span style=color:#f80>NOT conserved</span>'}"
                f"<br>oversaturated: {'YES' if g.get('oversaturated') else 'no'}"
                f" · first warning {g.get('first_warning','–')}")
        if top and top[0]["q"]>0:
            s+="<br><b>top queues</b>: "+", ".join(f"L{L['id']}({int(L['q'])})" for L in top)
        self.stats.setText(s)
    def show_inspector(self,L):
        if not L: self.insp.setText("click a link"); return
        d=self.M.td.get(L["id"],{}).get(self.canvas.bin_of())
        self.insp.setText(f"link <b>{L['id']}</b> ({L['f']}→{L['t']})<br>volume {L['vol']:,.0f} · "
            f"V/C {L['voc']:.2f} · max queue {int(L['q'])}<br>lanes {int(L['lanes'])} · cap {int(L['cap'])}"
            f" · len {L['ln']:.2f} mi" + (f"<br>bin now: inflow {int(d[0])}, queue {int(d[1])}" if d else ""))
    def set_time(self,v): self.canvas.clock=float(v); self.canvas.update()
    def toggle_play(self):
        if self.anim.isActive(): self.anim.stop(); self.play.setText("▶ Play")
        else: self.anim.start(100); self.play.setText("❚❚ Pause")
    def tick(self):
        rate={0:2,1:10,2:30}[self.speed.currentIndex()]/10.0
        c=self.canvas.clock+rate
        if c>self.M.tmax: c=self.M.tmin
        self.slider.setValue(int(c)); self.canvas.clock=c; self.canvas.update()
    def run_engine(self):
        if not self.folder: return
        here=os.path.dirname(os.path.abspath(__file__))
        cands=[os.path.join(here,"..","engine","bin","dlsim_run.exe"),          # consolidated repo layout
               os.path.join(here,"..","..","DLSim_STE","dlsim_run.exe")]        # legacy sibling layout
        exe=next((os.path.abspath(c) for c in cands if os.path.exists(c)), None)
        if not exe: self.statusBar().showMessage("dlsim_run.exe not found (engine/bin/)"); return
        self.logdock.show(); self.logw.clear(); self.live.setChecked(True)
        self.proc=QProcess(self); self.proc.setWorkingDirectory(os.path.dirname(exe))
        self.proc.readyReadStandardOutput.connect(
            lambda: self.logw.append(bytes(self.proc.readAllStandardOutput()).decode(errors="replace")))
        self.proc.finished.connect(lambda *_: (self.logw.append("— engine finished —"),
                                               self.open_folder(self.folder)))
        self.proc.start(exe,[self.folder,"--traj","2000"])
    def poll_folder(self):
        if not (self.live.isChecked() and self.folder): return
        changed=False
        for f in ("link_performance.csv","link_performance_15min.csv","agent_trajectory.csv"):
            p=os.path.join(self.folder,f)
            if os.path.exists(p):
                sz=os.path.getsize(p)
                if self.sizes.get(f)!=sz: self.sizes[f]=sz; changed=True
        if changed: self.open_folder(self.folder); self.statusBar().showMessage("live update")

def main():
    args=[a for a in sys.argv[1:]]
    snap=None; moe=None; t=None
    if "--snapshot" in args:
        i=args.index("--snapshot"); snap=args[i+1]; del args[i:i+2]
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    if "--moe" in args:
        i=args.index("--moe"); moe=args[i+1]; del args[i:i+2]
    if "--time" in args:
        i=args.index("--time"); t=args[i+1]; del args[i:i+2]
    app=QApplication(sys.argv[:1])
    w=Win()
    if args: w.open_folder(args[0])
    if moe: w.moe.setCurrentText(moe)
    if t: w.canvas.clock=hhmm_to_min(t)
    if snap:
        w.resize(1280,780); w.canvas.fit()
        img=w.grab().toImage()
        img.save(snap)
        # non-background pixel count for CI assertions
        n=sum(1 for y in range(0,img.height(),3) for x in range(0,img.width(),3)
              if QColor(img.pixel(x,y)).lightness()>40)
        print(f"snapshot {snap}: {img.width()}x{img.height()}, sampled_lit_px={n}")
        return 0
    w.show(); return app.exec()

if __name__=="__main__": sys.exit(main())

#!/usr/bin/env python3
"""ITS data-hub dashboard generator — reads the ITS I-95 sample and emits ONE self-contained HTML
showing every data source as a toggleable, time-animated layer over an embedded OSM/satellite basemap:

  network (GMNS links) · TMC speed (INRIX, per-link 15-min) · loop sensors (VDOT detectors) ·
  probe trips (trajectories on links) · GPS waypoints (breadcrumbs) · probe OD (desire lines)

Usage: python its_datahub.py <sample_dir> [-o its_datahub.html]
Demonstrates the "dataset-first, connect-from-DataHub" idea: many ITS sources, one GMNS base, layers.
"""
import base64, csv, json, math, os, re, sys, urllib.request
csv.field_size_limit(1 << 24)

def fnum(v):
    try: return float(v)
    except: return 0.0
def hhmm2min(s):
    m = re.match(r"(\d+):(\d+)", s or ""); return int(m[1])*60+int(m[2]) if m else 0

def load(d):
    D = {"links": [], "tmc": {}, "sensors": [], "sensor_ts": {}, "trips": [], "wp": [], "od": [], "bins": set()}
    # network links (WKT geometry)
    for r in csv.DictReader(open(d+"/network/link.csv", encoding="utf-8-sig")):
        pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
        if len(pts) >= 2:
            D["links"].append([r["link_id"], [[round(float(x), 6), round(float(y), 6)] for x, y in pts]])
    lgeo = {L[0]: L[1] for L in D["links"]}
    # TMC speed per link per bin
    for r in csv.DictReader(open(d+"/tmc_speed_15min.csv", encoding="utf-8-sig")):
        b = r["time"]; D["bins"].add(b)
        D["tmc"].setdefault(r["link_id"], {})[b] = round(fnum(r["speed"]), 1)
    # sensors (points) + time series
    for r in csv.DictReader(open(d+"/sensor_points.csv", encoding="utf-8-sig")):
        D["sensors"].append([r["zone_id"], round(fnum(r["longitude"]), 6), round(fnum(r["latitude"]), 6),
                             r.get("road", ""), r.get("direction", "")])
    for r in csv.DictReader(open(d+"/sensor_15min.csv", encoding="utf-8-sig")):
        b = r["time"]; D["bins"].add(b)
        D["sensor_ts"].setdefault(r["zone_id"], {})[b] = [round(fnum(r["speed"]), 0), round(fnum(r["volume"]), 0),
                                                           round(fnum(r["occupancy"]), 1)]
    # probe trips: link geometry sequence + active time window (UTC -> EDT local minute of day)
    def utcmin(s):
        m = re.search(r"T(\d{2}):(\d{2})", s or "")
        return ((int(m[1])*60+int(m[2])) - 240) % 1440 if m else 0
    for r in csv.DictReader(open(d+"/trips.csv", encoding="utf-8-sig")):
        lids = [x for x in (r.get("link_ids") or "").split(";") if x in lgeo]
        if len(lids) >= 2:
            D["trips"].append([lids, utcmin(r.get("t_start")), utcmin(r.get("t_end"))])
    # GPS waypoints (unix -> EDT local minute of day)
    for r in csv.DictReader(open(d+"/waypoints.csv", encoding="utf-8-sig")):
        t = fnum(r.get("t_unix"))
        D["wp"].append([round(fnum(r["longitude"]), 6), round(fnum(r["latitude"]), 6),
                        round(fnum(r.get("speed_mph")), 0), int(((t-14400) % 86400)//60)])
    # OD desire lines with coords
    for r in csv.DictReader(open(d+"/od.csv", encoding="utf-8-sig")):
        if r.get("o_lon") and r.get("d_lon"):
            D["od"].append([fnum(r["o_lon"]), fnum(r["o_lat"]), fnum(r["d_lon"]), fnum(r["d_lat"]), fnum(r["volume"])])
    D["bins"] = sorted(D["bins"], key=hhmm2min)
    return D

def tiles(D, src, z, cap):
    xs = [p[0] for L in D["links"] for p in L[1]]; ys = [p[1] for L in D["links"] for p in L[1]]
    my = lambda lat: math.degrees(math.log(math.tan(math.radians(45+lat/2))))
    x0, x1, y0, y1 = min(xs), max(xs), my(min(ys)), my(max(ys))
    n = 2**z
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "github_dev",
                         "desktop-qt", "tile_cache")
    os.makedirs(cache, exist_ok=True)
    txr = range(max(0, int((x0+180)/360*n)-1), min(n-1, int((x1+180)/360*n)+1)+1)
    tyr = range(max(0, int((1-y1/180)/2*n)-1), min(n-1, int((1-y0/180)/2*n)+1)+1)
    if len(txr)*len(tyr) > cap: return []
    out = []
    for tx in txr:
        for ty in tyr:
            ext = "png" if src == "osm" else "jpg"
            p = os.path.join(cache, f"{src}_{z}_{tx}_{ty}.{ext}")
            if not os.path.exists(p):
                url = (f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png" if src == "osm" else
                       f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{ty}/{tx}")
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "gui4gmns/1.0 (research)"})
                    open(p, "wb").write(urllib.request.urlopen(req, timeout=15).read())
                except Exception: continue
            mime = "png" if p.endswith("png") else "jpeg"
            out.append(["data:image/"+mime+";base64,"+base64.b64encode(open(p, "rb").read()).decode(),
                        tx/n*360-180, (tx+1)/n*360-180, 180*(1-2*(ty+1)/n), 180*(1-2*ty/n)])
    return out

TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>ITS I-95 (VA) data hub — gui4gmns</title>
<style>
body{margin:0;background:#14181d;color:#d8dee6;font:13px system-ui}
#bar{display:flex;gap:12px;align-items:center;padding:8px 14px;background:#1d232b;border-bottom:1px solid #2c3540;flex-wrap:wrap}
#bar b{color:#4db8ff;font-size:15px}
.ly{padding:2px 8px;border:1px solid #2c3540;border-radius:4px;cursor:pointer;user-select:none}
.ly input{accent-color:#4db8ff;margin-right:4px}
button,select{background:#28303a;color:#d8dee6;border:1px solid #2c3540;border-radius:4px;padding:4px 9px;cursor:pointer}
#wrap{position:relative}#cv{display:block;width:100vw;height:calc(100vh - 96px);cursor:grab}
#clock{font-size:20px;font-weight:700;color:#4db8ff}
#hud{position:absolute;left:12px;bottom:12px;background:rgba(20,26,32,.9);padding:6px 12px;border-radius:6px;border:1px solid #2c3540;font-size:12px}
#legend{position:absolute;right:12px;bottom:12px;background:rgba(20,26,32,.9);padding:8px 10px;border-radius:6px;border:1px solid #2c3540;font-size:11px;line-height:1.6}
input[type=range]{width:240px;accent-color:#4db8ff}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin-right:3px}
</style></head><body>
<div id="bar"><b>ITS I-95 · VA</b><span style="color:#8a94a3">data-hub layers · __DATE__</span>
<label class="ly"><input type="checkbox" id="L_net" checked>network</label>
<label class="ly"><input type="checkbox" id="L_tmc" checked>TMC speed</label>
<label class="ly"><input type="checkbox" id="L_sensor" checked>loop sensors</label>
<label class="ly"><input type="checkbox" id="L_trip">probe trips</label>
<label class="ly"><input type="checkbox" id="L_wp" checked>GPS waypoints</label>
<label class="ly"><input type="checkbox" id="L_od">probe OD</label>
<label class="ly"><input type="checkbox" id="L_base" checked>basemap</label>
<button id="play" onclick="tog()">▶ Play</button><input type="range" id="ts" min="0" max="1439" value="420" oninput="clock=+this.value">
<button onclick="fit()">Fit</button></div>
<div id="wrap"><canvas id="cv"></canvas>
  <div id="hud"><span id="clock">--:--</span> &nbsp;<span id="hud2" style="color:#8a94a3"></span></div>
  <div id="legend"></div></div>
<script>
const DATA=__DATA__;
const my=lat=>180/Math.PI*Math.log(Math.tan(Math.PI/4+lat*Math.PI/360));
const M=DATA; M.links.forEach(L=>L.geo=L[1].map(p=>[p[0],my(p[1])]));
const WP=M.wp.map(w=>[w[0],my(w[1]),w[2],w[3]]);
const OD=M.od.map(o=>[o[0],my(o[1]),o[2],my(o[3]),o[4]]);
const SEN=M.sensors.map(s=>[s[0],s[1],my(s[2]),s[3],s[4]]);
const lgeo={}; M.links.forEach(L=>lgeo[L[0]]=L.geo);
let bbox=null,zoom=1,px=0,py=0,clock=420,playing=false;
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const oxTiles=(DATA.tiles||[]).map(t=>{const i=new Image();i.src=t[0];return[i,t[1],t[2],t[3],t[4]];});
const satTiles=(DATA.tiles_sat||[]).map(t=>{const i=new Image();i.src=t[0];return[i,t[1],t[2],t[3],t[4]];});
function fit(){let a=[1e9,1e9,-1e9,-1e9];M.links.forEach(L=>L.geo.forEach(p=>{a[0]=Math.min(a[0],p[0]);a[1]=Math.min(a[1],p[1]);a[2]=Math.max(a[2],p[0]);a[3]=Math.max(a[3],p[1]);}));bbox=a;zoom=1;px=py=0;}
function vt(){const w=cv.width,h=cv.height,ar=w/h,span=Math.max(bbox[2]-bbox[0],(bbox[3]-bbox[1])*ar)||1;
 const s=w/span*0.92*zoom,cx=(bbox[0]+bbox[2])/2,cy=(bbox[1]+bbox[3])/2;return{s,tx:w/2-cx*s+px,ty:h/2+cy*s+py};}
const spd=(v,ff)=>{const r=Math.max(0,Math.min(1,1-v/(ff||65)));return`rgb(${(r<.5?510*r:255)|0},${(r<.5?255:255-(r-.5)*510)|0},60)`;};
function curBin(){const bs=M.bins;if(!bs.length)return null;let best=bs[0];for(const b of bs){if((+b.slice(0,2)*60+ +b.slice(3,5))<=clock)best=b;}return best;}
function draw(){cv.width=cv.clientWidth;cv.height=cv.clientHeight;if(!bbox)return;const T=vt();const W=(x,y)=>[x*T.s+T.tx,-y*T.s+T.ty];
 ctx.fillStyle='#101418';ctx.fillRect(0,0,cv.width,cv.height);
 if(document.getElementById('L_base').checked){const set=(zoom>=2.2&&satTiles.length)?satTiles:oxTiles;
  try{ctx.filter='saturate(45%)';}catch(e){}
  set.forEach(([im,x0,x1,y0,y1])=>{if(!im.complete||!im.naturalWidth)return;const a=W(x0,y1),b=W(x1,y0);ctx.drawImage(im,a[0],a[1],b[0]-a[0],b[1]-a[1]);});
  try{ctx.filter='none';}catch(e){}ctx.fillStyle='rgba(16,20,24,0.5)';ctx.fillRect(0,0,cv.width,cv.height);}
 const b=curBin();
 // network base
 if(document.getElementById('L_net').checked){ctx.strokeStyle='#3a4551';ctx.lineWidth=1.2;
  M.links.forEach(L=>{ctx.beginPath();L.geo.forEach((p,i)=>{const s=W(p[0],p[1]);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();});}
 // TMC speed (colored links)
 if(document.getElementById('L_tmc').checked&&b){ctx.lineWidth=4;
  for(const lid in M.tmc){const v=M.tmc[lid][b];const g=lgeo[lid];if(v==null||!g)continue;
   ctx.strokeStyle=spd(v,70);ctx.beginPath();g.forEach((p,i)=>{const s=W(p[0],p[1]);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();}}
 // probe trips (paths)
 if(document.getElementById('L_trip').checked){ctx.lineWidth=1.5;let n=0;
  M.trips.forEach(t=>{const lo=t[1],hi=t[2];const on=(lo<=hi)?(clock>=lo&&clock<=hi):(clock>=lo||clock<=hi);if(!on)return;n++;
   ctx.strokeStyle=`hsla(${(n*53)%360},85%,62%,.8)`;ctx.beginPath();let st=false;
   t[0].forEach(lid=>{const g=lgeo[lid];if(!g)return;g.forEach(p=>{const s=W(p[0],p[1]);st?ctx.lineTo(s[0],s[1]):(ctx.moveTo(s[0],s[1]),st=true);});});ctx.stroke();});}
 // OD desire lines
 if(document.getElementById('L_od').checked){const mx=Math.max(1,...OD.map(o=>o[4]));
  OD.forEach(o=>{const a=W(o[0],o[1]),c=W(o[2],o[3]),v=o[4]/mx;ctx.strokeStyle=`rgba(255,${(180-120*v)|0},80,${0.2+0.5*v})`;ctx.lineWidth=0.4+3*v;
   ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(c[0],c[1]);ctx.stroke();});}
 // GPS waypoints (breadcrumbs near current time)
 if(document.getElementById('L_wp').checked){let n=0;WP.forEach(w=>{if(Math.abs(((w[3]-clock+720)%1440)-720)>20)return;n++;
   const s=W(w[0],w[1]);const r=Math.max(0,Math.min(1,1-w[2]/65));ctx.fillStyle=`rgba(${(r<.5?510*r:255)|0},${(r<.5?255:255-(r-.5)*510)|0},80,.85)`;
   ctx.beginPath();ctx.arc(s[0],s[1],2.2,0,6.29);ctx.fill();});document.getElementById('hud2').textContent=n+' live GPS pts';}
 // loop sensors (points)
 if(document.getElementById('L_sensor').checked){SEN.forEach(sn=>{const ts=(M.sensor_ts[sn[0]]||{})[b];const s=W(sn[1],sn[2]);
   const vol=ts?ts[1]:0,sp=ts?ts[0]:0;ctx.fillStyle=ts?spd(sp,65):'#5b6b7d';ctx.strokeStyle='#fff';ctx.lineWidth=1;
   const rr=4+Math.min(9,vol/40);ctx.beginPath();ctx.arc(s[0],s[1],rr,0,6.29);ctx.fill();ctx.stroke();});}
 document.getElementById('clock').textContent=`${String(clock/60|0).padStart(2,'0')}:${String(clock%60|0).padStart(2,'0')}`;
 if(playing){clock=(clock+2)%1440;document.getElementById('ts').value=clock;}
 requestAnimationFrame(draw);}
function tog(){playing=!playing;document.getElementById('play').textContent=playing?'❚❚':'▶ Play';}
cv.addEventListener('wheel',e=>{e.preventDefault();zoom*=e.deltaY<0?1.25:.8;},{passive:false});
let dr=null;cv.addEventListener('mousedown',e=>dr=[e.offsetX,e.offsetY]);
cv.addEventListener('mousemove',e=>{if(!dr)return;px+=e.offsetX-dr[0];py+=e.offsetY-dr[1];dr=[e.offsetX,e.offsetY];});
window.addEventListener('mouseup',()=>dr=null);
document.getElementById('legend').innerHTML=
 `<b>ITS data hub</b> — ${M.links.length} links · ${M.sensors.length} sensors · ${M.trips.length} trips · ${WP.length} GPS pts · ${OD.length} OD<br>`+
 `<span class="sw" style="background:#3a4551"></span>network `+
 `<span class="sw" style="background:linear-gradient(90deg,#3f5,#fd3,#f33)"></span>speed (green free→red slow)<br>`+
 `<span class="sw" style="background:#fff;border-radius:50%"></span>loop sensor (size=volume) · `+
 `<span class="sw" style="background:hsl(200,85%,62%)"></span>probe trip · `+
 `<span class="sw" style="background:#f80"></span>OD desire`;
fit();requestAnimationFrame(draw);
</script></body></html>"""

def main():
    d = sys.argv[1]
    out = sys.argv[sys.argv.index("-o")+1] if "-o" in sys.argv else d+"/its_datahub.html"
    D = load(d)
    print(f"loaded: {len(D['links'])} links, {len(D['sensors'])} sensors, {len(D['trips'])} trips, "
          f"{len(D['wp'])} waypoints, {len(D['od'])} OD, {len(D['bins'])} time bins")
    xs = [p[0] for L in D["links"] for p in L[1]]
    span = max(xs)-min(xs)
    z = max(1, min(15, int(math.log2(360*5/max(span, 1e-6)))))
    D["tiles"] = tiles(D, "osm", z, 60)
    D["tiles_sat"] = tiles(D, "satellite", z+1, 130)
    print(f"basemap: {len(D['tiles'])} OSM z{z} + {len(D['tiles_sat'])} satellite z{z+1}")
    import datetime
    html = TEMPLATE.replace("__DATE__", str(datetime.date.today())).replace("__DATA__", json.dumps(D, separators=(",", ":")))
    open(out, "w", encoding="utf-8").write(html)
    print(f"generated {out} ({os.path.getsize(out)/1e6:.2f} MB)")

if __name__ == "__main__":
    main()

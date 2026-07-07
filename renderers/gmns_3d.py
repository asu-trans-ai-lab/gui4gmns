#!/usr/bin/env python3
"""GMNS 3D overlay — the analytical layer that sits ABOVE a 3D city base (OpenCities KMZ/Collada, etc.).

Encodes the gui4gmns 3D visual grammar on the GMNS network:
  volume -> extrusion HEIGHT   ·   speed -> COLOR (green fast -> red slow)   ·   V/C -> warning tint
Writes data.json (deck.gl extruded ribbons) + a self-contained deck.gl page (OSM basemap, pitched 3D).
The 3D city buildings/terrain come from the user's OpenCities export; this is the traffic overlay only.

    python gmns_3d.py <gmns_folder> "<label>" -o docs/portal_demo/gmns3d [--source "..."] [--zoom 13]
"""
import os, sys, json, math, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gmns_to_viz", os.path.join(HERE, "..", "exporters", "gmns_to_viz.py"))
gv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gv)

RAMP = [(47, 158, 94), (245, 206, 52), (230, 84, 30), (166, 13, 10)]  # green(fast) -> red(slow)
def ramp(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    s = t * 3; i = min(2, int(s)); f = s - i; a, b = RAMP[i], RAMP[i + 1]
    return [round(a[k] + (b[k] - a[k]) * f) for k in range(3)]

def pct(v, q):
    s = sorted(v); return s[max(0, min(len(s) - 1, int(q * (len(s) - 1))))] if s else 0

def ribbon(pts, w, coslat):
    """Buffer a centerline into a thin polygon ring (width w in degrees, lon corrected by 1/cos(lat))."""
    n = len(pts); left = []; right = []
    for i in range(n):
        if i == 0: dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif i == n - 1: dx, dy = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        else: dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        d = math.hypot(dx, dy) or 1e-9
        px, py = -dy / d, dx / d                          # perpendicular unit
        left.append([pts[i][0] + px * w / coslat, pts[i][1] + py * w])
        right.append([pts[i][0] - px * w / coslat, pts[i][1] - py * w])
    return left + right[::-1]

def main():
    a = sys.argv[1:]
    src = a[0]; label = a[1] if len(a) > 1 and not a[1].startswith("-") else os.path.basename(src)
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(src, "gmns3d")
    zoom = float(a[a.index("--zoom") + 1]) if "--zoom" in a else 13.0
    source = a[a.index("--source") + 1] if "--source" in a else ""
    os.makedirs(out, exist_ok=True)
    D = gv.read_gmns(src, max_traj=0)
    links = [L for L in D["links"] if len(L["poly"]) >= 2]
    vmax = max((L["vol"] for L in links), default=0) or 1
    sp = [L["speed"] for L in links if L["speed"] > 0]
    slo, shi = (pct(sp, 0.05), pct(sp, 0.95)) if sp else (0, 1); srng = (shi - slo) or 1
    lat0 = sum(p[1] for L in links for p in L["poly"]) / max(1, sum(len(L["poly"]) for L in links))
    lon0 = sum(p[0] for L in links for p in L["poly"]) / max(1, sum(len(L["poly"]) for L in links))
    coslat = max(0.2, math.cos(math.radians(lat0)))
    feats = []
    for L in links:
        h = (L["vol"] / vmax) * 320 + 3                    # volume -> height (m), min 3
        t = 1 - (L["speed"] - slo) / srng if L["speed"] > 0 else 0.5  # fast -> green
        c = ramp(t)
        feats.append({"polygon": [[round(x, 6), round(y, 6)] for x, y in ribbon(L["poly"], 0.00009, coslat)],
                      "height": round(h, 1), "color": c,
                      "vol": round(L["vol"]), "speed": round(L["speed"], 1), "voc": round(L["voc"], 2)})
    json.dump(feats, open(os.path.join(out, "data.json"), "w"))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(HTML
        .replace("__LON__", f"{lon0:.5f}").replace("__LAT__", f"{lat0:.5f}")
        .replace("__ZOOM__", str(zoom)).replace("__LABEL__", label).replace("__SRC__", source or "GMNS"))
    if source:
        open(os.path.join(out, "SOURCE.txt"), "w", encoding="utf-8").write(source + "\n")
    print(f"gmns 3d -> {out}/  ({len(feats)} extruded links, volume<= {vmax:.0f}, speed {slo:.0f}-{shi:.0f})")

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>GMNS 3D — __LABEL__</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
<style>
 html,body,#map{margin:0;height:100%;width:100%;background:#0e1116;overflow:hidden}
 body{font:13px system-ui,Segoe UI,Arial;color:#e6edf3}
 .p{position:absolute;z-index:5;background:rgba(20,25,31,.9);border:1px solid #2b333d;border-radius:8px;padding:9px 12px}
 #hdr{top:12px;left:12px;max-width:340px} #hdr b span{color:#58a6ff} #hdr .s{color:#9aa7bd;font-size:11.5px;margin-top:3px}
 #leg{bottom:16px;left:12px;font-size:12px} #leg .bar{height:9px;width:150px;border-radius:2px;margin:5px 0 3px;
   background:linear-gradient(90deg,rgb(166,13,10),rgb(230,84,30),rgb(245,206,52),rgb(47,158,94))}
 #leg .e{display:flex;justify-content:space-between;color:#9aa7bd;font-size:11px}
 #src{bottom:16px;right:12px;color:#9aa7bd;font-size:11.5px}
 #tip{position:absolute;z-index:6;pointer-events:none;background:rgba(0,0,0,.8);padding:4px 7px;border-radius:4px;font-size:12px;display:none}
</style></head><body>
<div id="map"></div>
<div class="p" id="hdr"><b><span>gui4gmns</span> · GMNS 3D — __LABEL__</b>
  <div class="s">Traffic overlay on the network: <b>height = volume</b>, <b>color = speed</b> (green fast → red slow).
  Drag to orbit. Composite this over a 3D city base (OpenCities KMZ/Collada) for the full scene.</div></div>
<div class="p" id="leg">speed (green fast → red slow)<div class="bar"></div><div class="e"><span>slow / queue</span><span>free-flow</span></div></div>
<div class="p" id="src">Source: __SRC__ · basemap © OpenStreetMap</div>
<div id="tip"></div>
<script>
const {DeckGL,PolygonLayer,TileLayer,BitmapLayer}=deck;
const osm=new TileLayer({data:'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',minZoom:0,maxZoom:19,tileSize:256,
  renderSubLayers:p=>{const{west,south,east,north}=p.tile.bbox;return new BitmapLayer(p,{data:null,image:p.data,bounds:[west,south,east,north]});}});
fetch('data.json').then(r=>r.json()).then(data=>{
  const net=new PolygonLayer({id:'net',data,extruded:true,wireframe:false,pickable:true,
    getPolygon:d=>d.polygon,getElevation:d=>d.height,getFillColor:d=>d.color,opacity:0.92,
    material:{ambient:0.6,diffuse:0.6,shininess:20}});
  const deckgl=new DeckGL({container:'map',
    initialViewState:{longitude:__LON__,latitude:__LAT__,zoom:__ZOOM__,pitch:52,bearing:18},
    controller:true,layers:[osm,net],
    getTooltip:({object})=>object&&{html:`link · vol <b>${object.vol}</b> · speed <b>${object.speed}</b> mph · V/C ${object.voc}`,
      style:{background:'rgba(0,0,0,.8)',color:'#fff',fontSize:'12px'}}});
});
</script></body></html>"""

if __name__ == "__main__":
    main()

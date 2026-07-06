#!/usr/bin/env python3
"""GUI-X exporters — GMNS run folder OUT to best-in-class external visualization tools.

gui4gmns isn't only its own viewer; it feeds the tools users already love, so they add their own
layers, styling, and 3D. Each target is an independent pipeline:

  kepler   -> GeoJSON network + Trip GeoJSON (4th coord = timestamp) + OD-arc CSV + a kepler.gl config
  deckgl   -> data.json (PathLayer/TripsLayer/ArcLayer) + a minimal standalone deck.gl page
  qgis     -> GeoJSON layers + .qml graduated styles + a PyQGIS load_layers.py (automation)
  kml      -> Google Earth KML: volume-extruded 3D link bars + time-stamped trajectory tour (fly)

Usage: python gmns_to_viz.py <gmns_folder> [-o out_dir] [--target kepler|deckgl|qgis|kml|all]
Pure-Python stdlib. Reads node.csv, link.csv (+link_performance.csv), agent_trajectory.csv, demand.csv.
"""
import csv, json, math, os, re, sys
csv.field_size_limit(1 << 24)

def fnum(v):
    try: return float(v)
    except: return 0.0

# ---------------- GMNS read ----------------
def read_gmns(d, max_traj=500):
    nodes, links = {}, []
    zpts = {}
    nf = os.path.join(d, "node.csv")
    if os.path.exists(nf):
        for r in csv.DictReader(open(nf, encoding="utf-8-sig")):
            i = int(fnum(r["node_id"])); nodes[i] = (fnum(r["x_coord"]), fnum(r["y_coord"]))
            z = (r.get("zone_id") or "").strip()
            if z: zpts.setdefault(z, []).append((fnum(r["x_coord"]), fnum(r["y_coord"])))
    perf = {}
    pf = os.path.join(d, "link_performance.csv")
    if os.path.exists(pf):
        for r in csv.DictReader(open(pf, encoding="utf-8-sig")): perf[r.get("link_id")] = r
    volcol = None
    if perf:
        any_r = next(iter(perf.values()))
        volcol = "cum_departure" if "cum_departure" in any_r else "volume"
    for r in csv.DictReader(open(os.path.join(d, "link.csv"), encoding="utf-8-sig")):
        lid = str(int(fnum(r["link_id"]))); poly = None
        pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
        if len(pts) >= 2: poly = [(float(x), float(y)) for x, y in pts]
        if not poly:
            a = nodes.get(int(fnum(r["from_node_id"]))); b = nodes.get(int(fnum(r["to_node_id"])))
            if a and b: poly = [a, b]
        if not poly: continue
        p = perf.get(lid) or perf.get(r["link_id"]) or {}
        vol = fnum(p.get(volcol)) if p else 0.0
        cap = fnum(r.get("capacity") or 1800); lanes = max(1, fnum(r.get("lanes") or 1))
        links.append({"id": lid, "poly": poly, "vol": vol, "cap": cap, "lanes": lanes,
                      "speed": fnum(p.get("speed")) if p else fnum(r.get("free_speed")),
                      "voc": vol / (cap * lanes * 8) if cap * lanes else 0,
                      "ff": fnum(r.get("free_speed") or 60)})
    # trajectories -> ordered link paths per agent
    trips = []
    tf = os.path.join(d, "agent_trajectory.csv")
    lgeo = {L["id"]: L["poly"] for L in links}
    if os.path.exists(tf):
        by = {}
        for r in csv.DictReader(open(tf, encoding="utf-8-sig")):
            a = int(fnum(r["agent_id"]))
            if a >= max_traj: continue
            by.setdefault(a, []).append((fnum(r["time_min"]), str(int(fnum(r["link_id"]))), r.get("buffer")))
        for a, ev in by.items():
            ev.sort(); pts = []
            for t, lid, buf in ev:
                g = lgeo.get(lid)
                if g: pts.append((g[0][0], g[0][1], t))       # link entry point + time
            if len(pts) >= 2: trips.append(pts)
    # OD desire lines from demand + zone centroids
    od = []
    zc = {z: (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)) for z, ps in zpts.items()}
    df = os.path.join(d, "demand.csv")
    if os.path.exists(df) and zc:
        agg = {}
        for r in csv.DictReader(open(df, encoding="utf-8-sig")):
            o = (r.get("o_zone_id") or "").strip(); dd = (r.get("d_zone_id") or "").strip(); v = fnum(r.get("volume"))
            if v > 0 and o in zc and dd in zc and o != dd: agg[(o, dd)] = agg.get((o, dd), 0) + v
        for (o, dd), v in sorted(agg.items(), key=lambda kv: -kv[1])[:300]:
            od.append((zc[o][0], zc[o][1], zc[dd][0], zc[dd][1], v))
    geo = links and -181 < links[0]["poly"][0][0] < 181 and -85 < links[0]["poly"][0][1] < 85
    return {"links": links, "trips": trips, "od": od, "geo": geo}

def ramp_rgb(t):   # 0..1 green->yellow->red
    t = max(0.0, min(1.0, t))
    return (int(510 * t) if t < .5 else 255, 255 if t < .5 else int(255 - (t - .5) * 510), 60)

# ---------------- kepler.gl ----------------
def export_kepler(D, out):
    os.makedirs(out, exist_ok=True)
    mv = max([L["vol"] for L in D["links"]] + [1])
    net = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"link_id": L["id"], "volume": round(L["vol"], 1),
         "voc": round(L["voc"], 3), "capacity": L["cap"], "lanes": L["lanes"], "speed": round(L["speed"], 1)},
         "geometry": {"type": "LineString", "coordinates": [[x, y] for x, y in L["poly"]]}}
        for L in D["links"]]}
    json.dump(net, open(os.path.join(out, "network.geojson"), "w"))
    # Trip GeoJSON: coordinates carry a 4th element = timestamp (kepler Trip layer format)
    trips = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"trip": i},
         "geometry": {"type": "LineString", "coordinates": [[x, y, 0, int(t * 60)] for x, y, t in tr]}}
        for i, tr in enumerate(D["trips"])]}
    json.dump(trips, open(os.path.join(out, "trips.geojson"), "w"))
    with open(os.path.join(out, "od_arcs.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["o_lon", "o_lat", "d_lon", "d_lat", "volume"])
        for o in D["od"]: w.writerow([round(o[0], 6), round(o[1], 6), round(o[2], 6), round(o[3], 6), round(o[4], 0)])
    cfg = {"version": "v1", "config": {"visState": {"layers": [
        {"type": "geojson", "config": {"dataId": "network", "label": "network (volume)",
         "colorField": {"name": "volume", "type": "real"}, "visConfig": {"opacity": 0.8, "thickness": 2}}},
        {"type": "trip", "config": {"dataId": "trips", "label": "trajectories"}},
        {"type": "arc", "config": {"dataId": "od_arcs", "label": "OD",
         "columns": {"lat0": "o_lat", "lng0": "o_lon", "lat1": "d_lat", "lng1": "d_lon"}}}]}}}
    json.dump(cfg, open(os.path.join(out, "kepler_config.json"), "w"), indent=1)
    open(os.path.join(out, "README.txt"), "w").write(
        "kepler.gl export. Go to https://kepler.gl/demo, drag in network.geojson, trips.geojson, "
        "od_arcs.csv; load kepler_config.json (Share > Add config) for styled layers. Add your own layers freely.")
    return ["network.geojson", "trips.geojson", "od_arcs.csv", "kepler_config.json"]

# ---------------- deck.gl ----------------
def export_deckgl(D, out):
    os.makedirs(out, exist_ok=True)
    mv = max([L["vol"] for L in D["links"]] + [1])
    data = {
        "paths": [{"path": [[x, y] for x, y in L["poly"]], "color": list(ramp_rgb(L["vol"] / mv)),
                   "width": 1 + 5 * L["vol"] / mv, "volume": round(L["vol"], 1)} for L in D["links"]],
        "trips": [{"path": [[x, y] for x, y, t in tr], "timestamps": [int(t * 60) for _, _, t in tr]} for tr in D["trips"]],
        "arcs": [{"source": [o[0], o[1]], "target": [o[2], o[3]], "volume": round(o[4], 0)} for o in D["od"]],
    }
    json.dump(data, open(os.path.join(out, "data.json"), "w"))
    ctr = D["links"][len(D["links"]) // 2]["poly"][0] if D["links"] else [0, 0]
    html = DECKGL_HTML.replace("__LON__", str(round(ctr[0], 5))).replace("__LAT__", str(round(ctr[1], 5)))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    return ["data.json", "index.html"]

DECKGL_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>deck.gl — gui4gmns export</title>
<script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
<style>body{margin:0}#c{position:absolute;inset:0}</style></head><body><div id="c"></div>
<script>
// NOTE: this standalone deck.gl page loads deck.gl from a CDN (needs internet) — it is an EXPORT to an
// external tool, not the self-contained gui4gmns dashboard. Add/remove layers below freely.
fetch('data.json').then(r=>r.json()).then(D=>{
 const {DeckGL,PathLayer,TripsLayer,ArcLayer}=deck;
 let t=0;const T=Math.max(1,...D.trips.flatMap(x=>x.timestamps.length?[x.timestamps[x.timestamps.length-1]]:[0]));
 const deckgl=new DeckGL({container:'c',mapStyle:null,
  initialViewState:{longitude:__LON__,latitude:__LAT__,zoom:11,pitch:45,bearing:0},controller:true,
  layers:[]});
 function render(){t=(t+30)%T;deckgl.setProps({layers:[
   new PathLayer({id:'net',data:D.paths,getPath:d=>d.path,getColor:d=>d.color,getWidth:d=>d.width,widthMinPixels:1}),
   new ArcLayer({id:'od',data:D.arcs,getSourcePosition:d=>d.source,getTargetPosition:d=>d.target,
     getSourceColor:[80,160,255],getTargetColor:[255,140,80],getWidth:1}),
   new TripsLayer({id:'trips',data:D.trips,getPath:d=>d.path,getTimestamps:d=>d.timestamps,
     getColor:[87,217,140],opacity:0.9,widthMinPixels:2,trailLength:180,currentTime:t})]});
   requestAnimationFrame(render);}
 render();});
</script></body></html>"""

# ---------------- QGIS ----------------
def export_qgis(D, out):
    os.makedirs(out, exist_ok=True)
    net = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"link_id": L["id"], "volume": round(L["vol"], 1),
         "voc": round(L["voc"], 3), "capacity": L["cap"], "lanes": L["lanes"]},
         "geometry": {"type": "LineString", "coordinates": [[x, y] for x, y in L["poly"]]}}
        for L in D["links"]]}
    json.dump(net, open(os.path.join(out, "network.geojson"), "w"))
    if D["od"]:
        odg = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"volume": round(o[4], 0)},
             "geometry": {"type": "LineString", "coordinates": [[o[0], o[1]], [o[2], o[3]]]}} for o in D["od"]]}
        json.dump(odg, open(os.path.join(out, "od.geojson"), "w"))
    # graduated .qml style (volume): 5 classes green->red
    mv = max([L["vol"] for L in D["links"]] + [1])
    brks = [mv * k / 5 for k in range(1, 6)]
    ranges = "".join(
        f'<range lower="{(brks[i-1] if i else 0):.3f}" upper="{brks[i]:.3f}" symbol="{i}" '
        f'label="{(brks[i-1] if i else 0):.0f}-{brks[i]:.0f}"/>' for i in range(5))
    syms = "".join(
        f'<symbol type="line" name="{i}"><layer class="SimpleLine">'
        f'<Option value="{ramp_rgb(i/4)[0]},{ramp_rgb(i/4)[1]},{ramp_rgb(i/4)[2]},255" name="line_color" type="QString"/>'
        f'<Option value="{0.4+i*0.5}" name="line_width" type="QString"/></layer></symbol>' for i in range(5))
    qml = (f'<!DOCTYPE qgis><qgis version="3.28"><renderer-v2 type="graduatedSymbol" attr="volume">'
           f'<ranges>{ranges}</ranges><symbols>{syms}</symbols></renderer-v2></qgis>')
    open(os.path.join(out, "network.qml"), "w").write(qml)
    # PyQGIS automation: load layers + apply styles (template-driven)
    open(os.path.join(out, "load_layers.py"), "w").write(QGIS_LOAD)
    open(os.path.join(out, "README.txt"), "w").write(
        "QGIS export. Drag network.geojson in and it auto-loads network.qml (same basename). "
        "Or run load_layers.py in the QGIS Python console to add all layers styled by template.")
    return ["network.geojson", "network.qml", "load_layers.py"]

QGIS_LOAD = '''# Run in QGIS Python console (from this folder) — adds gui4gmns layers with template styles.
import os
from qgis.core import QgsVectorLayer, QgsProject
here = os.path.dirname(__file__) if "__file__" in dir() else os.getcwd()
for fn, qml in [("network.geojson", "network.qml"), ("od.geojson", None)]:
    p = os.path.join(here, fn)
    if not os.path.exists(p): continue
    lyr = QgsVectorLayer(p, fn.replace(".geojson", ""), "ogr")
    if qml and os.path.exists(os.path.join(here, qml)): lyr.loadNamedStyle(os.path.join(here, qml))
    QgsProject.instance().addMapLayer(lyr)
print("gui4gmns layers loaded.")
'''

# ---------------- Google Earth KML (3D + fly) ----------------
def kml_color(t):   # KML is aabbggrr
    r, g, b = ramp_rgb(t); return f"ff{b:02x}{g:02x}{r:02x}"

def export_kml(D, out):
    os.makedirs(out, exist_ok=True)
    mv = max([L["vol"] for L in D["links"]] + [1])
    styles, pms = [], []
    for i, L in enumerate(D["links"]):
        t = L["vol"] / mv; alt = L["vol"] / mv * 300      # extrude height ∝ volume -> 3D bars
        styles.append(f'<Style id="s{i}"><LineStyle><color>{kml_color(t)}</color>'
                      f'<width>{1+4*t:.1f}</width></LineStyle><PolyStyle><color>{kml_color(t)[:2]}aa{kml_color(t)[4:]}</color></PolyStyle></Style>')
        coords = " ".join(f"{x},{y},{alt:.0f}" for x, y in L["poly"])
        pms.append(f'<Placemark><name>link {L["id"]}</name><styleUrl>#s{i}</styleUrl>'
                   f'<description>volume {L["vol"]:.0f}, V/C {L["voc"]:.2f}</description>'
                   f'<LineString><extrude>1</extrude><altitudeMode>relativeToGround</altitudeMode>'
                   f'<tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString></Placemark>')
    # trajectory fly-tour: time-stamped placemarks so Google Earth's time slider animates
    tpm = []
    for i, tr in enumerate(D["trips"][:200]):
        for x, y, t in tr:
            hh = int(t // 60) % 24; mm = int(t % 60)
            tpm.append(f'<Placemark><TimeStamp><when>2024-01-01T{hh:02d}:{mm:02d}:00Z</when></TimeStamp>'
                       f'<Point><coordinates>{x},{y},20</coordinates></Point></Placemark>')
    kml = ('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2">'
           '<Document><name>gui4gmns — GMNS 3D</name>'
           f'{"".join(styles)}<Folder><name>network (3D volume bars)</name>{"".join(pms)}</Folder>'
           f'<Folder><name>trajectories (time slider)</name>{"".join(tpm)}</Folder></Document></kml>')
    open(os.path.join(out, "gmns.kml"), "w", encoding="utf-8").write(kml)
    open(os.path.join(out, "README.txt"), "w").write(
        "Google Earth export. Open gmns.kml in Google Earth (Pro/web). Links are extruded 3D bars "
        "(height = volume) — tilt to fly. Use the time slider to animate trajectory points.")
    return ["gmns.kml"]

TARGETS = {"kepler": export_kepler, "deckgl": export_deckgl, "qgis": export_qgis, "kml": export_kml}

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    src = a[0]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(src, "export")
    tgt = a[a.index("--target") + 1] if "--target" in a else "all"
    D = read_gmns(src)
    print(f"read: {len(D['links'])} links, {len(D['trips'])} trips, {len(D['od'])} OD, geographic={D['geo']}")
    if not D["geo"]:
        print("WARN: coordinates not lon/lat — kepler/kml/deck.gl need geographic CRS (add crs.txt or reproject).")
    targets = TARGETS if tgt == "all" else {tgt: TARGETS[tgt]}
    for name, fn in targets.items():
        o = os.path.join(out, name)
        files = fn(D, o)
        print(f"  {name:7s} -> {o}/  ({', '.join(files)})")

if __name__ == "__main__":
    main()

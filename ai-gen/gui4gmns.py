#!/usr/bin/env python3
"""gui4gmns — the NeXTA-X master generator: GMNS run folder in -> self-contained dashboard.html out.

The user never opens files in a viewer: this engine PREPROCESSES the package (slim, subsample, quality-
check) and EMBEDS the data into one double-clickable HTML (works offline; OSM basemap appears when
online). Template blocks follow ai-gen/VIZ_SCHEMA.md so an AI (or a student) can generate custom
dashboards from the same embedded JSON.

Usage: python gui4gmns.py <dataset_or_run_folder> [-o dashboard.html] [--max-traj 2000]
"""
import csv, json, math, os, re, sys

__version__ = "0.1.0"
__all__ = ["generate", "load", "main", "__version__"]

def fnum(v):
    try: return float(v)
    except: return 0.0

def load(folder, max_traj=2000, basemap="osm"):
    D = {"meta": {"folder": os.path.abspath(folder), "checks": [], "basemap": basemap}, "nodes": [], "links": [],
         "bins": [], "td": {}, "trajs": {}, "run": None, "paths": []}
    ck = D["meta"]["checks"]
    def rd(name):
        p = os.path.join(folder, name)
        if not os.path.exists(p): return None
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    n = rd("node.csv"); l = rd("link.csv")
    if not n or not l:
        sys.exit("need node.csv + link.csv")
    nid = {}; zone_pts = {}
    for r in n:
        i = int(fnum(r["node_id"])); nid[i] = (fnum(r["x_coord"]), fnum(r["y_coord"]))
        zid = (r.get("zone_id") or "").strip()
        D["nodes"].append([i, round(fnum(r["x_coord"]), 6), round(fnum(r["y_coord"]), 6),
                           1 if zid else 0])
        if zid: zone_pts.setdefault(zid, []).append((fnum(r["x_coord"]), fnum(r["y_coord"])))
    # optional CRS
    crs = os.path.join(folder, "crs.txt")
    tr = None
    if os.path.exists(crs):
        txt = open(crs).read().strip()
        if txt.lower() != "none":
            try:
                import pyproj
                tr = pyproj.Transformer.from_crs(int(txt.upper().replace("EPSG:", "")), 4326,
                                                 always_xy=True)
                ck.append(f"reprojected EPSG:{txt}")
            except Exception as e:
                ck.append(f"WARN crs.txt present but transform failed: {e}")
    def proj(x, y):
        if tr: x, y = tr.transform(x, y)
        return round(x, 6), round(y, 6)
    perf = {r0["link_id"]: r0 for r0 in (rd("link_performance.csv") or []) if r0.get("link_id")}
    volcol = None
    if perf:
        any_r = next(iter(perf.values()))
        volcol = "cum_departure" if "cum_departure" in any_r else "volume"
    miss_geom = 0
    for r in l:
        lid = int(fnum(r["link_id"])); poly = None
        g = r.get("geometry") or ""
        if "LINESTRING" in g:
            pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", g)
            if len(pts) >= 2: poly = [proj(float(a), float(b)) for a, b in pts]
        if not poly:
            a = nid.get(int(fnum(r["from_node_id"]))); b = nid.get(int(fnum(r["to_node_id"])))
            if not a or not b: miss_geom += 1; continue
            poly = [proj(*a), proj(*b)]
        p = perf.get(str(lid)) or perf.get(r["link_id"]) or {}
        vol = fnum(p.get(volcol)) if p else 0.0
        q = fnum(p.get("max_queue_exb") or p.get("queue") or 0)
        cap = fnum(r.get("capacity") or 1800) * max(1, fnum(r.get("lanes") or 1))
        D["links"].append([lid, poly, round(vol, 1), round(q, 1), round(cap, 0),
                           round(fnum(r.get("vdf_length_mi") or 0) or fnum(r.get("length") or 1), 3)])
    if miss_geom: ck.append(f"WARN {miss_geom} links without resolvable geometry (skipped)")
    # geographic?
    xs = [pt[0] for L in D["links"] for pt in L[1]]; ys = [pt[1] for L in D["links"] for pt in L[1]]
    D["meta"]["geo"] = bool(xs) and -181 < min(xs) < max(xs) < 181 and -85 < min(ys) < max(ys) < 85
    if os.path.exists(crs) and open(crs).read().strip().lower() == "none": D["meta"]["geo"] = False
    td = rd("link_performance_15min.csv")
    if td:
        D["bins"] = sorted({r["time_bin_start"] for r in td},
                           key=lambda s: int(s[:2]) * 60 + int(s[3:5]))
        bx = {b: i for i, b in enumerate(D["bins"])}
        for r in td:
            vals = [round(fnum(r.get("inflow_veh")), 0), round(fnum(r.get("queue_exb") or 0), 0)]
            if r.get("speed"):                                    # QVDF time-dependent speed layer
                vals += [round(fnum(r["speed"]), 1), round(fnum(r.get("free_flow") or 0), 1)]
            D["td"].setdefault(r["link_id"], {})[bx[r["time_bin_start"]]] = vals
        if any(len(v) > 2 for m in D["td"].values() for v in m.values()):
            ck.append("time-dependent SPEED present (QVDF) -> 'speed' MOE mode enabled")
    tj = rd("agent_trajectory.csv")
    if tj:
        for r in tj:
            a = int(fnum(r["agent_id"]))
            if a >= max_traj: continue
            D["trajs"].setdefault(a, []).append([round(fnum(r["time_min"]), 2),
                                                 int(fnum(r["link_id"])), r.get("buffer") or ""])
        for ev in D["trajs"].values(): ev.sort()
        ck.append(f"trajectories subsampled to {len(D['trajs'])} agents (--max-traj)")
    pf = rd("path_flow.csv")
    if pf:
        for r in pf[:60]:
            ids = [int(x) for x in (r.get("link_ids") or "").split(";") if x.strip().isdigit()]
            if ids: D["paths"].append([fnum(r.get("base_volume") or 1), ids])
    rj = os.path.join(folder, "run_summary.json")
    if os.path.exists(rj): D["run"] = json.load(open(rj))
    # ---- corridor speed profile: INRIX-observed vs QVDF-model space-time contour + validation ----
    cs = rd("corridor_speed.csv")
    if cs:
        cor = {}
        for r in cs:
            name = r.get("corridor") or "corridor"
            c = cor.setdefault(name, {"seq": [], "bins": [], "dist": {}, "cells": {}, "ff": 0})
            seq = int(fnum(r["seq"])); tb = r["time"]
            if seq not in c["dist"]: c["dist"][seq] = round(fnum(r["cum_dist_mi"]), 3)
            if tb not in c["bins"]: c["bins"].append(tb)
            c["cells"].setdefault(seq, {})[tb] = [round(fnum(r["speed_inrix"]), 1),
                                                   round(fnum(r["speed_qvdf"]), 1)]
            c["ff"] = max(c["ff"], round(fnum(r["free_flow"]), 1))
        for name, c in cor.items():
            c["seq"] = sorted(c["dist"], key=lambda s: c["dist"][s])
            c["bins"] = sorted(set(c["bins"]), key=lambda s: int(s[:2]) * 60 + int(s[3:5]))
            # validation: RMSE / R2 / bias over all cells with both observed & model > 0
            o = []; m = []
            for s in c["seq"]:
                for tb in c["bins"]:
                    v = c["cells"].get(s, {}).get(tb)
                    if v and v[0] > 0 and v[1] > 0: o.append(v[0]); m.append(v[1])
            if o:
                nn = len(o); mo = sum(o) / nn
                rmse = (sum((a - b) ** 2 for a, b in zip(o, m)) / nn) ** 0.5
                sst = sum((a - mo) ** 2 for a in o) or 1
                c["val"] = {"n": nn, "rmse": round(rmse, 2),
                            "r2": round(1 - sum((a - b) ** 2 for a, b in zip(o, m)) / sst, 3),
                            "bias": round(sum(b - a for a, b in zip(o, m)) / nn, 2), "ff": c["ff"]}
                ck.append(f"corridor '{name}': INRIX-vs-QVDF {nn} cells, "
                          f"RMSE {c['val']['rmse']} mph, R2 {c['val']['r2']}")
        D["corridor"] = cor
    # ---- demand layer (learned from plot4gmns: OD desire lines + demand matrix) ----
    dm = rd("demand.csv")
    if dm and zone_pts:
        zc = {z: proj(sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
              for z, pts in zone_pts.items()}
        od = {}
        for r in dm:
            oz = (r.get("o_zone_id") or "").strip(); dz = (r.get("d_zone_id") or "").strip()
            v = fnum(r.get("volume"))
            if v > 0 and oz in zc and dz in zc and oz != dz:
                od[(oz, dz)] = od.get((oz, dz), 0) + v
        top = sorted(od.items(), key=lambda kv: -kv[1])[:400]      # top desire lines by volume
        lines = [[*zc[o], *zc[d], round(v, 1)] for (o, d), v in top]
        # compact matrix for the heatmap: the busiest ~24 origins x destinations
        zvol = {}
        for (o, d), v in od.items(): zvol[o] = zvol.get(o, 0) + v; zvol[d] = zvol.get(d, 0) + v
        hz = [z for z, _ in sorted(zvol.items(), key=lambda kv: -kv[1])[:24]]
        mat = [[round(od.get((o, d), 0), 0) for d in hz] for o in hz]
        D["demand"] = {"lines": lines, "n_od": len(od), "total": round(sum(od.values()), 0),
                       "hz": hz, "mat": mat}
        ck.append(f"demand: {len(od)} OD pairs, total {D['demand']['total']:.0f} veh; "
                  f"top {len(lines)} desire lines (learned from plot4gmns)")
    # ---- attribute distributions (learned from plot4gmns: capacity/free-speed/lanes histograms) ----
    def hist(vals, nb=10):
        vals = [v for v in vals if v > 0]
        if not vals: return None
        lo, hi = min(vals), max(vals)
        if hi <= lo: return {"lo": lo, "hi": hi, "bins": [len(vals)]}
        b = [0] * nb
        for v in vals: b[min(nb - 1, int((v - lo) / (hi - lo) * nb))] += 1
        return {"lo": round(lo, 1), "hi": round(hi, 1), "bins": b}
    lk = list(l)
    D["dist"] = {"capacity": hist([fnum(r.get("capacity")) for r in lk]),
                 "free_speed": hist([fnum(r.get("free_speed")) for r in lk]),
                 "lanes": hist([fnum(r.get("lanes")) for r in lk]),
                 "volume": hist([L[2] for L in D["links"]])}
    # ---- tier classification + volume percentiles (multi-agent study, ai-gen/variants/*.md) ----
    # connectors carry a per-lane capacity sentinel (>=40000 total) -> tier 4, never auto-drawn
    real = [L for L in D["links"] if L[4] < 40000]
    ct = sorted(L[4] for L in real)
    pct = lambda arr, p: arr[min(len(arr) - 1, int(p * len(arr)))] if arr else 0
    t1, t2 = pct(ct, 0.85), pct(ct, 0.50)
    rv = sorted(L[2] for L in real if L[2] > 0)
    D["meta"]["vstats"] = {"p25": pct(rv, 0.25), "p99": pct(rv, 0.99)}
    for L in D["links"]:
        L.append(4 if L[4] >= 40000 else (1 if L[4] >= t1 else 2 if L[4] >= t2 else 3))
    n1 = sum(1 for L in D["links"] if L[6] == 1); n4 = sum(1 for L in D["links"] if L[6] == 4)
    zv = sum(1 for L in D["links"] if L[6] == 1 and L[2] == 0)
    ck.append(f"tiers: {n1} major (cap*ln>={t1:.0f}), {n4} connectors excluded; "
              f"volume ramp anchored p25={D['meta']['vstats']['p25']:.0f} p99={D['meta']['vstats']['p99']:.0f}")
    if zv: ck.append(f"WARN checks layer: {zv} zero-volume MAJOR links (enable 'checks' to see)")
    # ---- STATIC hybrid background: OSM tiles for the network-wide view + SATELLITE tiles one
    #      zoom level deeper for detail (viewer switches by zoom) — both embedded as data URIs ----
    def fetch_tileset(src, z, cap):
        import base64, urllib.request
        n = 2**z
        cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desktop-qt", "tile_cache")
        os.makedirs(cache, exist_ok=True)
        tiles = []
        txr = range(max(0, int((bx0 + 180) / 360 * n) - 1), min(n - 1, int((bx1 + 180) / 360 * n) + 1) + 1)
        tyr = range(max(0, int((1 - by1 / 180) / 2 * n) - 1), min(n - 1, int((1 - by0 / 180) / 2 * n) + 1) + 1)
        if len(txr) * len(tyr) > cap: return tiles
        for tx in txr:
            for ty in tyr:
                ext = "png" if src == "osm" else "jpg"
                p = os.path.join(cache, f"{src}_{z}_{tx}_{ty}.{ext}")
                if src == "osm" and not os.path.exists(p):
                    old = os.path.join(cache, f"{z}_{tx}_{ty}.png")
                    if os.path.exists(old): p = old
                if not os.path.exists(p):
                    url = (f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png" if src == "osm" else
                           f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                           f"MapServer/tile/{z}/{ty}/{tx}")                    # satellite = z/y/x
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "NeXTA-X/1.0 (research)"})
                        open(p, "wb").write(urllib.request.urlopen(req, timeout=15).read())
                    except Exception: continue
                mime = "png" if p.endswith("png") else "jpeg"
                b64 = base64.b64encode(open(p, "rb").read()).decode()
                tiles.append([f"data:image/{mime};base64," + b64, tx / n * 360 - 180,
                              (tx + 1) / n * 360 - 180, 180 * (1 - 2 * (ty + 1) / n), 180 * (1 - 2 * ty / n)])
        return tiles
    if D["meta"]["geo"] and basemap != "none":
        mercy = lambda lat: math.degrees(math.log(math.tan(math.radians(45 + lat / 2))))
        bx0, bx1 = min(xs), max(xs); by0, by1 = mercy(min(ys)), mercy(max(ys))
        z = max(1, min(15, int(math.log2(360 * 5 / max(bx1 - bx0, 1e-6)))))
        while (int((bx1 + 180) / 360 * 2**z) - int((bx0 + 180) / 360 * 2**z) + 2) * \
              (int((1 - by0 / 180) / 2 * 2**z) - int((1 - by1 / 180) / 2 * 2**z) + 2) > 48 and z > 1:
            z -= 1
        D["tiles"] = fetch_tileset("osm", z, 60)                    # network-wide: OSM
        D["tiles_sat"] = fetch_tileset("satellite", z + 1, 130)     # zoomed detail: satellite
        D["meta"]["attrib"] = "© OpenStreetMap contributors · Imagery © Esri, Maxar, Earthstar Geographics"
        ck.append(f"hybrid basemap: {len(D['tiles'])} OSM tiles z{z} (overview) + "
                  f"{len(D['tiles_sat'])} satellite tiles z{z+1} (detail), offline-capable")
    # ---- data quality checks (the "check all the data" panel) ----
    ck.append(f"nodes {len(D['nodes'])}, links {len(D['links'])}, "
              f"zones {sum(1 for x in D['nodes'] if x[3])}")
    if perf:
        withvol = sum(1 for L in D['links'] if L[2] > 0)
        ck.append(f"MOE coverage: {withvol}/{len(D['links'])} links with volume")
    else: ck.append("WARN no link_performance.csv -> network-only view")
    if D["run"]:
        c = "OK" if D["run"].get("conserved") else "FAIL"
        ck.append(f"conservation {c}: {D['run'].get('completed')}/{D['run'].get('agents')}")
        g = D["run"].get("gridlock") or {}
        if g.get("oversaturated"): ck.append(f"WARN OVERSATURATED (first warning {g.get('first_warning')})")
    if not D["bins"]: ck.append("note: no 15-min file -> static MOE only")
    return D

TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>NeXTA-X dashboard — __NAME__</title>
<style>
body{margin:0;background:#14181d;color:#d8dee6;font:13px system-ui}
#bar{display:flex;gap:14px;align-items:center;padding:8px 14px;background:#1d232b;border-bottom:1px solid #2c3540;flex-wrap:wrap}
#bar b{color:#4db8ff;font-size:15px}
.kpi{background:#232b35;border:1px solid #2c3540;border-radius:6px;padding:5px 12px;text-align:center}
.kpi .v{font-size:17px;font-weight:700;color:#4db8ff}.kpi .l{font-size:10px;color:#8a94a3}
button,select{background:#28303a;color:#d8dee6;border:1px solid #2c3540;border-radius:4px;padding:4px 9px;cursor:pointer}
#wrap{position:relative}#cv{display:block;width:100vw;height:calc(100vh - 118px)}
#hud{position:absolute;left:12px;bottom:12px;background:rgba(20,26,32,.9);padding:6px 12px;border-radius:6px;border:1px solid #2c3540}
#clock{font-size:20px;font-weight:700;color:#4db8ff}
#checks{padding:5px 14px;background:#171c22;border-top:1px solid #2c3540;font-size:11.5px;color:#8a94a3;max-height:52px;overflow-y:auto}
.warn{color:#ffb45f}
input[type=range]{width:260px;accent-color:#4db8ff}
</style></head><body>
<div id="bar"><b>NeXTA-X</b><span style="color:#8a94a3">__NAME__ · generated __DATE__</span>
<span id="kpis" style="display:flex;gap:8px"></span>
<select id="moe"><option value="volume">volume</option><option value="voc">V/C</option><option value="queue">queue</option><option value="td">time-dependent flow</option><option value="speed">t-dep speed (QVDF)</option></select>
<button id="play" onclick="togglePlay()">▶ Play</button><input type="range" id="ts" oninput="clock=+this.value">
<label style="color:#8a94a3"><input type="checkbox" id="base" checked onchange="draw()"> basemap</label>
<label style="color:#8a94a3"><input type="checkbox" id="checks"> checks</label>
<label style="color:#8a94a3">min vol <input type="range" id="minvol" min="0" max="100" value="0" style="width:90px"></label>
<label id="demLab" style="color:#8a94a3;display:none"><input type="checkbox" id="demand" onchange="draw()"> demand OD</label>
<button id="distBtn" style="display:none" onclick="toggleDist()">▦ distributions</button>
<button id="corBtn" style="display:none" onclick="toggleCor()">▤ corridor speed</button>
<button id="sciBtn" onclick="toggleSci()">✓ physics</button>
<button onclick="fit()">Fit</button></div>
<div id="scipanel" style="display:none;position:absolute;right:10px;top:10px;width:360px;background:rgba(20,26,32,.97);border:1px solid #2c3540;border-radius:6px;padding:8px 10px;max-height:80%;overflow:auto;z-index:6">
  <div style="display:flex;align-items:center;gap:8px"><b style="color:#4db8ff">Physics-informed checks (SCI)</b>
    <span style="margin-left:auto"><button onclick="toggleSci()" style="padding:1px 7px">✕</button></span></div>
  <div id="scisum" style="text-align:center;font-weight:700;border-radius:4px;padding:4px;margin:6px 0"></div>
  <div id="scibody"></div>
  <div style="font-size:10px;color:#6e7681;margin-top:6px">Conservation & bound gates computed from this dashboard's own data — the reusable version of the Apache SCI panel.</div>
</div>
<div id="wrap"><canvas id="cv"></canvas><div id="hud"><span id="clock">--:--</span></div>
<div id="corpanel" style="display:none;position:absolute;left:0;right:0;bottom:0;background:rgba(20,26,32,.96);border-top:1px solid #2c3540;padding:8px 12px;max-height:56%;overflow:auto">
  <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
    <b style="color:#4db8ff">Corridor speed contour</b>
    <select id="corSel"></select>
    <span id="corVal" style="color:#8a94a3"></span>
    <span style="margin-left:auto;color:#8a94a3;font-size:11px">distance ↓ · time → · green=free-flow red=breakdown · click a bin to sync map clock</span>
    <button onclick="toggleCor()" style="padding:2px 8px">✕</button>
  </div>
  <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:6px">
    <div><div style="font-size:11px;color:#8a94a3;margin-bottom:2px">INRIX observed</div><canvas id="corObs"></canvas></div>
    <div><div style="font-size:11px;color:#8a94a3;margin-bottom:2px">QVDF model</div><canvas id="corMod"></canvas></div>
    <div><div style="font-size:11px;color:#8a94a3;margin-bottom:2px">model − observed (bias)</div><canvas id="corDif"></canvas></div>
  </div>
</div>
<div id="distpanel" style="display:none;position:absolute;left:0;right:0;bottom:0;background:rgba(20,26,32,.96);border-top:1px solid #2c3540;padding:8px 12px;max-height:56%;overflow:auto">
  <div style="display:flex;gap:14px;align-items:center"><b style="color:#4db8ff">Distributions &amp; demand</b>
    <span style="margin-left:auto;color:#8a94a3;font-size:11px">learned from plot4gmns</span>
    <button onclick="toggleDist()" style="padding:2px 8px">✕</button></div>
  <div id="distbody" style="display:flex;gap:22px;flex-wrap:wrap;margin-top:8px"></div>
</div>
<div id="attrib" style="position:absolute;right:6px;bottom:4px;font-size:10px;color:#aab;background:rgba(16,20,24,.6);padding:1px 6px;border-radius:3px"></div></div>
<div id="checks"></div>
<script>
const DATA=__DATA__;
const M={links:DATA.links,nodes:DATA.nodes,geo:DATA.meta.geo,bins:DATA.bins,td:DATA.td,trajs:DATA.trajs,run:DATA.run};
const my=lat=>180/Math.PI*Math.log(Math.tan(Math.PI/4+lat*Math.PI/360));
const DEM=DATA.demand||{}, DIST=DATA.dist||{};
if(M.geo){M.links.forEach(L=>L[1]=L[1].map(p=>[p[0],my(p[1])]));
 (DEM.lines||[]).forEach(l=>{l[1]=my(l[1]);l[3]=my(l[3]);});}
M.links.sort((a,b)=>a[2]-b[2]);                       // hot links stroke last (on top)
const VS=DATA.meta.vstats||{p25:1,p99:1000},l1p=Math.log1p;
const vscale=v=>Math.max(0,Math.min(1,(l1p(v)-l1p(VS.p25))/((l1p(VS.p99)-l1p(VS.p25))||1)));
function styleOf(L,mode,b){const t=L[6]||3;
 if(mode==='speed'){const d=(M.td[L[0]]||{})[b];
  if(!d||d.length<4||!d[3])return[-1,t===1?1.4:0.6];             // no speed data -> dim gray
  const r=d[2]/d[3];                                             // speed / free-flow
  return[Math.max(0,Math.min(1,(1-r)/0.6)),2.5+3.5*Math.max(0,Math.min(1,(1-r)/0.6))];}
 if(mode==='volume'){const v=vscale(L[2]);return[v,(t===1?2.2:t===2?1.2:0.6)+2.2*v];}
 if(mode==='voc'){const v=Math.min(1,L[2]/(L[4]*8||1));return[v,1+4*v];}
 if(mode==='queue'){const v=L[3]/maxQ;return[v,1+5*v];}
 const d=(M.td[L[0]]||{})[b],inf=d?d[0]:0,q=d?d[1]:0;
 return[q>0?0.55+0.45*Math.min(1,q/60):Math.min(1,inf*4/(L[4]||1800)),1+4*Math.min(1,inf/450)];}
let bbox=null,zoom=1,px=0,py=0,clock=420,playing=false,maxVol=1,maxQ=1;
// STATIC embedded hybrid basemap: OSM (network-wide) -> satellite (zoomed detail); offline-capable
const mkImgs=a=>(a||[]).map(t=>{const im=new Image();im.src=t[0];return[im,t[1],t[2],t[3],t[4]];});
let tiles=mkImgs(DATA.tiles), satTiles=mkImgs(DATA.tiles_sat);
M.links.forEach(L=>{maxVol=Math.max(maxVol,L[2]);maxQ=Math.max(maxQ,L[3]);});
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
function fit(){let a=[1e18,1e18,-1e18,-1e18];M.links.forEach(L=>L[1].forEach(p=>{a[0]=Math.min(a[0],p[0]);a[1]=Math.min(a[1],p[1]);a[2]=Math.max(a[2],p[0]);a[3]=Math.max(a[3],p[1]);}));bbox=a;zoom=1;px=py=0;loadTiles();}
function vt(){const w=cv.width,h=cv.height,ar=w/h,span=Math.max(bbox[2]-bbox[0],(bbox[3]-bbox[1])*ar)||1;
 const s=w/span*0.94*zoom,cx=(bbox[0]+bbox[2])/2,cy=(bbox[1]+bbox[3])/2;return{s,tx:w/2-cx*s+px,ty:h/2+cy*s+py};}
function loadTiles(){if(DATA.tiles&&DATA.tiles.length)return;   // static background embedded
 tiles=[];if(!M.geo||!document.getElementById('base').checked)return;
 const z=Math.max(1,Math.min(16,Math.floor(Math.log2(360*5/Math.max(bbox[2]-bbox[0],1e-6))))),n=2**z;
 const tx0=Math.floor((bbox[0]+180)/360*n),tx1=Math.floor((bbox[2]+180)/360*n);
 const ty0=Math.floor((1-bbox[3]/180)/2*n),ty1=Math.floor((1-bbox[1]/180)/2*n);
 for(let tx=Math.max(0,tx0-1);tx<=Math.min(n-1,tx1+1);tx++)for(let ty=Math.max(0,ty0-1);ty<=Math.min(n-1,ty1+1);ty++){
  const img=new Image();img.crossOrigin='anonymous';img.onload=()=>draw();
  img.src=`https://tile.openstreetmap.org/${z}/${tx}/${ty}.png`;
  tiles.push([img,tx/n*360-180,(tx+1)/n*360-180,180*(1-2*(ty+1)/n),180*(1-2*ty/n)]);}}
const ramp=t=>{t=Math.max(0,Math.min(1,t));const r=t<.5?510*t:255,g=t<.5?255:255-(t-.5)*510;return`rgb(${r|0},${g|0},60)`};
function binOf(){let b=0;M.bins.forEach((t,i)=>{if(+t.slice(0,2)*60+ +t.slice(3,5)<=clock)b=i;});return b;}
function draw(){cv.width=cv.clientWidth;cv.height=cv.clientHeight;if(!bbox)return;
 ctx.fillStyle='#101418';ctx.fillRect(0,0,cv.width,cv.height);const T=vt();
 const W=(x,y)=>[x*T.s+T.tx,-y*T.s+T.ty];
 if(document.getElementById('base').checked){
  const set=(zoom>=2.2&&satTiles.length)?satTiles:tiles;   // OSM network-wide -> satellite in detail
  try{ctx.filter='saturate(40%)';}catch(e){}
  set.forEach(([im,x0,x1,y0,y1])=>{if(!im.complete||!im.naturalWidth)return;
   const a=W(x0,y1),b=W(x1,y0);ctx.drawImage(im,a[0],a[1],b[0]-a[0],b[1]-a[1]);});
  try{ctx.filter='none';}catch(e){}
  ctx.fillStyle='rgba(16,20,24,0.55)';ctx.fillRect(0,0,cv.width,cv.height);}   // dim + desat
 const mode=document.getElementById('moe').value,b=binOf();
 const mv=Math.pow(+document.getElementById('minvol').value/100,2)*maxVol;
 const zTier=zoom<2.5?1:zoom<8?2:3;                    // LOD: skeleton -> +middle -> all real roads
 const path=L=>{ctx.beginPath();L[1].forEach((p,i)=>{const s=W(p[0],p[1]);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();};
 ctx.lineCap='round';
 M.links.forEach(L=>{const t=L[6]||3;if(t>2||t>zTier||L[2]<mv)return;            // casing: tiers 1-2 only
  const[,w]=styleOf(L,mode,b);ctx.strokeStyle='rgba(0,0,0,0.71)';ctx.lineWidth=w+3;path(L);});
 M.links.forEach(L=>{const t=L[6]||3;if(t>zTier||L[2]<mv)return;
  const[v,w]=styleOf(L,mode,b);ctx.strokeStyle=v<0?'#39424e':ramp(v);ctx.lineWidth=w;path(L);});
 if(document.getElementById('checks').checked)
  M.links.forEach(L=>{if((L[6]||3)===1&&L[2]===0){ctx.strokeStyle='#ff4df0';ctx.lineWidth=2.5;path(L);}});
 if(document.getElementById('demand')&&document.getElementById('demand').checked&&DEM.lines){
  const mx=Math.max(1,...DEM.lines.map(l=>l[4]));
  DEM.lines.forEach(l=>{const a=W(l[0],l[1]),b=W(l[2],l[3]),v=l[4]/mx;
   ctx.strokeStyle=`rgba(255,${(180-120*v)|0},${(80-60*v)|0},${0.25+0.5*v})`;ctx.lineWidth=0.5+3.5*v;
   ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();});}
 const lk={};M.links.forEach(L=>lk[L[0]]=L);
 for(const a in M.trajs){const ev=M.trajs[a];if(!ev.length||clock<ev[0][0]||clock>ev[ev.length-1][0])continue;
  let i=0;while(i+1<ev.length&&ev[i+1][0]<=clock)i++;
  const L=lk[ev[i][1]];if(!L)continue;let f=1,c='#ff5f5f';
  if(ev[i][2]==='ENB'&&i+1<ev.length&&ev[i+1][1]===ev[i][1]&&ev[i+1][0]>ev[i][0]){f=(clock-ev[i][0])/(ev[i+1][0]-ev[i][0]);c='#57d977';}
  const A=L[1][0],B=L[1][L[1].length-1],s=W(A[0]+(B[0]-A[0])*f,A[1]+(B[1]-A[1])*f);
  ctx.fillStyle=c;ctx.beginPath();ctx.arc(s[0],s[1],3,0,6.29);ctx.fill();}
 document.getElementById('clock').textContent=`${String(Math.floor(clock/60)%24).padStart(2,'0')}:${String(Math.floor(clock%60)).padStart(2,'0')}`;
 if(playing){clock+=0.35;if(clock>+document.getElementById('ts').max)clock=+document.getElementById('ts').min;document.getElementById('ts').value=clock;}
 requestAnimationFrame(draw);}
function togglePlay(){playing=!playing;document.getElementById('play').textContent=playing?'❚❚':'▶ Play';}
cv.addEventListener('wheel',e=>{e.preventDefault();zoom*=e.deltaY<0?1.25:.8;loadTiles();},{passive:false});
let dr=null;cv.addEventListener('mousedown',e=>dr=[e.offsetX,e.offsetY]);
cv.addEventListener('mousemove',e=>{if(!dr)return;px+=e.offsetX-dr[0];py+=e.offsetY-dr[1];dr=[e.offsetX,e.offsetY];});
window.addEventListener('mouseup',()=>dr=null);
// ---- corridor speed contour (INRIX observed vs QVDF model, space-time) ----
const COR=DATA.corridor||{};
const spdRamp=(sp,ff)=>{const r=Math.max(0,Math.min(1,1-sp/(ff||60)));   // 0=free(green) 1=stopped(red)
 return`rgb(${(r<.5?510*r:255)|0},${(r<.5?255:255-(r-.5)*510)|0},60)`;};
const difRamp=d=>{const t=Math.max(-15,Math.min(15,d))/15;              // blue=model slower, red=faster
 return t>0?`rgb(${(120+135*t)|0},${(120-100*t)|0},80)`:`rgb(80,${(120+100*-t)|0},${(160+95*-t)|0})`;};
function drawContour(cid,c,mode){const cvx=document.getElementById(cid),g=cvx.getContext('2d');
 const nb=c.bins.length,ns=c.seq.length,cw=Math.max(9,Math.min(20,Math.floor(460/nb))),ch=Math.max(4,Math.min(16,Math.floor(300/ns)));
 cvx.width=nb*cw+2;cvx.height=ns*ch+2;g.fillStyle='#101418';g.fillRect(0,0,cvx.width,cvx.height);
 c.seq.forEach((s,yi)=>c.bins.forEach((tb,xi)=>{const v=(c.cells[s]||{})[tb];if(!v)return;
   const io=v[0],iq=v[1];let col;
   if(mode==='obs')col=io>0?spdRamp(io,c.ff):'#1b2027';
   else if(mode==='mod')col=iq>0?spdRamp(iq,c.ff):'#1b2027';
   else col=(io>0&&iq>0)?difRamp(iq-io):'#1b2027';
   g.fillStyle=col;g.fillRect(1+xi*cw,1+yi*ch,cw-1,ch-1);}));
 cvx.onclick=e=>{const xi=Math.floor((e.offsetX-1)/cw);if(xi>=0&&xi<nb){
   const tb=c.bins[xi],mm=+tb.slice(0,2)*60+ +tb.slice(3,5);clock=mm;
   const sl=document.getElementById('ts');if(mm>=+sl.min&&mm<=+sl.max)sl.value=mm;
   if(document.getElementById('moe').value!=='speed')document.getElementById('moe').value='speed';}};
}
function renderCorridor(){const name=document.getElementById('corSel').value,c=COR[name];if(!c)return;
 drawContour('corObs',c,'obs');drawContour('corMod',c,'mod');drawContour('corDif',c,'dif');
 const v=c.val||{};document.getElementById('corVal').innerHTML=v.n?
  `<b>validation</b> n=${v.n} · RMSE <b style="color:#4db8ff">${v.rmse} mph</b> · R² <b style="color:#4db8ff">${v.r2}</b> · bias ${v.bias>0?'+':''}${v.bias} mph · free-flow ${v.ff} mph · length ${c.dist[c.seq[c.seq.length-1]]||''} mi`:'';}
function toggleCor(){const p=document.getElementById('corpanel');
 p.style.display=p.style.display==='none'?'block':'none';if(p.style.display==='block')renderCorridor();}
(function(){const names=Object.keys(COR);if(!names.length)return;
 document.getElementById('corBtn').style.display='';
 const sel=document.getElementById('corSel');
 names.forEach(n=>sel.insertAdjacentHTML('beforeend',`<option>${n}</option>`));
 sel.onchange=renderCorridor;})();
// ---- distributions + demand heatmap (learned from plot4gmns) ----
function histSVG(title,h){if(!h)return'';const mx=Math.max(1,...h.bins),nb=h.bins.length,bw=180/nb;
 let bars='';h.bins.forEach((c,i)=>{const bh=70*c/mx;
  bars+=`<rect x="${i*bw}" y="${72-bh}" width="${bw-1.5}" height="${bh}" fill="#4db8ff"/>`;});
 return`<div><div style="font-size:11px;color:#8a94a3;margin-bottom:2px">${title}</div>
  <svg width="182" height="90"><g>${bars}</g>
  <text x="0" y="88" fill="#8a94a3" font-size="9">${h.lo}</text>
  <text x="150" y="88" fill="#8a94a3" font-size="9">${h.hi}</text></svg></div>`;}
function demandHeatmap(){if(!DEM.mat||!DEM.mat.length)return'';
 const hz=DEM.hz,n=hz.length,cs=Math.max(6,Math.min(16,Math.floor(280/n)));
 const mx=Math.max(1,...DEM.mat.flat());let cells='';
 DEM.mat.forEach((row,i)=>row.forEach((v,j)=>{const t=v/mx,
  col=v?`rgb(${(40+215*t)|0},${(60+120*(1-t))|0},80)`:'#1b2027';
  cells+=`<rect x="${j*cs}" y="${i*cs}" width="${cs-1}" height="${cs-1}" fill="${col}"><title>O${hz[i]}→D${hz[j]}: ${v}</title></rect>`;}));
 return`<div><div style="font-size:11px;color:#8a94a3;margin-bottom:2px">demand matrix (top ${n} zones · O rows × D cols)</div>
  <svg width="${n*cs}" height="${n*cs}">${cells}</svg></div>`;}
function toggleDist(){const p=document.getElementById('distpanel');
 const show=p.style.display==='none';p.style.display=show?'block':'none';if(!show)return;
 let h='';['volume','capacity','free_speed','lanes'].forEach(k=>h+=histSVG(k.replace('_',' '),DIST[k]));
 if(DEM.total)h=`<div style="font-size:12px;color:#d8dee6;width:100%">demand: <b>${DEM.n_od.toLocaleString()}</b> OD pairs · total <b>${(DEM.total||0).toLocaleString()}</b> veh</div>`+h+demandHeatmap();
 document.getElementById('distbody').innerHTML=h;}
(function(){if(DEM.lines&&DEM.lines.length){document.getElementById('demLab').style.display='';}
 if((DIST&&DIST.volume)||DEM.total){document.getElementById('distBtn').style.display='';}})();
// ---- 7-check SCI physics panel (ported from the Apache simulator; data-driven for any dashboard) ----
function computeSCI(){
 const R=[]; const td=M.td||{}, bins=M.bins||[];
 const tdcells=()=>{const o=[];for(const l in td)for(const b in td[l]){const d=td[l][b];o.push([l,b,d]);}return o;};
 // 1) speed bounds: 0 <= v <= free_flow*1.15 (TD speed cells)
 {let n=0,bad=0,mx=0,ex='';tdcells().forEach(([l,b,d])=>{if(d.length<3)return;n++;const v=d[2],ff=d[3]||70;mx=Math.max(mx,v);
   if(v<0||v>ff*1.15){bad++;if(!ex)ex=`link ${l} @${bins[b]||b}: ${v} mph > ${(ff*1.15).toFixed(0)}`;}});
  R.push({id:'S',desc:'0 ≤ speed ≤ free-flow (TD speed cells)',pass:bad===0,na:n===0,
   stat:n?`${n-bad}/${n} ok, max ${mx.toFixed(0)} mph`:'no TD speed',fail:ex});}
 // 2) flow conservation: completed == agents (run), else volumes present & finite
 {let pass=true,stat='n/a',fail='';if(M.run){const a=M.run.agents||0,c=M.run.completed||0;pass=(c>=a);
   stat=`${c.toLocaleString()}/${a.toLocaleString()} completed`;if(!pass)fail=`${(a-c).toLocaleString()} agents unaccounted (CA<CD)`;}
  else{const tot=M.links.reduce((s,L)=>s+(L[2]||0),0);stat=`Σvol ${Math.round(tot).toLocaleString()}`;pass=isFinite(tot);}
  R.push({id:'C',desc:'Flow conservation — completed ≥ loaded (CA ≥ CD)',pass,na:false,stat,fail});}
 // 3) non-negativity: volume, queue, inflow >= 0
 {let bad=0,ex='';M.links.forEach(L=>{if((L[2]||0)<0||(L[3]||0)<0){bad++;if(!ex)ex=`link ${L[0]}: vol ${L[2]} q ${L[3]}`;}});
  tdcells().forEach(([l,b,d])=>{if(d[0]<0||d[1]<0){bad++;if(!ex)ex=`link ${l} @${bins[b]||b}: inflow ${d[0]} q ${d[1]}`;}});
  R.push({id:'N',desc:'Non-negativity — volume, queue, inflow ≥ 0',pass:bad===0,na:false,
   stat:bad?`${bad} negative`:'all ≥ 0',fail:ex});}
 // 4) capacity feasibility: volume <= capacity*hours*(1+slack)  (V/C physics)
 {let n=0,bad=0,mx=0,ex='';const H=8,SLK=1.25;M.links.forEach(L=>{const cap=L[4]||0,v=L[2]||0;if(cap<=0||cap>=40000||v<=0)return;n++;
   const vc=v/(cap*H);mx=Math.max(mx,vc);if(vc>SLK){bad++;if(!ex)ex=`link ${L[0]}: V/C ≈ ${vc.toFixed(2)}`;}});
  R.push({id:'Q',desc:'Capacity feasibility — volume ≤ capacity·h (V/C bound)',pass:bad===0,na:n===0,
   stat:n?`max V/C ${mx.toFixed(2)}, ${bad} over`:'no capacity data',fail:ex});}
 // 5) congestion consistency: queue>0 ⇒ speed < free-flow (fundamental-relation sanity)
 {let n=0,bad=0,ex='';tdcells().forEach(([l,b,d])=>{if(d.length<3||!d[3])return;const q=d[1],v=d[2],ff=d[3];if(q>0){n++;
   if(v>=ff*0.98){bad++;if(!ex)ex=`link ${l} @${bins[b]||b}: queued but ${v}≈free-flow`;}}});
  R.push({id:'K',desc:'Congestion consistency — queued ⇒ speed < free-flow',pass:bad===0,na:n===0,
   stat:n?`${n-bad}/${n} queued cells ok`:'no queued speed cells',fail:ex});}
 // 6) topology valid: each link ≥2 finite geometry points
 {let bad=0,ex='';M.links.forEach(L=>{const g=L[1];if(!g||g.length<2||g.some(p=>!isFinite(p[0])||!isFinite(p[1]))){bad++;if(!ex)ex=`link ${L[0]}: degenerate geometry`;}});
  R.push({id:'T',desc:'Topology — every link has ≥2 finite geometry points',pass:bad===0,na:false,
   stat:bad?`${bad} degenerate`:`${M.links.length} links ok`,fail:ex});}
 // 7) temporal ordering: per-agent trajectory times non-decreasing; bins sorted
 {let bad=0,ex='',n=0;for(const a in M.trajs){const ev=M.trajs[a];n++;for(let i=1;i<ev.length;i++)if(ev[i][0]<ev[i-1][0]-1e-6){bad++;if(!ex)ex=`agent ${a}: time goes backward`;break;}}
  for(let i=1;i<bins.length;i++){const p=+bins[i].slice(0,2)*60+ +bins[i].slice(3,5),q=+bins[i-1].slice(0,2)*60+ +bins[i-1].slice(3,5);if(p<q){bad++;if(!ex)ex='time bins not ordered';break;}}
  R.push({id:'O',desc:'Temporal ordering — trajectory times & bins monotonic',pass:bad===0,na:(n===0&&bins.length<2),
   stat:bad?`${bad} out of order`:(n?`${n} agents ok`:'bins ok'),fail:ex});}
 return R;}
function renderSci(){const R=computeSCI();const active=R.filter(r=>!r.na);const nf=active.filter(r=>!r.pass).length;
 const sum=document.getElementById('scisum');
 sum.textContent=nf?`${nf} of ${active.length} PHYSICS CHECKS FAILED`:`ALL ${active.length} PHYSICS CHECKS PASS`;
 sum.style.background=nf?'rgba(248,81,73,.2)':'rgba(46,160,67,.18)';sum.style.color=nf?'#f85149':'#56d364';
 sum.style.border='1px solid '+(nf?'#f85149':'#2ea043');
 document.getElementById('scibody').innerHTML=R.map(r=>{
  const st=r.na?'na':(r.pass?'pass':'fail');const ic=r.na?'–':(r.pass?'✓':'✗');
  const col=r.na?'#6e7681':(r.pass?'#56d364':'#f85149');const bg=r.na?'transparent':(r.pass?'rgba(46,160,67,.08)':'rgba(248,81,73,.16)');
  return `<div style="padding:4px 6px;border-radius:3px;margin-bottom:3px;background:${bg};border-left:2px solid ${col};font-size:11px">
   <span style="color:${col};font-weight:700">${ic}</span> ${r.desc}
   <div style="font-size:9px;color:#8a94a3;font-family:monospace;margin-top:1px">${r.stat}${r.fail?' — <span style=color:#f85149>'+r.fail+'</span>':''}</div></div>`;}).join('');
 // badge on the button
 const b=document.getElementById('sciBtn');b.textContent=(nf?'✗ '+nf+' physics':'✓ physics');
 b.style.background=nf?'#5a2020':'';b.style.color=nf?'#f85149':'';}
function toggleSci(){const p=document.getElementById('scipanel');const show=p.style.display==='none';
 p.style.display=show?'block':'none';if(show)renderSci();}
try{renderSci();}catch(e){}   // run once on load so the button badges immediately
// KPIs + checks
(function(){const k=document.getElementById('kpis');const vmt=M.links.reduce((s,L)=>s+L[2]*L[5],0);
 const add=(v,l)=>k.insertAdjacentHTML('beforeend',`<span class="kpi"><div class="v">${v}</div><div class="l">${l}</div></span>`);
 add(M.links.length.toLocaleString(),'links');add(Math.round(vmt).toLocaleString(),'VMT');
 if(M.run){add(M.run.agents.toLocaleString(),'agents');add(M.run.conserved?'✓':'✗','conserved');
  const g=M.run.gridlock||{};add(g.oversaturated?'YES':'no','oversat.');}
 add(Object.keys(M.trajs).length,'vehicles');add(M.bins.length,'TD bins');
 document.getElementById('checks').innerHTML='<b>preprocessing checks:</b> '+
  DATA.meta.checks.map(c=>c.startsWith('WARN')?`<span class="warn">${c}</span>`:c).join(' · ');
 if(DATA.meta.attrib)document.getElementById('attrib').textContent=DATA.meta.attrib;
 let t0=420,t1=480;const ts=[];for(const a in M.trajs)M.trajs[a].forEach(e=>ts.push(e[0]));
 if(ts.length){t0=Math.floor(Math.min(...ts));t1=Math.ceil(Math.max(...ts));}
 else if(M.bins.length){t0=+M.bins[0].slice(0,2)*60+ +M.bins[0].slice(3,5);t1=t0+M.bins.length*15;}
 const sl=document.getElementById('ts');sl.min=t0;sl.max=t1;sl.value=t0;clock=t0;})();
fit();requestAnimationFrame(draw);
</script></body></html>"""

def generate(folder, out=None, basemap="osm", max_traj=2000, split=True):
    """The NeXTA-X AI-Gen core: GMNS run folder -> self-contained dashboard.html.
    Importable like plot4gmns:  from gui4gmns import generate; generate('datasets/01_sioux_falls').
    Returns the output path."""
    out = out or os.path.join(folder, "dashboard.html")
    mt, bm = max_traj, basemap
    D = load(folder, mt, bm)
    import datetime
    html = (TEMPLATE.replace("__NAME__", os.path.basename(os.path.abspath(folder)))
                    .replace("__DATE__", str(datetime.date.today())))
    if split:
        lay = os.path.join(os.path.dirname(out) or ".", "dashboard_layers")
        os.makedirs(lay, exist_ok=True)
        net_links = [[L[0], L[1], L[4], L[5], L[6]] for L in D["links"]]
        parts = {"network.js":      ("network", {"meta": D["meta"], "nodes": D["nodes"], "links": net_links}),
                 "moe.js":          ("moe", {L[0]: [L[2], L[3]] for L in D["links"] if L[2] or L[3]}),
                 "td.js":           ("td", {"bins": D["bins"], "td": D["td"]}),
                 "trajectories.js": ("trajs", D["trajs"]),
                 "tiles_osm.js":    ("tiles_osm", D.get("tiles", [])),
                 "tiles_satellite.js": ("tiles_sat", D.get("tiles_sat", [])),
                 "corridor.js":     ("corridor", D.get("corridor", {})),
                 "demand.js":       ("demand", {"demand": D.get("demand", {}), "dist": D.get("dist", {})}),
                 "run.js":          ("run", {"run": D["run"], "paths": D["paths"]})}
        print(f"layer files -> {lay}/")
        for fn, (key, obj) in parts.items():
            p = os.path.join(lay, fn)
            open(p, "w", encoding="utf-8").write(
                f"window.NX=window.NX||{{}};NX.{key}={json.dumps(obj, separators=(',', ':'))};")
            print(f"   {fn:20s} {os.path.getsize(p)/1e6:6.2f} MB")
        inc = "\n".join(f'<script src="dashboard_layers/{fn}"></script>' for fn in parts)
        loader = ('<script>window.NX=window.NX||{};</script>\n' + inc + '\n<script>\n'
                  'const DATA=(function(){const N=window.NX;'
                  'const net=N.network||{meta:{checks:["WARN network layer missing"],geo:false},nodes:[],links:[]};'
                  'const moe=N.moe||{};net.links.forEach(L=>{const m=moe[L[0]]||[0,0];L.splice(2,0,m[0],m[1]);});'
                  'const td=N.td||{bins:[],td:{}};'
                  'return{meta:net.meta,nodes:net.nodes,links:net.links,bins:td.bins,td:td.td,'
                  'trajs:N.trajs||{},paths:(N.run&&N.run.paths)||[],run:(N.run&&N.run.run)||null,'
                  'tiles:N.tiles_osm||[],tiles_sat:N.tiles_sat||[],corridor:N.corridor||{},'
                  'demand:(N.demand&&N.demand.demand)||{},dist:(N.demand&&N.demand.dist)||{}};})();')
        html = html.replace("<script>\nconst DATA=__DATA__;", loader)
    else:
        html = html.replace("__DATA__", json.dumps(D, separators=(",", ":")))
    open(out, "w", encoding="utf-8").write(html)
    print(f"generated {out} ({os.path.getsize(out)/1e6:.2f} MB"
          f"{', split layers' if split else ', single-file'}) — checks: {len(D['meta']['checks'])}")
    for c in D["meta"]["checks"]: print("  ", c)
    return out

def main():
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    folder = args[0]
    out = args[args.index("-o") + 1] if "-o" in args else None
    mt = int(args[args.index("--max-traj") + 1]) if "--max-traj" in args else 2000
    bm = args[args.index("--basemap") + 1] if "--basemap" in args else "osm"   # osm | satellite | none
    generate(folder, out=out, basemap=bm, max_traj=mt, split="--single" not in args)

if __name__ == "__main__": main()

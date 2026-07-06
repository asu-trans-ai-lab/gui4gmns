#!/usr/bin/env python3
"""Make a *viewable* Kepler.gl demo for a GMNS folder — not blank instructions:
  - map.kepler.json : a kepler.gl map (data + config) that kepler.gl/demo?mapUrl= loads directly (live)
  - preview.png     : a Kepler-style rendered image so you can SEE the network before clicking
  - the drag-drop export files (network.geojson / trips.geojson / od_arcs.csv / kepler_config.json)

Usage: python kepler_demo.py <gmns_folder> "<label>" -o <out_dir> [--zoom 9] [--no-map]
"""
import os, sys, json, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gmns_to_viz", os.path.join(HERE, "..", "exporters", "gmns_to_viz.py"))
gv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gv)

def reproject(D, epsg):
    """Reproject link/OD/trip coords from a projected CRS (e.g. ARC EPSG:2240) to lon/lat for map portals."""
    from pyproj import Transformer
    tr = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
    for L in D["links"]:
        L["poly"] = [tr.transform(x, y) for x, y in L["poly"]]
    D["od"] = [(*tr.transform(o[0], o[1]), *tr.transform(o[2], o[3]), o[4]) for o in D["od"]]
    D["trips"] = [[(*tr.transform(x, y), t) for x, y, t in trp] for trp in D["trips"]]
    D["geo"] = True
    return D

def _metric(D):
    """Pick the field that actually varies: volume (network loading) if present, else free-flow speed.
    Returns (value_fn, label, hot_high) — hot_high=True means high value = red (busy)."""
    if max((L["vol"] for L in D["links"]), default=0) > 0:
        return (lambda L: L["vol"]), "volume (veh)", True
    sp = [L["speed"] for L in D["links"] if L["speed"] > 0]
    if sp and max(sp) - min(sp) > 1:
        # read_gmns puts observed speed in L["speed"] when link_performance exists, else free_speed.
        observed = any(abs(L["speed"] - L["ff"]) > 0.5 for L in D["links"])
        return (lambda L: L["speed"]), ("observed speed (mph)" if observed else "free-flow speed (mph)"), False
    return (lambda L: L["ff"]), "free-flow speed (mph)", False

def preview_png(D, out_png, title):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mc
    from matplotlib.collections import LineCollection
    val, label, hot_high = _metric(D)
    cool_to_hot = ["#2f9e5e", "#f5ce34", "#e6541e", "#a60d0a"]   # low->high = green->red
    cmap = mc.LinearSegmentedColormap.from_list("m", cool_to_hot if hot_high else cool_to_hot[::-1])
    vs = sorted(val(L) for L in D["links"])
    def pct(q): return vs[max(0, min(len(vs) - 1, int(q * (len(vs) - 1))))] if vs else 0
    lo, hi = pct(0.02), pct(0.97); rng = (hi - lo) or 1
    segs, cols, widths = [], [], []
    for L in D["links"]:
        if len(L["poly"]) >= 2:
            t = max(0.0, min(1.0, (val(L) - lo) / rng))
            segs.append(L["poly"]); cols.append(cmap(t)); widths.append(0.35 + (t ** 0.5) * 2.1)
    fig, ax = plt.subplots(figsize=(10, 7), dpi=100)
    fig.patch.set_facecolor("#0e1116"); ax.set_facecolor("#0e1116")
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=widths))
    ax.autoscale(); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{title}   ·   colored by {label}", color="#e6edf3", fontsize=14, pad=10)
    fig.savefig(out_png, dpi=100, facecolor="#0e1116", bbox_inches="tight"); plt.close(fig)

def kepler_map(D, label, zoom):
    feats = [{"type": "Feature",
              "properties": {"volume": round(L["vol"], 1), "speed": round(L["speed"], 1)},
              "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in L["poly"]]}}
             for L in D["links"] if len(L["poly"]) >= 2]
    xs = [c[0] for f in feats for c in f["geometry"]["coordinates"]]
    ys = [c[1] for f in feats for c in f["geometry"]["coordinates"]]
    lon, lat = sum(xs) / len(xs), sum(ys) / len(ys)
    rows = [[f, f["properties"]["volume"], f["properties"]["speed"]] for f in feats]
    fields = [{"name": "_geojson", "type": "geojson", "format": "", "analyzerType": "GEOMETRY"},
              {"name": "volume", "type": "real", "format": "", "analyzerType": "FLOAT"},
              {"name": "speed", "type": "real", "format": "", "analyzerType": "FLOAT"}]
    ds = {"version": "v1", "data": {"id": "network", "label": label, "color": [30, 150, 190],
                                    "allData": rows, "fields": fields}}
    # color by the field that varies (volume if present, else speed); low->high = green->red for volume
    color_field = "volume" if any(r[1] for r in rows) else "speed"
    ramp = ["#2f9e5e", "#f5ce34", "#e6541e", "#a60d0a"] if color_field == "volume" else ["#a60d0a", "#e6541e", "#f5ce34", "#2f9e5e"]
    layer = {"id": "net", "type": "geojson",
             "config": {"dataId": "network", "label": label, "columns": {"geojson": "_geojson"},
                        "isVisible": True,
                        "visConfig": {"opacity": 0.85, "thickness": 1.2, "stroked": True,
                                      "colorRange": {"name": color_field, "type": "sequential", "category": "custom",
                                                     "colors": ramp}}},
             "visualChannels": {"colorField": {"name": color_field, "type": "real"}, "colorScale": "quantile"}}
    cfg = {"version": "v1", "config": {
        "visState": {"layers": [layer], "filters": [],
                     "interactionConfig": {"tooltip": {"enabled": True,
                        "fieldsToShow": {"network": [{"name": "volume"}, {"name": "speed"}]}}}},
        "mapState": {"latitude": lat, "longitude": lon, "zoom": zoom, "pitch": 0, "bearing": 0},
        "mapStyle": {"styleType": "dark"}}}
    return {"datasets": [ds], "config": cfg, "info": {"app": "kepler.gl", "source": "gui4gmns"}}

def main():
    a = sys.argv[1:]
    src = a[0]; label = a[1] if len(a) > 1 and not a[1].startswith("-") else os.path.basename(src)
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(src, "kepler")
    zoom = float(a[a.index("--zoom") + 1]) if "--zoom" in a else 9.0
    top = int(a[a.index("--top") + 1]) if "--top" in a else 0
    os.makedirs(out, exist_ok=True)
    D = gv.read_gmns(src, max_traj=300)
    # reproject projected coords (crs.txt or --crs) so map portals place the network correctly
    epsg = a[a.index("--crs") + 1] if "--crs" in a else None
    if not epsg and os.path.exists(os.path.join(src, "crs.txt")):
        epsg = open(os.path.join(src, "crs.txt")).read().strip()
    if epsg and not D["geo"]:
        reproject(D, epsg); print(f"reprojected {epsg} -> lon/lat")
    # for big networks, keep the top-N most important links (by whatever field varies: volume, else
    # free-flow speed = the freeway/arterial skeleton, else lanes) so the live map loads fast
    if top and len(D["links"]) > top:
        val, mlabel, _ = _metric(D)
        D["links"] = sorted(D["links"], key=lambda L: -(val(L) or 0))[:top]
        label = f"{label} — top {top:,} by {mlabel.split(' (')[0]}"
    gv.export_kepler(D, out)                                    # drag-drop geojson set
    gv.export_kml(D, out)                                       # Google Earth KML
    if "--no-deck" not in a:
        gv.export_deckgl(D, os.path.join(out, "deckgl"))       # standalone deck.gl page
    preview_png(D, os.path.join(out, "preview.png"), f"{label} · {len(D['links']):,} links")
    if "--no-map" not in a and D["geo"]:
        json.dump(kepler_map(D, label, zoom), open(os.path.join(out, "map.kepler.json"), "w"))
    mb = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out) if os.path.isfile(os.path.join(out, f))) / 1e6
    print(f"portal demo -> {out}/  ({len(D['links']):,} links, geo={D['geo']}, {mb:.1f} MB)")

if __name__ == "__main__":
    main()

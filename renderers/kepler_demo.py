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

def load_polys(path):
    """Outer rings of a boundary GeoJSON (Polygon or MultiPolygon); holes ignored for a fast clip."""
    g = json.load(open(path, encoding="utf-8"))
    g = g.get("geometry", g)
    if g["type"] == "Polygon":
        return [g["coordinates"][0]]
    if g["type"] == "MultiPolygon":
        return [poly[0] for poly in g["coordinates"]]
    return []

def in_polys(x, y, rings):
    for ring in rings:
        inside = False; n = len(ring); j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
        if inside:
            return True
    return False

def _metric(D):
    """Pick the field that actually varies: volume (network loading) if present, else free-flow speed.
    Returns (value_fn, label, hot_high) — hot_high=True means high value = red (busy)."""
    if max((L["vol"] for L in D["links"]), default=0) > 0:
        return (lambda L: L["vol"]), "volume (veh)", True
    sp = [L["speed"] for L in D["links"] if L["speed"] > 0]
    if sp and max(sp) - min(sp) > 1:
        # read_gmns puts observed speed in L["speed"] when link_performance exists, else free_speed.
        # "observed" only if a real fraction of links differ from free_speed (not just a few defaults).
        n_diff = sum(1 for L in D["links"] if abs(L["speed"] - L["ff"]) > 0.5)
        observed = n_diff > 0.2 * max(1, len(D["links"]))
        return (lambda L: L["speed"]), ("observed speed (mph)" if observed else "free-flow speed (mph)"), False
    return (lambda L: L["ff"]), "free-flow speed (mph)", False

def preview_png(D, out_png, title, source="", boundary=None):
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
    if boundary:
        for ring in boundary:
            ax.plot([p[0] for p in ring], [p[1] for p in ring], color="#58a6ff", lw=1.3, alpha=0.65)
    ax.autoscale(); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{title}   ·   colored by {label}", color="#e6edf3", fontsize=14, pad=10)
    if source:
        fig.text(0.5, 0.012, "Source: " + source, ha="center", va="bottom", color="#8a94a3", fontsize=9)
    fig.savefig(out_png, dpi=100, facecolor="#0e1116", bbox_inches="tight"); plt.close(fig)

def kepler_map(D, label, zoom):
    # A Kepler LINE layer (from->to segments) — numeric lat/lng columns render reliably, unlike a
    # hand-built geojson layer (which Kepler silently drops to a blank Point layer).
    val, mlabel, hot_high = _metric(D)
    xs, ys, rows = [], [], []
    for L in D["links"]:
        p = L["poly"]
        if len(p) < 2:
            continue
        v = round(val(L) or 0, 2)
        for i in range(len(p) - 1):
            (x0, y0), (x1, y1) = p[i], p[i + 1]
            rows.append([round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5), v])
            xs += [x0, x1]; ys += [y0, y1]
    lon, lat = (sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (0, 0)
    fields = [{"name": n, "type": "real", "format": "", "analyzerType": "FLOAT"}
              for n in ("lng0", "lat0", "lng1", "lat1", "value")]
    ds = {"version": "v1", "data": {"id": "network", "label": label, "color": [30, 150, 190],
                                    "allData": rows, "fields": fields}}
    ramp = ["#2f9e5e", "#f5ce34", "#e6541e", "#a60d0a"] if hot_high else ["#a60d0a", "#e6541e", "#f5ce34", "#2f9e5e"]
    layer = {"id": "net", "type": "line",
             "config": {"dataId": "network", "label": mlabel,
                        "columns": {"lat0": "lat0", "lng0": "lng0", "lat1": "lat1", "lng1": "lng1"},
                        "isVisible": True,
                        "visConfig": {"opacity": 0.85, "thickness": 2.0, "colorRange":
                                      {"name": "gui4gmns", "type": "sequential", "category": "custom", "colors": ramp}}},
             "visualChannels": {"colorField": {"name": "value", "type": "real"}, "colorScale": "quantile"}}
    cfg = {"version": "v1", "config": {
        "visState": {"layers": [layer], "filters": [], "interactionConfig": {}},
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
    # geofence to a city bbox (minlon,minlat,maxlon,maxlat) — clip a subarea out of a regional network
    if "--bbox" in a:
        x0, y0, x1, y1 = map(float, a[a.index("--bbox") + 1].split(","))
        def _inb(L):
            xs = [p[0] for p in L["poly"]]; ys = [p[1] for p in L["poly"]]
            return xs and x0 <= sum(xs) / len(xs) <= x1 and y0 <= sum(ys) / len(ys) <= y1
        D["links"] = [L for L in D["links"] if _inb(L)]
        print(f"geofenced to bbox -> {len(D['links'])} links")
    boundary = None
    if "--poly" in a:  # clip to a real city boundary polygon (point-in-polygon on the link midpoint)
        boundary = load_polys(a[a.index("--poly") + 1])
        def _inp(L):
            xs = [p[0] for p in L["poly"]]; ys = [p[1] for p in L["poly"]]
            return xs and in_polys(sum(xs) / len(xs), sum(ys) / len(ys), boundary)
        D["links"] = [L for L in D["links"] if _inp(L)]
        print(f"clipped to city polygon -> {len(D['links'])} links")
    source = a[a.index("--source") + 1] if "--source" in a else ""
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
    preview_png(D, os.path.join(out, "preview.png"), f"{label} · {len(D['links']):,} links",
                source=source, boundary=boundary)
    if source:
        open(os.path.join(out, "SOURCE.txt"), "w", encoding="utf-8").write(source + "\n")
    if "--no-map" not in a and D["geo"]:
        m = kepler_map(D, label, zoom); m["info"]["source"] = source
        json.dump(m, open(os.path.join(out, "map.kepler.json"), "w"))
    mb = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out) if os.path.isfile(os.path.join(out, f))) / 1e6
    print(f"portal demo -> {out}/  ({len(D['links']):,} links, geo={D['geo']}, {mb:.1f} MB)")

if __name__ == "__main__":
    main()

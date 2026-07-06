#!/usr/bin/env python3
"""Compact network thumbnail (inline SVG) for a GMNS folder — the gallery card preview.

Mirrors the gui4gmns sample network view: links drawn between node coords, colored green(fast)->
red(slow), width by lanes, faint node dots, a small speed legend. Aspect-ratio preserved. Pure stdlib.

    from network_thumb import render
    stats = render("datasets/01_sioux_falls", "docs/dashboards/thumbs/01_sioux_falls.svg")
    # stats -> {"nodes":24,"links":76,"zones":24,"color_by":"free-flow speed","vmin":..,"vmax":..}
"""
import csv, os

# red -> orange -> yellow -> green (low speed -> high speed), matching the sample legend anchors.
RAMP = [(0.0, (166, 13, 10)), (0.34, (230, 84, 30)), (0.67, (245, 206, 52)), (1.0, (120, 195, 67))]

def _lerp(a, b, t): return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def color(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    for i in range(len(RAMP) - 1):
        t0, c0 = RAMP[i]; t1, c1 = RAMP[i + 1]
        if t <= t1:
            r, g, b = _lerp(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
            return f"#{r:02x}{g:02x}{b:02x}"
    r, g, b = RAMP[-1][1]; return f"#{r:02x}{g:02x}{b:02x}"

def _read(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def _num(s, d=None):
    try: return float(s)
    except (TypeError, ValueError): return d

def _pct(vals, q):
    if not vals: return None
    s = sorted(vals); k = max(0, min(len(s) - 1, int(q * (len(s) - 1))))
    return s[k]

def render(folder, out_svg, W=360, H=224, pad=13):
    nodes = {}
    zids = set()
    for r in _read(os.path.join(folder, "node.csv")):
        x, y = _num(r.get("x_coord")), _num(r.get("y_coord"))
        if x is not None and y is not None:
            nodes[str(r.get("node_id"))] = (x, y)
        z = str(r.get("zone_id", "")).strip()
        if z and z not in ("0", "nan", "None"): zids.add(z)
    links = _read(os.path.join(folder, "link.csv"))

    # speed source: observed mean speed from link_performance if it carries a speed column, else free_speed.
    obs = {}
    lp = _read(os.path.join(folder, "link_performance.csv"))
    if lp and "speed" in lp[0]:
        acc = {}
        for r in lp:
            v = _num(r.get("speed"))
            if v and v > 0: acc.setdefault(str(r.get("link_id")), []).append(v)
        obs = {k: sum(v) / len(v) for k, v in acc.items()}
    color_by = "mean observed speed" if obs else "free-flow speed"

    def link_val(r):
        if obs: return obs.get(str(r.get("link_id")))
        return _num(r.get("free_speed")) or _num(r.get("vdf_free_speed_mph"))

    vals = [v for v in (link_val(r) for r in links) if v is not None]
    lo, hi = (_pct(vals, 0.05), _pct(vals, 0.95)) if vals else (None, None)
    # if speed has ~no spread, color by lanes instead so the map still reads as a hierarchy.
    if lo is None or hi is None or hi - lo < 1e-6:
        color_by = "lanes"
        vals = [v for v in (_num(r.get("lanes")) for r in links) if v is not None]
        lo, hi = (_pct(vals, 0.05) or 1, _pct(vals, 0.95) or 1)
        link_val = lambda r: _num(r.get("lanes"), lo)  # noqa: E731
        if hi - lo < 1e-6: hi = lo + 1

    xs = [c[0] for c in nodes.values()]; ys = [c[1] for c in nodes.values()]
    if not xs:
        open(out_svg, "w", encoding="utf-8").write(f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#f6f7f9"/></svg>')
        return {"nodes": 0, "links": len(links), "zones": len(zids), "color_by": color_by}
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dw, dh = max(maxx - minx, 1e-9), max(maxy - miny, 1e-9)
    scale = min((W - 2 * pad) / dw, (H - 2 * pad) / dh)
    ox = (W - dw * scale) / 2 - minx * scale
    oy = (H - dh * scale) / 2 + maxy * scale  # + because we flip y
    def P(x, y): return (x * scale + ox, oy - y * scale)

    seg = []
    for r in links:
        a, b = nodes.get(str(r.get("from_node_id"))), nodes.get(str(r.get("to_node_id")))
        if not a or not b: continue
        x1, y1 = P(*a); x2, y2 = P(*b)
        v = link_val(r); t = (v - lo) / (hi - lo) if v is not None else 0.5
        ln = _num(r.get("lanes"), 1) or 1
        w = 0.7 + min(ln, 4) * 0.42
        seg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="{color(t)}" stroke-width="{w:.1f}" stroke-linecap="round"/>')
    dots = "".join(f'<circle cx="{P(x, y)[0]:.1f}" cy="{P(x, y)[1]:.1f}" r="1.1" fill="#0366d6" opacity=".35"/>'
                   for x, y in nodes.values())
    # legend: green->red gradient bar + endpoints
    unit = "" if color_by == "lanes" else " mph"
    leg = (f'<g font-family="system-ui,Arial" font-size="9" fill="#555">'
           f'<defs><linearGradient id="g"><stop offset="0" stop-color="{color(0)}"/>'
           f'<stop offset=".5" stop-color="{color(.5)}"/><stop offset="1" stop-color="{color(1)}"/></linearGradient></defs>'
           f'<rect x="{pad}" y="{H-13}" width="86" height="7" fill="url(#g)" rx="1"/>'
           f'<text x="{pad}" y="{H-15}">{color_by}</text>'
           f'<text x="{pad+90}" y="{H-7}">{lo:.0f}&#8211;{hi:.0f}{unit}</text></g>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'style="width:100%;display:block;background:#f6f7f9">{"".join(seg)}{dots}{leg}</svg>')
    os.makedirs(os.path.dirname(out_svg), exist_ok=True)
    open(out_svg, "w", encoding="utf-8").write(svg)
    return {"nodes": len(nodes), "links": sum(1 for r in links if nodes.get(str(r.get("from_node_id")))
            and nodes.get(str(r.get("to_node_id")))), "zones": len(zids), "color_by": color_by,
            "vmin": lo, "vmax": hi}

if __name__ == "__main__":
    import sys
    print(render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "thumb.svg"))

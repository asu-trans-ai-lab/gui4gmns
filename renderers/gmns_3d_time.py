#!/usr/bin/env python3
"""gui4gmns — time-dynamic 3D TMC viewer.

Turns a GMNS network + a TIME-SERIES performance feed (+ optional incident/weather events) into a
self-contained deck.gl PLAYER: a time slider that animates one corridor through an operations timeline.

Visual grammar (the same language, now over time):
  speed          -> link COLOR              (green free-flow -> red slow); a moving red front = a shockwave
  congestion     -> extrusion HEIGHT        (volume where measured, else speed-deficit "congestion wall")
  queue          -> red SPILLBACK TAIL       growing UPSTREAM from the stop line (measured queue, or speed-derived)
  incident/wx    -> pulsing EVENT MARKER      appearing at its start time with an influence zone
  timeline       -> a data-driven TMC STORY   baseline -> bottleneck activation -> worst -> recovery

Honest by construction: every frame is a real measured time bin. Nothing is invented. Where a feed lacks a
measured queue, the red tail is clearly labelled "speed-derived" (not a measured queue).

Auto-detects three feed shapes:
  A) <folder>/tmc_speed_15min.csv        (link_id,tmc,time,speed)                 + network/ subfolder   [I-95]
  B) <folder>/link_performance_15min.csv (link_id,time_bin_start,inflow_veh,queue_exb)                   [Chicago/toy]
  C) --series <csv> --network <dir>      (explicit override)
Events (optional, auto-found): gridlock_events.csv | control_event.csv | events.csv | incident.csv

    python gmns_3d_time.py <folder> "<label>" -o docs/portal_demo/tmc [--source "..."] [--zoom 12] [--maxlinks 400]
"""
import os, sys, csv, json, math, re
csv.field_size_limit(1 << 24)


# ---------------------------------------------------------------- helpers
def fnum(v, d=0.0):
    try: return float(v)
    except: return d

def norm_id(v):
    """Normalize a link/node id so joins match: numeric '1.0'->'1', '49'->'49'; keep 'L405N-002' as-is."""
    v = str(v).strip()
    try: return str(int(float(v)))
    except: return v

def tmin(s):
    """Time string -> minutes past midnight. Accepts '07:15', '0715', '0700_0800' (uses start), '7:5'."""
    s = (s or "").strip()
    if "_" in s: s = s.split("_")[0]
    if ":" in s:
        h, m = s.split(":")[:2]; return int(fnum(h)) * 60 + int(fnum(m))
    if s.isdigit() and len(s) >= 3:                       # 0715
        return int(s[:-2]) * 60 + int(s[-2:])
    return int(fnum(s)) * 60

def hhmm(m):
    return f"{int(m)//60:02d}:{int(m)%60:02d}"

def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def poly_len(line):
    return sum(math.hypot(line[i+1][0]-line[i][0], line[i+1][1]-line[i][1]) for i in range(len(line)-1))

def ribbon(pts, w, coslat):
    """Buffer a centerline into a thin polygon ring (width w in deg; lon corrected by 1/cos lat)."""
    n = len(pts); left, right = [], []
    for i in range(n):
        if i == 0: dx, dy = pts[1][0]-pts[0][0], pts[1][1]-pts[0][1]
        elif i == n-1: dx, dy = pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1]
        else: dx, dy = pts[i+1][0]-pts[i-1][0], pts[i+1][1]-pts[i-1][1]
        d = math.hypot(dx, dy) or 1e-9
        px, py = -dy/d, dx/d
        left.append([round(pts[i][0]+px*w/coslat, 6), round(pts[i][1]+py*w, 6)])
        right.append([round(pts[i][0]-px*w/coslat, 6), round(pts[i][1]-py*w, 6)])
    return left + right[::-1]


# ---------------------------------------------------------------- network
def load_network(ndir):
    nodes = {}
    for r in read_csv(os.path.join(ndir, "node.csv")):
        x = r.get("x_coord") or r.get("x") or r.get("lon") or r.get("longitude")
        y = r.get("y_coord") or r.get("y") or r.get("lat") or r.get("latitude")
        nodes[norm_id(r["node_id"])] = (fnum(x), fnum(y))
    links = {}
    for r in read_csv(os.path.join(ndir, "link.csv")):
        lid = norm_id(r["link_id"])
        pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", r.get("geometry") or "")
        line = [(float(x), float(y)) for x, y in pts] if len(pts) >= 2 else None
        if not line:
            a = nodes.get(norm_id(r["from_node_id"])); b = nodes.get(norm_id(r["to_node_id"]))
            line = [a, b] if a and b else None
        if not line: continue
        links[lid] = {"line": line,
                      "ff": fnum(r.get("free_speed") or r.get("free_speed_raw") or r.get("free_speed_kmh") or 60),
                      "lanes": max(1, fnum(r.get("lanes") or 1)),
                      "cap": fnum(r.get("capacity") or r.get("capacity_vph") or 1800)}
    return links


# ---------------------------------------------------------------- series (auto-detect feed shape)
def load_series_pems(folder):
    """PeMS corridor package: observations/speeds.csv (avg_speed_mph) + counts.csv (avg_flow_vphpl),
    5-min bins keyed by time_index (minute = time_index*5). Merged on link_id x time_index."""
    ser = {}
    for r in read_csv(os.path.join(folder, "observations", "speeds.csv")):
        lid = norm_id(r["link_id"]); m = int(fnum(r.get("time_index"))) * 5
        ser.setdefault(lid, {"speed": {}, "vol": {}, "queue": {}})["speed"][m] = fnum(r.get("avg_speed_mph"))
    cf = os.path.join(folder, "observations", "counts.csv")
    if os.path.exists(cf):
        for r in read_csv(cf):
            lid = norm_id(r["link_id"]); m = int(fnum(r.get("time_index"))) * 5
            fv = fnum(r.get("avg_flow_vphpl"))
            if fv: ser.setdefault(lid, {"speed": {}, "vol": {}, "queue": {}})["vol"][m] = fv
    return ser

def load_series_qvdf(handoff):
    """QVDF calibration handoff (handoff_avgweekday_timedependent.csv): speed_qvdf_model = the calibrated
    QVDF speed reconstruction; count_per_lane_15min -> approx per-lane hourly flow. Full weekday (both peaks)."""
    ser = {}
    for r in read_csv(handoff):
        lid = norm_id(r["link_id"]); m = int(fnum(r.get("t_min")))
        d = ser.setdefault(lid, {"speed": {}, "vol": {}, "queue": {}})
        sm = r.get("speed_qvdf_model")
        if sm not in (None, ""): d["speed"][m] = fnum(sm)
        cv = fnum(r.get("count_per_lane_15min"))
        if cv: d["vol"][m] = cv * 4                       # 15-min per-lane count -> veh/h/lane
    print(f"  series: QVDF handoff (speed_qvdf_model)  links={len(ser)}")
    return ser

def load_paq(paq):
    """daily_paq_all.csv -> per-link {dc: peak D/C, ep: [(t0,t2,t3,msr), ...]} congestion episodes (hours).
    'magnitude' column == MSR = (v_co-v_t2)/v_t2 (verified). One episode per calibrated period (AM/PM)."""
    out = {}
    if not (paq and os.path.exists(paq)): return out
    for r in read_csv(paq):
        lid = norm_id(r["link_id"])
        d = out.setdefault(lid, {"dc": 0.0, "ep": []})
        d["dc"] = max(d["dc"], fnum(r.get("DC")))
        t0, t2, t3, msr = fnum(r.get("t0")), fnum(r.get("t2")), fnum(r.get("t3")), fnum(r.get("magnitude"))
        if t3 > t0 and msr > 0: d["ep"].append((t0, t2, t3, msr))
    return out

def qvdf_queue(episodes, minute):
    """Analytical QVDF queue length at a clock minute: Q(t) ∝ (t-t0)^2·(t3-t)^2 (cubic PAQ, m=0.5; Eq. 15/
    Newell Eq. 10 family), zero outside [t0,t3], peak at t2, scaled by the episode's MSR. Max over episodes."""
    th = minute / 60.0; best = 0.0
    for t0, t2, t3, msr in episodes:
        if t0 <= th <= t3:
            peak = ((t2 - t0) * (t3 - t2)) ** 2 or 1e-9
            best = max(best, msr * ((th - t0) * (t3 - th)) ** 2 / peak)
    return best

def load_series(folder, series_arg):
    """Return (series, network_dir). series[link_id] = {'speed':{min:val}, 'vol':{...}, 'queue':{...}}."""
    ndir = os.path.join(folder, "network") if os.path.exists(os.path.join(folder, "network", "node.csv")) else folder
    if not series_arg and os.path.exists(os.path.join(folder, "observations", "speeds.csv")):
        ser = load_series_pems(folder)
        print(f"  series: observations/speeds.csv (+counts.csv)  5-min PeMS  links={len(ser)}")
        return ser, ndir, "PeMS observations (speeds+counts, 5-min)"
    if series_arg:
        path = series_arg
    elif os.path.exists(os.path.join(folder, "tmc_speed_15min.csv")):
        path = os.path.join(folder, "tmc_speed_15min.csv")
    elif os.path.exists(os.path.join(folder, "link_performance_15min.csv")):
        path = os.path.join(folder, "link_performance_15min.csv")
    else:
        sys.exit("no time-series feed found (observations/speeds.csv / tmc_speed_15min.csv / link_performance_15min.csv). Use --series.")
    rows = read_csv(path)
    hdr = rows[0].keys() if rows else []
    tcol = next((c for c in ("time", "time_bin_start", "time_period", "timestamp", "time_of_day") if c in hdr), None)
    scol = next((c for c in ("speed", "speed_mph", "avg_speed", "avg_speed_mph") if c in hdr), None)
    vcol = next((c for c in ("inflow_veh", "volume", "flow", "count", "avg_flow_vphpl") if c in hdr), None)
    qcol = next((c for c in ("queue_exb", "queue", "queue_length") if c in hdr), None)
    ser = {}
    for r in rows:
        lid = norm_id(r["link_id"]); m = tmin(r.get(tcol))
        d = ser.setdefault(lid, {"speed": {}, "vol": {}, "queue": {}})
        if scol and r.get(scol) not in (None, ""): d["speed"][m] = fnum(r[scol])
        if vcol and r.get(vcol) not in (None, ""): d["vol"][m] = fnum(r[vcol])
        if qcol and r.get(qcol) not in (None, ""): d["queue"][m] = fnum(r[qcol])
    print(f"  series: {os.path.basename(path)}  time={tcol} speed={scol} vol={vcol} queue={qcol}  links={len(ser)}")
    return ser, ndir, os.path.basename(path)


# ---------------------------------------------------------------- events (incident / weather)
def load_events(folder):
    for fn in ("gridlock_events.csv", "control_event.csv", "events.csv", "incident.csv"):
        p = os.path.join(folder, fn)
        if os.path.exists(p): return _norm_events(read_csv(p), fn)
    return [], ""

def _norm_events(rows, fn):
    ev = []
    for r in rows:
        lid = r.get("link_id") or r.get("location_id") or r.get("link")
        if lid in (None, ""): continue
        st = r.get("time") or r.get("start_time") or r.get("time_bin_start")
        en = r.get("end_time") or st
        typ = (r.get("type") or "event").replace("_", " ")
        sev = fnum(r.get("value") or r.get("severity") or r.get("parameter_value") or r.get("value") or 50)
        ev.append({"link": norm_id(lid), "t0": tmin(st), "t1": tmin(en), "type": typ, "sev": sev,
                   "note": r.get("notes") or r.get("parameter") or ""})
    print(f"  events: {fn}  ({len(ev)} events)")
    return ev, fn


# ---------------------------------------------------------------- data-driven TMC storyline
def build_narration(times, avg_ratio, events, evlinks):
    """Data-driven TMC storyline. With a speed feed: detect baseline/activation/worst/recovery from the
    real speed-ratio curve. With a volume/queue feed: a timeline note + one beat per incident event."""
    N = len(times); n = []
    if any(r is not None for r in avg_ratio):
        R = [r if r is not None else 1.0 for r in avg_ratio]
        base = sorted(R[:max(3, N//8)])[len(R[:max(3, N//8)])//2]       # early-window median
        worst_i = min(range(N), key=lambda i: R[i]); worst = R[worst_i]
        # baseline-relative thresholds: a corridor AVERAGE dilutes localized bottlenecks, so phase off the
        # drop FROM baseline, not an absolute speed (works for both strong and mild-average corridors)
        act_lvl = min(0.82, base - 0.10)
        n.append({"i": 0, "phase": "Baseline — free flow",
                  "text": f"Corridor near free-flow (~{round(base*100)}% of the peak reference speed). Detectors nominal; no active TIM."})
        act = next((i for i in range(N) if R[i] < act_lvl and R[min(i+1, N-1)] < act_lvl + 0.04 and i <= worst_i), None)
        if act is not None:
            n.append({"i": act, "phase": "Bottleneck activation",
                      "text": f"Speed breaks down at {times[act]} — capacity drop / onset of congestion. A recurrent "
                              f"queue forms; the red front propagates upstream (a shockwave moving against traffic)."})
        if base - worst > 0.12:
            n.append({"i": worst_i, "phase": "Peak congestion — spillback",
                      "text": f"Worst at {times[worst_i]} — corridor at ~{round(worst*100)}% of reference (bottleneck "
                              f"links far lower). Queue spillback extends upstream; secondary-crash risk window open. "
                              f"Candidate response: VSL harmonization, ramp metering, DMS diversion."})
        rec = next((i for i in range(worst_i, N) if R[i] > base - 0.05), None)
        if rec is not None:
            n.append({"i": rec, "phase": "Recovery — return to normal",
                      "text": f"Speed recovers by {times[rec]} — queue discharges, shockwave clears. Roadway clearance "
                              f"complete; confirm MOEs (TTI, delay) return to baseline."})
    else:
        n.append({"i": 0, "phase": "Timeline — volume & measured queue",
                  "text": "Volume/queue feed (no corridor speed). Height = volume, red tail = measured queue "
                          "spillback (queue_exb) growing upstream from the stop line. Watch queues build as events fire."})
    for e in events:
        i = min(range(N), key=lambda k: abs(tmin(times[k]) - e["t0"]))
        n.append({"i": i, "phase": f"Event — {e['type']}",
                  "text": f"{e['type'].title()} reported {times[i]} on link {e['link']} (severity {round(e['sev'])}). "
                          f"TIM phases: detection → verification → response → clearance → recovery."})
    n.sort(key=lambda x: x["i"])
    # de-dup same frame
    out = []
    for m in n:
        if out and out[-1]["i"] == m["i"]: continue
        out.append(m)
    return out


# ---------------------------------------------------------------- main
def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    folder = a[0]
    label = a[1] if len(a) > 1 and not a[1].startswith("-") else os.path.basename(folder.rstrip("/\\"))
    def opt(k, d=None): return a[a.index(k)+1] if k in a else d
    out = opt("-o", os.path.join(folder, "tmc3d"))
    zoom = float(opt("--zoom", 12))
    source = opt("--source", "")
    maxlinks = int(opt("--maxlinks", 600))
    os.makedirs(out, exist_ok=True)

    qvdf_handoff = opt("--qvdf")
    if qvdf_handoff:                                       # QVDF calibrated reconstruction mode
        ser = load_series_qvdf(qvdf_handoff)
        ndir = os.path.join(folder, "network") if os.path.exists(os.path.join(folder, "network", "node.csv")) else folder
        series_name = "QVDF reconstruction (speed_qvdf_model)"
        paq = load_paq(opt("--paq")); dc = {k: v["dc"] for k, v in paq.items()}; qmode = True
    else:
        ser, ndir, series_name = load_series(folder, opt("--series"))
        paq = {}; dc = {}; qmode = False
    net = load_network(ndir)
    events, ev_name = load_events(folder)
    evlinks = {e["link"] for e in events}

    # global time axis = union of all time keys across every measure
    tset = set()
    for d in ser.values():
        for k in ("speed", "vol", "queue"):
            tset.update(d[k].keys())
    axis = sorted(tset)
    if not axis: sys.exit("time axis empty")
    times = [hhmm(m) for m in axis]
    N = len(axis)

    def sample(dic):
        """Carry-forward sample of a {minute:value} dict onto the global axis; None until first obs."""
        if not dic: return None
        out_, last = [], None
        for m in axis:
            if m in dic: last = dic[m]
            out_.append(last)
        return out_

    # assemble per-link records (only links that have both geometry AND a series)
    def pctl(vals, q):
        s = sorted(vals); return s[max(0, min(len(s)-1, int(q*(len(s)-1))))] if s else 0
    coslat = None; recs = []
    for lid, d in ser.items():
        L = net.get(lid)
        if not L: continue
        line = L["line"]
        if coslat is None:
            coslat = max(0.2, math.cos(math.radians(line[0][1])))
        s = sample(d["speed"]); v = sample(d["vol"])
        if qmode and paq.get(lid, {}).get("ep"):          # analytical QVDF queue Q(t) on the time axis
            q = [qvdf_queue(paq[lid]["ep"], m) for m in axis]
        else:
            q = sample(d["queue"])
        # reference (free-flow) speed = 90th pctile of the link's OWN measured speed (INRIX-style,
        # unit-agnostic) — avoids km/h-vs-mph mismatch with link.csv free_speed
        ref = pctl(list(d["speed"].values()), 0.9) or L["ff"] or 60
        rank = (max((1 - (x/ref) for x in d["speed"].values()), default=0) if d["speed"]
                else max(d["vol"].values(), default=0))
        recs.append({"lid": lid, "line": line, "ff": ref, "lanes": L["lanes"],
                     "s": s, "v": v, "q": q, "rank": rank})
    if not recs: sys.exit("no links matched between series and network (check link_id join)")
    recs.sort(key=lambda r: -r["rank"])
    keep = recs[:maxlinks]; kept = {r["lid"] for r in keep}
    for r in recs[maxlinks:]:                                 # always retain links that carry an event
        if r["lid"] in evlinks and r["lid"] not in kept: keep.append(r); kept.add(r["lid"])
    recs = keep

    # center + geometry ribbons
    allpts = [p for r in recs for p in r["line"]]
    lon0 = sum(p[0] for p in allpts)/len(allpts); lat0 = sum(p[1] for p in allpts)/len(allpts)
    coslat = max(0.2, math.cos(math.radians(lat0)))
    vmax = max((max((x for x in r["v"] if x is not None), default=0) for r in recs if r["v"]), default=0) or 1
    qmax = max((max((x for x in r["q"] if x is not None), default=0) for r in recs if r["q"]), default=0)
    lidx = {r["lid"]: i for i, r in enumerate(recs)}

    links = []
    for r in recs:
        w = 0.00007 + 0.00002 * min(r["lanes"], 5)
        mid = r["line"][len(r["line"])//2]
        links.append({"poly": ribbon(r["line"], w, coslat),
                      "line": [[round(x, 6), round(y, 6)] for x, y in r["line"]],
                      "ff": round(r["ff"], 1), "lanes": r["lanes"], "lid": r["lid"],
                      "mid": [round(mid[0], 6), round(mid[1], 6)],
                      "s": [round(x, 1) if x is not None else None for x in r["s"]] if r["s"] else None,
                      "v": [round(x) if x is not None else None for x in r["v"]] if r["v"] else None,
                      "q": [round(x, 3) if x is not None else None for x in r["q"]] if r["q"] else None,
                      "dc": round(dc[r["lid"]], 1) if dc.get(r["lid"]) else None})

    # per-frame network-average speed ratio (for KPIs + storyline)
    avg_ratio = []
    for f in range(N):
        rr = [(links[i]["s"][f]/links[i]["ff"]) for i in range(len(links))
              if links[i]["s"] and links[i]["s"][f] is not None and links[i]["ff"]]
        avg_ratio.append(sum(rr)/len(rr) if rr else None)

    ev_out = []
    for e in events:
        if e["link"] in lidx:
            i0 = min(range(N), key=lambda k: abs(axis[k]-e["t0"]))
            i1 = min(range(N), key=lambda k: abs(axis[k]-e["t1"]))
            ev_out.append({"link_i": lidx[e["link"]], "i0": i0, "i1": max(i1, i0), "type": e["type"],
                           "sev": round(e["sev"]), "at": links[lidx[e["link"]]]["mid"], "note": e["note"]})

    narration = build_narration(times, avg_ratio, events, evlinks)

    n_dc = sum(1 for l in links if l["dc"])
    data = {"label": label, "source": source, "center": [round(lon0, 5), round(lat0, 5)], "zoom": zoom,
            "times": times, "vmax": round(vmax, 1), "qmax": round(qmax, 1),
            "hasV": any(l["v"] for l in links), "hasS": any(l["s"] for l in links),
            "links": links, "events": ev_out, "narration": narration,
            "avg_ratio": [round(r, 3) if r is not None else None for r in avg_ratio],
            "feed": series_name, "events_feed": ev_name,
            "mode": "qvdf" if qmode else "obs",
            "qlabel": ("■ red tail = QVDF queue Q(t) ∝ (t−t₀)²(t₃−t)² — analytical, calibrated (D/C on hover)"
                       if qmode else "")}
    json.dump(data, open(os.path.join(out, "frames.json"), "w"))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(
        HTML.replace("__LON__", f"{lon0:.5f}").replace("__LAT__", f"{lat0:.5f}")
            .replace("__ZOOM__", str(zoom)).replace("__LABEL__", label)
            .replace("__SRC__", source or "GMNS").replace("__QMEAS__", "1" if qmax > 0 else "0"))
    if source:
        open(os.path.join(out, "SOURCE.txt"), "w", encoding="utf-8").write(source + "\n")
    print(f"tmc 3d -> {out}/  ({len(links)} links, {N} time bins {times[0]}-{times[-1]}, "
          f"{len(ev_out)} events, {len(narration)} story beats, queue={'measured' if qmax>0 else 'speed-derived'})")


HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>GMNS 3D TMC — __LABEL__</title>
<script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
<style>
 html,body{margin:0;height:100%;width:100%;background:#0e1116;overflow:hidden;font:13px system-ui,Segoe UI,Arial;color:#e6edf3}
 #map{position:absolute;inset:0}
 .p{position:absolute;z-index:5;background:rgba(18,23,29,.92);border:1px solid #2b333d;border-radius:10px;padding:10px 13px}
 #hdr{top:12px;left:12px;max-width:300px} #hdr b span{color:#58a6ff} #hdr .s{color:#9aa7bd;font-size:11.5px;margin-top:3px;line-height:1.45}
 #story{top:12px;right:12px;width:270px} #story .ph{color:#ffb454;font-weight:600;font-size:13px}
 #story .tx{color:#c3ccd8;font-size:12px;margin-top:4px;line-height:1.5} #story .clk{color:#58a6ff;font-variant-numeric:tabular-nums;font-size:12px}
 #kpi{bottom:86px;right:12px;display:flex;gap:8px} .k{background:rgba(18,23,29,.92);border:1px solid #2b333d;border-radius:9px;padding:7px 11px;text-align:center;min-width:70px}
 .k b{display:block;font-size:18px} .k span{color:#9aa7bd;font-size:10.5px}
 #leg{bottom:86px;left:12px;font-size:12px} #leg .bar{height:9px;width:150px;border-radius:2px;margin:5px 0 3px;
   background:linear-gradient(90deg,rgb(166,13,10),rgb(230,84,30),rgb(245,206,52),rgb(47,158,94))}
 #leg .e{display:flex;justify-content:space-between;color:#9aa7bd;font-size:11px} #leg .q{color:#ff5a4d;margin-top:6px}
 #ctl{bottom:14px;left:12px;right:12px;display:flex;align-items:center;gap:12px}
 #ctl button{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:7px 15px;font-size:14px;cursor:pointer}
 #ctl input[type=range]{flex:1;accent-color:#58a6ff} #ctl .clk{font-variant-numeric:tabular-nums;min-width:52px;font-size:15px;color:#e6edf3}
 #ctl select{background:#2b333d;color:#c3ccd8;border:1px solid #39424d;border-radius:6px;padding:5px 8px}
 #src{position:absolute;bottom:52px;right:14px;z-index:5;color:#9aa7bd;font-size:11px}
 .mk{margin-top:6px;height:5px;position:relative;background:#222c36;border-radius:3px} .mk i{position:absolute;top:-1px;width:2px;height:7px;background:#ffb454}
</style></head><body>
<div id="map"></div>
<div class="p" id="hdr"><b><span>gui4gmns</span> · 3D TMC — __LABEL__</b>
  <div class="s"><b>height</b> = congestion · <b>color</b> = speed (green→red) · <b>red tail</b> = queue spillback.
  Drag to orbit. A moving red front is a shockwave. Composite over an OpenCities 3D city base for the full scene.</div></div>
<div class="p" id="story"><div class="clk" id="clk2">—</div><div class="ph" id="ph">—</div><div class="tx" id="tx">—</div>
  <div class="mk" id="mk"></div></div>
<div id="kpi">
  <div class="k"><b id="kavg">—</b><span id="kL1">avg speed %</span></div>
  <div class="k"><b id="kcong">—</b><span id="kL2">congested</span></div>
  <div class="k"><b id="kev">0</b><span>active events</span></div></div>
<div class="p" id="leg"><span id="legTitle">speed (green free-flow → red slow)</span><div class="bar" id="legBar"></div>
  <div class="e"><span id="legLo">slow</span><span id="legHi">free-flow</span></div>
  <div class="q" id="legQ">■ red tail = queue spillback</div></div>
<div id="src">Source: __SRC__ · basemap © OpenStreetMap</div>
<div class="p" id="ctl"><button id="play">▶</button><span class="clk" id="clk">—</span>
  <input type="range" id="slider" min="0" value="0"><label style="color:#9aa7bd">speed</label>
  <select id="spd"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option><option value="8">8×</option></select></div>
<script>
const {DeckGL,PolygonLayer,PathLayer,TileLayer,BitmapLayer,ScatterplotLayer}=deck;
const QMEAS=__QMEAS__;
fetch('frames.json').then(r=>r.json()).then(D=>{
  const N=D.times.length; let f=0, playing=false, tick=0;
  const HAS_V=D.hasV, MAXH=520, BASE=4;
  const val=(arr)=>arr&&arr[f]!=null?arr[f]:null;
  const ratio=d=>{const s=val(d.s); return (s!=null&&d.ff)?Math.max(0,Math.min(1.3,s/d.ff)):null;};
  // speed ramp: r high (fast) -> green ; low -> red
  function rampSpeed(r){const t=Math.max(0,Math.min(1,(r-0.3)/0.6));  // 0.3..0.9 -> 0..1
    const S=[[166,13,10],[230,84,30],[245,206,52],[47,158,94]],s=t*3,i=Math.min(2,Math.floor(s)),fr=s-i,a=S[i],b=S[i+1];
    return a.map((v,k)=>Math.round(v+(b[k]-v)*fr));}
  function rampVol(t){t=Math.max(0,Math.min(1,t));const S=[[47,158,94],[245,206,52],[230,84,30],[166,13,10]],
    s=t*3,i=Math.min(2,Math.floor(s)),fr=s-i,a=S[i],b=S[i+1];return a.map((v,k)=>Math.round(v+(b[k]-v)*fr));}
  function color(d){const r=ratio(d); if(r!=null)return rampSpeed(r);
    const v=val(d.v); return rampVol(v!=null&&D.vmax?Math.min(1,v/D.vmax):0);}
  function height(d){const v=val(d.v); if(HAS_V&&v!=null&&D.vmax)return BASE+(v/D.vmax)*MAXH;
    const r=ratio(d); if(r!=null)return BASE+(1-Math.min(1,r))*MAXH; return BASE;}
  function qfrac(d){const q=val(d.q); if(q!=null&&D.qmax)return Math.min(1,q/D.qmax);
    const r=ratio(d); if(r!=null)return Math.max(0,Math.min(1,(0.82-r)/0.5)); return 0;}
  // tail(line,frac): sub-path covering the last `frac` of length, from the downstream (to_node) end
  function tail(line,frac){const tot=len(line)*frac; if(tot<=0)return null; let acc=0,out=[line[line.length-1]];
    for(let i=line.length-1;i>0;i--){const seg=Math.hypot(line[i][0]-line[i-1][0],line[i][1]-line[i-1][1]);
      if(acc+seg>=tot){const t=(tot-acc)/seg;out.push([line[i][0]+(line[i-1][0]-line[i][0])*t,line[i][1]+(line[i-1][1]-line[i][1])*t]);return out;}
      acc+=seg;out.push(line[i-1]);} return out;}
  function len(line){let s=0;for(let i=0;i<line.length-1;i++)s+=Math.hypot(line[i+1][0]-line[i][0],line[i+1][1]-line[i][1]);return s;}

  const osm=new TileLayer({data:'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',minZoom:0,maxZoom:19,tileSize:256,
    renderSubLayers:p=>{const{west,south,east,north}=p.tile.bbox;return new BitmapLayer(p,{data:null,image:p.data,bounds:[west,south,east,north]});}});
  const deckgl=new DeckGL({container:'map',
    initialViewState:{longitude:__LON__,latitude:__LAT__,zoom:__ZOOM__,pitch:54,bearing:16},controller:true,
    getTooltip:({object})=>object&&object.lid&&{html:`link <b>${object.lid}</b> · speed <b>${val(object.s)??'–'}</b> · ff ${object.ff}${object.dc?' · D/C <b>'+object.dc+'</b>':''}`,
      style:{background:'rgba(0,0,0,.8)',color:'#fff',fontSize:'12px',borderRadius:'4px'}}});

  function draw(){
    const netL=new PolygonLayer({id:'net',data:D.links,extruded:true,pickable:true,
      getPolygon:d=>d.poly,getElevation:height,getFillColor:color,opacity:0.9,
      material:{ambient:0.65,diffuse:0.6,shininess:12},updateTriggers:{getElevation:f,getFillColor:f}});
    const qd=D.links.map(d=>({t:tail(d.line,qfrac(d)),sev:qfrac(d)})).filter(x=>x.t&&x.sev>0.05);
    const qL=new PathLayer({id:'q',data:qd,getPath:d=>d.t,getColor:[255,60,45],
      getWidth:d=>3+7*d.sev,widthUnits:'pixels',capRounded:true,updateTriggers:{getPath:f,getWidth:f}});
    const active=D.events.filter(e=>f>=e.i0&&f<=e.i1);
    const evL=new ScatterplotLayer({id:'ev',data:active,getPosition:e=>e.at,
      getRadius:e=>120+90*Math.sin(tick/6),radiusUnits:'meters',getFillColor:[255,70,50,140],
      getLineColor:[255,180,60],lineWidthMinPixels:2,stroked:true,updateTriggers:{getRadius:tick}});
    deckgl.setProps({layers:[osm,netL,qL,evL]});
  }
  function kpis(){
    document.getElementById('kev').textContent=D.events.filter(e=>f>=e.i0&&f<=e.i1).length;
    const rs=D.links.map(ratio).filter(r=>r!=null);
    if(rs.length){                                   // speed feed
      const avg=Math.round(rs.reduce((a,b)=>a+b)/rs.length*100);
      const cong=Math.round(100*rs.filter(r=>r<0.7).length/rs.length);
      document.getElementById('kavg').textContent=avg+'%';
      document.getElementById('kcong').textContent=cong+'%';
      document.getElementById('kavg').style.color=avg<70?'#ff5a4d':avg<88?'#ffb454':'#57d98c';
    }else{                                            // volume / queue feed
      const load=D.links.map(d=>val(d.v)).filter(v=>v!=null);
      const avgv=load.length?Math.round(load.reduce((a,b)=>a+b)/load.length):'–';
      const qd=D.links.filter(d=>{const q=val(d.q);return q!=null&&q>0;}).length;
      document.getElementById('kavg').textContent=avgv;
      document.getElementById('kcong').textContent=qd;
      document.getElementById('kavg').style.color=qd>0?'#ffb454':'#57d98c';
    }
  }
  // storyline: latest beat at or before f
  const beats=D.narration;
  function story(){let b=beats[0];for(const x of beats)if(x.i<=f)b=x;
    document.getElementById('ph').textContent=b?b.phase:'—';
    document.getElementById('tx').textContent=b?b.text:'';}
  const mk=document.getElementById('mk');
  beats.forEach(b=>{const i=document.createElement('i');i.style.left=(100*b.i/(N-1))+'%';i.title=b.phase;mk.appendChild(i);});

  const slider=document.getElementById('slider'); slider.max=N-1;
  function setClk(){const t=D.times[f];document.getElementById('clk').textContent=t;document.getElementById('clk2').textContent='⏱ '+t;}
  function frame(){setClk();draw();kpis();story();slider.value=f;}
  slider.oninput=e=>{f=+e.target.value;frame();};
  document.getElementById('play').onclick=function(){playing=!playing;this.textContent=playing?'⏸':'▶';};
  const spd=document.getElementById('spd');
  // adapt legend + KPI labels to the feed (speed vs volume/queue)
  if(!D.hasS){
    document.getElementById('legTitle').textContent='volume (green low → red high)';
    document.getElementById('legBar').style.background='linear-gradient(90deg,rgb(47,158,94),rgb(245,206,52),rgb(230,84,30),rgb(166,13,10))';
    document.getElementById('legLo').textContent='low'; document.getElementById('legHi').textContent='high';
    document.getElementById('kL1').textContent='avg volume'; document.getElementById('kL2').textContent='queued links';
  }
  document.getElementById('legQ').textContent=D.qlabel||(QMEAS?'■ red tail = measured queue spillback (queue_exb)':'■ red tail = speed-derived congestion (no measured queue)');
  if(D.mode==='qvdf')document.querySelector('#hdr .s').innerHTML+=' <b style="color:#ffb454">QVDF model</b> — speed is the calibrated QVDF reconstruction from the inflow demand-to-capacity ratio; hover a link for its <b>D/C</b>.';
  setInterval(()=>{tick++;if(playing){if(tick%(9-2*Math.log2(+spd.value))<1){f=(f+1)%N;frame();}}else draw();},70);
  frame();
});
</script></body></html>"""

if __name__ == "__main__":
    main()

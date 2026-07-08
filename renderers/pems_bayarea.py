#!/usr/bin/env python3
"""Build a single-corridor GMNS package from Caltrans PeMS D4 (Bay Area) + CHP incidents, for the
time-dynamic 3D TMC viewer (gmns_3d_time.py). All inputs are PUBLIC (Caltrans PeMS / CHP).

Given a freeway + direction + date, it:
  1. reads the PeMS station metadata (ML stations on that freeway/direction, lat/lon, postmile, lanes),
  2. chains them by absolute postmile into a corridor (nodes = stations, links = consecutive segments,
     oriented along the travel direction),
  3. pulls that day's 5-min speed+flow for those stations from station_5min_am_extract.csv,
  4. attaches the day's CHP incident(s) on that freeway/direction as events (mapped to the nearest link),
  5. writes node.csv / link.csv / series.csv / events.csv.

    python pems_bayarea.py <pems_root> <fwy> <dir> <YYYY_MM_DD> -o <out>
e.g. python pems_bayarea.py <root> 880 N 2026_04_21 -o docs/portal_demo/bayarea_tmc
"""
import os, sys, csv, glob, gzip, io, zipfile, math

def fnum(v, d=0.0):
    try: return float(v)
    except: return d

def meta_stations(root, fwy, drc):
    """ML stations on (fwy, dir): {id: (abs_pm, lon, lat, lanes)} from the latest d04 meta file."""
    metas = sorted(glob.glob(os.path.join(root, "meta", "*", "d04", "d04_text_meta_*.txt")))
    if not metas: sys.exit("no d04 meta file found under meta/*/d04/")
    out = {}
    with open(metas[-1], encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f, delimiter="\t"); next(rd, None)
        for r in rd:
            if len(r) < 13 or r[1] != str(fwy) or r[2] != drc or r[11] != "ML": continue
            sid = r[0].strip(); lat, lon = fnum(r[8]), fnum(r[9])
            if lat == 0 or lon == 0: continue
            out[sid] = (fnum(r[7]), lon, lat, max(1, int(fnum(r[12]) or 1)))
    return out, os.path.basename(metas[-1])

def read_5min(root, date_us, station_set):
    """{station: {hhmm: (speed, flow)}} for the given date (YYYY-MM-DD) and station subset."""
    path = os.path.join(root, "station_5min_am_extract.csv")
    d_iso = date_us.replace("_", "-")
    ser = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if r["date"] != d_iso: continue
            sid = r["station"].strip()
            if sid not in station_set: continue
            sp = r.get("speed"); fl = r.get("flow")
            if sp in (None, ""): continue
            ser.setdefault(sid, {})[r["time"]] = (fnum(sp), fnum(fl))
    return ser

def read_incidents(root, date_us, fwy, drc):
    """CHP incidents on (fwy, dir) for the date: list of (hhmm, abs_pm, lat, lon, dur_min, desc)."""
    zp = os.path.join(root, "chp_incidents_day", "2026", "all",
                      f"all_text_chp_incidents_day_{date_us}.txt.zip")
    if not os.path.exists(zp): return []
    with zipfile.ZipFile(zp) as z:
        mem = [n for n in z.namelist() if "incident_day" in n and "det" not in n]
        if not mem: return []
        raw = gzip.decompress(z.read(mem[0])).decode("utf-8", "ignore")
    ev = []
    for r in csv.reader(io.StringIO(raw)):
        if len(r) < 20 or r[11] != "4" or r[14] != str(fwy) or r[15] != drc: continue
        ts = r[3]
        try: hh, mm = int(ts[11:13]), int(ts[14:16])
        except: continue
        if not (6 <= hh < 11): continue                        # match the AM series window
        ev.append((f"{hh:02d}:{mm:02d}", fnum(r[17]), fnum(r[9]), fnum(r[10]),
                   int(fnum(r[19])), (r[4] or "").split("-", 1)[-1][:32]))
    return ev

def main():
    a = sys.argv[1:]
    if len(a) < 4: sys.exit(__doc__)
    root, fwy, drc, date_us = a[0], a[1], a[2], a[3]
    out = a[a.index("-o") + 1] if "-o" in a else f"bayarea_{fwy}{drc}"
    os.makedirs(out, exist_ok=True)

    st, meta_name = meta_stations(root, fwy, drc)
    if len(st) < 3: sys.exit(f"only {len(st)} ML stations on {fwy}{drc} — pick another corridor")
    order = sorted(st, key=lambda s: st[s][0])                 # by absolute postmile (ascending)
    if drc in ("S", "W"): order = order[::-1]                  # orient along travel direction
    print(f"  meta: {meta_name}  ML stations on {fwy}{drc}: {len(order)}")

    ser = read_5min(root, date_us, set(st))
    print(f"  5-min: {sum(len(v) for v in ser.values())} readings on {date_us.replace('_','-')} "
          f"across {len(ser)} stations")

    # nodes
    with open(os.path.join(out, "node.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["node_id", "x_coord", "y_coord", "zone_id"])
        for s in order: w.writerow([s, round(st[s][1], 6), round(st[s][2], 6), ""])

    # links (consecutive stations along travel direction) + geometry
    links = []
    with open(os.path.join(out, "link.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["link_id", "from_node_id", "to_node_id", "lanes",
                                       "free_speed", "capacity", "geometry"])
        for i in range(len(order) - 1):
            a1, b1 = order[i], order[i + 1]
            lanes = max(st[a1][3], st[b1][3])
            geo = f"LINESTRING ({st[a1][1]} {st[a1][2]}, {st[b1][1]} {st[b1][2]})"
            lid = i + 1
            w.writerow([lid, a1, b1, lanes, 65, 2000 * lanes, geo])
            links.append((lid, a1, b1, st[a1][0], st[b1][0]))

    # series: each link gets the mean of its two endpoint stations' speed/flow per 5-min bin
    times = sorted({t for v in ser.values() for t in v})
    with open(os.path.join(out, "series.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["link_id", "time", "speed", "volume"])
        for lid, a1, b1, _, _ in links:
            for t in times:
                vals = [ser[s][t] for s in (a1, b1) if s in ser and t in ser[s]]
                if not vals: continue
                sp = sum(v[0] for v in vals) / len(vals); fl = sum(v[1] for v in vals) / len(vals)
                w.writerow([lid, t, round(sp, 1), round(fl, 1)])

    # events: CHP incidents mapped to the nearest link by postmile midpoint
    inc = read_incidents(root, date_us, fwy, drc)
    with open(os.path.join(out, "events.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["link_id", "time", "end_time", "type", "value"])
        for hhmm, pm, lat, lon, dur, desc in inc:
            best = min(links, key=lambda L: abs((L[3] + L[4]) / 2 - pm))
            eh = (int(hhmm[:2]) * 60 + int(hhmm[3:]) + dur)
            w.writerow([best[0], hhmm, f"{(eh//60)%24:02d}:{eh%60:02d}",
                        desc.strip() or "collision", dur])
    print(f"  incidents on {fwy}{drc}: {len(inc)}  ->  {out}/  (node.csv, link.csv, series.csv, events.csv)")

if __name__ == "__main__":
    main()

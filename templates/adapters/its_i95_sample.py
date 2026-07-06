#!/usr/bin/env python3
"""ITS I-95 (VA) data-hub adapter — extract a small, all-layers sample from the 2.3 GB source.

Streams the big files (trajs 1.96 GB, waypoints 209 MB) line-by-line so nothing large is held in
memory, and writes a compact multi-layer sample that keeps EVERY data source:

  network (copy) · tmc_speed_15min · sensor_points + sensor_15min · trips (probe trajectories on links)
  · waypoints (downsampled GPS breadcrumbs) · od (top probe OD pairs)

Usage: python its_i95_sample.py <src_dir> <out_dir> [--trips 300] [--day 2024-08-05] [--wp-every 180]
"""
import csv, os, sys, re
csv.field_size_limit(1 << 24)

def fnum(v):
    try: return float(v)
    except: return 0.0
def bin15(hhmm_min): return hhmm_min - hhmm_min % 15

def main():
    a = sys.argv[1:]
    src, out = a[0], a[1]
    trips_n = int(a[a.index("--trips")+1]) if "--trips" in a else 300
    day = a[a.index("--day")+1] if "--day" in a else "2024-08-05"
    wp_every = int(a[a.index("--wp-every")+1]) if "--wp-every" in a else 180
    os.makedirs(out, exist_ok=True)
    os.makedirs(out+"/network", exist_ok=True)
    import shutil

    # ---- 1. network: copy node/link + crosswalks (tiny) ----
    for f in ["node.csv", "link.csv", "SegmentId_to_link.csv", "tmc_to_link.csv", "zone_name_to_link.csv"]:
        p = src+"/network/"+f
        if os.path.exists(p): shutil.copy(p, out+"/network/"+f)
    # link geometry: midpoint per link for point-joins, + keep full geometry
    linkgeo = {}; linkmid = {}
    for r in csv.DictReader(open(src+"/network/link.csv", encoding="utf-8-sig")):
        g = r.get("geometry") or ""
        pts = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", g)
        if pts:
            linkgeo[r["link_id"]] = [(float(x), float(y)) for x, y in pts]
            m = pts[len(pts)//2]; linkmid[r["link_id"]] = (float(m[0]), float(m[1]))
    print(f"network: {len(linkgeo)} links with geometry")

    # ---- 2. TMC speed -> per-link 15-min speed for one day ----
    tmc2link = {}
    for r in csv.DictReader(open(src+"/network/tmc_to_link.csv", encoding="utf-8-sig")):
        tmc = (r.get("tmc") or r.get("﻿tmc") or "").strip()
        ids = [x for x in (r.get("link_ids") or "").split(";") if x.strip()]
        if tmc and ids: tmc2link[tmc] = ids
    agg = {}   # (tmc, binmin) -> [sum_speed, n]
    with open(src+"/tmc_speed/Readings.csv", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        for r in rd:
            ts = r.get("measurement_tstamp") or ""
            if not ts.startswith(day): continue
            m = re.search(r"(\d{2}):(\d{2})", ts)
            if not m: continue
            bm = bin15(int(m[1])*60+int(m[2]))
            k = (r["tmc_code"], bm); s = fnum(r.get("speed"))
            if s > 0:
                agg.setdefault(k, [0.0, 0]); agg[k][0] += s; agg[k][1] += 1
    with open(out+"/tmc_speed_15min.csv", "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["link_id", "tmc", "time", "speed"])
        n = 0
        for (tmc, bm), (ss, c) in sorted(agg.items()):
            for lid in tmc2link.get(tmc, []):
                w.writerow([lid, tmc, f"{bm//60:02d}:{bm%60:02d}", round(ss/c, 1)]); n += 1
    print(f"tmc_speed_15min: {n} link-bin rows ({day})")

    # ---- 3. sensors: points + per-station 15-min speed/volume/occupancy for one day ----
    inv = {}
    for r in csv.DictReader(open(src+"/sensor/Inventory.csv", encoding="utf-8-sig")):
        inv[r["zone_id"]] = r
    with open(out+"/sensor_points.csv", "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["zone_id", "road", "direction", "lane_type", "latitude", "longitude", "bearing"])
        for z, r in inv.items():
            w.writerow([z, r.get("road"), r.get("direction"), r.get("lane_type"),
                        r.get("latitude"), r.get("longitude"), r.get("bearing")])
    sagg = {}  # (zone, binmin) -> [spd_sum, vol_sum, occ_sum, n]
    with open(src+"/sensor/lane_readings.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ts = r.get("measurement_start") or ""
            if not ts.startswith(day): continue
            m = re.search(r"(\d{2}):(\d{2})", ts)
            if not m: continue
            bm = bin15(int(m[1])*60+int(m[2])); k = (r["zone_id"], bm)
            sagg.setdefault(k, [0.0, 0.0, 0.0, 0])
            sagg[k][0] += fnum(r.get("speed")); sagg[k][1] += fnum(r.get("volume"))
            sagg[k][2] += fnum(r.get("occupancy")); sagg[k][3] += 1
    with open(out+"/sensor_15min.csv", "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["zone_id", "time", "speed", "volume", "occupancy"])
        for (z, bm), (s, v, o, c) in sorted(sagg.items()):
            w.writerow([z, f"{bm//60:02d}:{bm%60:02d}", round(s/c, 1), round(v, 0), round(o/c, 1)])
    print(f"sensor: {len(inv)} stations, {len(sagg)} station-bins ({day})")

    # ---- 4. probe trajectories: first N trips -> ordered link path + crossing times ----
    seg2link = {}
    for r in csv.DictReader(open(src+"/network/SegmentId_to_link.csv", encoding="utf-8-sig")):
        seg2link[r["SegmentId"]] = r["link_id"]
    H = ["TripId","DeviceId","ProviderId","TripTimezone","TrajIdx","TrajRawDistanceM","TrajRawDurationMillis",
         "SegmentId","SegmentIdx","LengthM","CrossingStartOffsetM","CrossingEndOffsetM",
         "CrossingStartDateUtc","CrossingEndDateUtc"]
    trips = {}   # tripid -> list of (segidx, link_id, start, end)
    seen = []
    with open(src+"/trip_path/trajs.csv", encoding="utf-8-sig") as f:
        for line in f:
            row = next(csv.reader([line]))
            if len(row) < 14: continue
            tid = row[0]
            if tid not in trips:
                if len(seen) >= trips_n: break
                seen.append(tid); trips[tid] = []
            lid = seg2link.get(row[7])
            if lid:
                trips[tid].append((fnum(row[8]), lid, row[12][:19], row[13][:19]))
    with open(out+"/trips.csv", "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["trip_id", "link_ids", "t_start", "t_end", "n_links"])
        for i, (tid, segs) in enumerate(trips.items()):
            segs.sort()
            lids = [s[1] for s in segs]
            if not lids: continue
            w.writerow([i, ";".join(lids), segs[0][2], segs[-1][3], len(lids)])
    print(f"trips: {len([t for t in trips.values() if t])} probe trajectories (of {trips_n} requested)")

    # ---- 5. waypoints: downsample GPS breadcrumbs ----
    kept = 0
    with open(src+"/waypoint/waypoint.csv", encoding="utf-8-sig") as f, \
         open(out+"/waypoints.csv", "w", newline="") as fo:
        rd = csv.DictReader(f); w = csv.writer(fo)
        w.writerow(["journey_id", "t_unix", "latitude", "longitude", "speed_mph", "heading"])
        for i, r in enumerate(rd):
            if i % wp_every: continue
            w.writerow([(r.get("journey_id") or "")[:8], r.get("capture_time"), r.get("latitude"),
                        r.get("longitude"), r.get("speed_mph"), r.get("heading_deg_north")])
            kept += 1
    print(f"waypoints: {kept} downsampled points (every {wp_every})")

    # ---- 6. OD: top probe OD pairs (with zone->link->coord where available) ----
    zone_mid = {}
    for r in csv.DictReader(open(src+"/network/zone_name_to_link.csv", encoding="utf-8-sig")):
        lid = r.get("link_id")
        if lid in linkmid: zone_mid[(r.get("Zone Name") or "").strip()] = linkmid[lid]
    od = {}
    for r in csv.DictReader(open(src+"/probe_od/od.csv", encoding="utf-8-sig")):
        o = (r.get("Origin Zone Name") or "").strip(); d = (r.get("Destination Zone Name") or "").strip()
        v = fnum(r.get("Average Daily O-D Traffic (StL Volume)"))
        if v > 0 and o and d and o != d: od[(o, d)] = od.get((o, d), 0) + v
    top = sorted(od.items(), key=lambda kv: -kv[1])[:300]
    with open(out+"/od.csv", "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["o_zone", "d_zone", "volume", "o_lon", "o_lat", "d_lon", "d_lat"])
        for (o, d), v in top:
            om, dm = zone_mid.get(o), zone_mid.get(d)
            w.writerow([o, d, round(v, 0),
                        om[0] if om else "", om[1] if om else "", dm[0] if dm else "", dm[1] if dm else ""])
    print(f"od: {len(od)} pairs, top {len(top)} written")

    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(out) for f in fs)
    print(f"\nSAMPLE total: {tot/1e6:.1f} MB  (from 2.3 GB source)")

if __name__ == "__main__":
    main()

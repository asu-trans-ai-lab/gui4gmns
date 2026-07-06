# gui4gmns AI-Gen — the visualization schema (build your own dashboard engine)

**The master flow:** keep ONE GMNS master package per scenario/run. Never "open files in a viewer" —
run the generator (or ask an AI to) and get a double-clickable, self-contained `dashboard.html` with the
data embedded and pre-checked:

```bash
python ai-gen/gui4gmns.py <gmns_folder> [--max-traj 2000]     # -> <folder>/dashboard.html
```

## 1. The embedded data schema (`const DATA = {...}` inside every dashboard)
```jsonc
{
  "meta":  { "folder": "...", "geo": true, "checks": ["preprocessing/data-quality lines..."] },
  "nodes": [[node_id, x, y, is_zone], ...],
  "links": [[link_id, [[x,y],...], volume, max_queue, capacity_total_hr, length_mi], ...],
  "bins":  ["07:00","07:15",...],                       // 15-min time bins
  "td":    { "<link_id>": { "<bin_idx>": [inflow, queue] } },
  "trajs": { "<agent_id>": [[time_min, link_id, "ENB|EXB"], ...] },   // event list = trajectory
  "paths": [[volume, [link_id,...]], ...],
  "run":   { "engine","agents","conserved","vmt_veh_mi","gridlock":{...} },   // run_summary.json verbatim
  "corridor": {            // from corridor_speed.csv — INRIX observed vs QVDF model, space-time
    "<name>": { "seq":[...], "bins":["05:00",...], "dist":{seq:cum_mi},
                "cells":{seq:{bin:[speed_inrix, speed_qvdf]}}, "ff":free_flow,
                "val":{"n","rmse","r2","bias","ff"} } }
}
```
Time-dependent SPEED: `link_performance_15min.csv` may carry `speed` (+`free_flow`) columns (e.g. QVDF
output) — then `td[link][bin] = [inflow, queue, speed, free_flow]` and the `speed` MOE mode colors the
map by speed/free-flow (green free-flow → red breakdown). Corridor input `corridor_speed.csv` columns:
`corridor, seq, cum_dist_mi, length_mi, t_min, time, speed_inrix, speed_qvdf, free_flow`.
Preprocessing guarantees: coordinates in lon/lat when `meta.geo` (CRS handled via `crs.txt` EPSG),
mercator-ready; trajectories subsampled; every anomaly reported in `meta.checks` (missing MOE, failed
conservation, oversaturation, geometry gaps) — **the dashboard always shows its own data-quality audit.**

## 2. Section catalog (compose any subset)
| block | inputs | reference implementation |
|---|---|---|
| KPI cards | links, run | `gui4gmns.py` template (`.kpi`) |
| network map + MOE color/bandwidth (volume, V/C, queue, TD) | links, td | canvas renderer in template |
| OSM basemap | meta.geo | tile loader (`loadTiles`) — online only, degrades gracefully |
| animation clock + vehicle dots | trajs, bins | `draw()` interpolation (green moving / red queued) |
| data-quality footer | meta.checks | `#checks` |
| charts (cumulative curves, delay, comparisons) | td, trajs | see `html_examples/apache_*.html` for style |

## 3. AI-guided generation (the "master AI" interface)
To have an AI build a **custom** dashboard (comparison views, teaching cases, physics checks like the
Apache Blvd examples), give it this prompt skeleton:

> You are generating a self-contained HTML dashboard. The data is embedded as `const DATA = {...}`
> following the schema in gui4gmns `ai-gen/VIZ_SCHEMA.md` (paste §1). Style: dark theme, KPI cards,
> canvas map with green→yellow→red MOE ramp, OSM tiles when `meta.geo`, animation slider, and always
> render `meta.checks` as a data-audit footer. Build me: [DESCRIBE THE VIEW — e.g. "a side-by-side
> before/after ODME comparison with a screenline obs-vs-sim bar chart", "a signal-timing teaching case
> with cumulative arrival/departure curves"]. No external libraries except OSM tile requests.

The generator emits the data block; the AI writes the view. `html_examples/` is the style gallery
(Apache corridor simulators, four-step dashboards, digital-twin labs) showing where this goes:
physics-informed checks, side-by-side scenario comparison, seeded-RNG experiments.

## 4. Generated so far
`datasets/02_chicago_sketch/dashboard.html` (1.4 MB: MOE + 26 bins + 1,500 vehicles + run/gridlock KPIs) ·
`datasets/05_toy_merge/dashboard.html` (30 KB; correctly warns "no MOE") ·
`datasets/04_arc_atlanta/dashboard.html` (25.6 MB; 145,971 links reprojected EPSG:2240, static MOE).

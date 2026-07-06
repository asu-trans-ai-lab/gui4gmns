# MOE gallery — static PNGs for offline docs (no screen-copying)

Publication-quality PNGs of the key MOEs, rendered with `renderers/moe_static.py` (matplotlib, proper
labels/legends/colorbars). Drop these straight into reports, slides, or papers — no screenshot needed.

```bash
python renderers/moe_static.py <gmns_folder> -o docs/moe_gallery --moe all
#   --moe bandwidth | spacetime | all     --links "1;2;3" (explicit corridor)
```

| file | MOE | encoding | needs |
|---|---|---|---|
| `moe_traffic_speed_bandwidth.png` | Traffic Speed | **width = link volume/hr**, **color = speed / free-flow** (green→red) | `link.csv` + `link_performance.csv` |
| `moe_spacetime_speed.png` | Dynamic Speed Contour | distance-along-corridor (y) × time-of-day (x), color = speed (mph) | `link_performance_15min.csv` (speed, or inflow→BPR) + a corridor |
| `moe_spacetime_density.png` | Density Contour | same axes, color = density k = flow/speed (veh/mi/lane) | same |

The corridor for the space-time plots is auto-picked as the busiest path in `path_flow.csv`, or set it
explicitly with `--links`. Time-dependent speed is used directly when present (QVDF/TMC), else derived
from 15-min inflow via BPR(0.15,4) + queue delay — so even flow-only semi-dynamic results give a
space-time picture. This is the modern replacement for the old gnuplot corridor plots.

Current gallery is Chicago Sketch (public). On a congested corridor (e.g. a QVDF I-395 speed field) the
space-time plot shows the classic red breakdown band; here it stays green because the sketch path is
uncongested and its static speed = free-flow.

Review of these figures against visualization best practice: `../TRB_VIZ_REVIEW.md` (colorblind-safe
colormaps, provenance stamps, and density/flow trio are the queued improvements — roadmap E9–E11).


## Tested on large / real networks (2026-07)
- **ARC Atlanta (145,971 links)** — `moe_ARC_traffic_speed_bandwidth.png`: full-metro bandwidth map,
  freeway skeleton as thick bands, downtown/I-285 olive-orange with red bottlenecks (real speed field).
  Rendered in ~5 s. `moe_ARC_corridor_I75.png`: I-75 corridor (241 links, 35.9 mi) — speed collapses to
  15-30 mph exactly where volume peaks at ~40k veh through the downtown core (the flow-speed signature).
- **Tucson I-10 (`--corridor-name "I-10 WB"`)** — `moe_Tucson_corridor_I10_WB.png`: 52-link, 22.8-mi
  **connectivity-chained** corridor; clean ~47 mph urban -> 71 mph free-flow mainline -> arterial.

Corridors are extracted by `--corridor-name "I-75"` / `"I-10 WB"` and **chained by node connectivity**
(from_node -> to_node) into a real sequence, not a spatial jumble. With time-dependent data these same
sorted links become the 2D space-time contour; static networks get the 1D speed/volume profile shown here.
Note: volume/speed join needs a standard `link_performance.csv` (`link_id,volume,speed`); nonstandard
DTALite period-column schemas (e.g. Tucson) fall back to posted speed until an adapter maps their columns.

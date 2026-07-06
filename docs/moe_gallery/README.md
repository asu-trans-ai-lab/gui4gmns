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

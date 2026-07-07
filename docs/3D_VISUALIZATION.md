# 3D visualization — city base + GMNS overlay + optimization layer

**The principle:** don't bake traffic values into a 3D city model. Use an exported **3D city scene as the
static base**, and overlay **GMNS simulation/optimization outputs as separate, animated 3D layers**.

```text
OpenCities / 3D city export        →  terrain + buildings + trees + road surface   (BASE, static)
GMNS simulation / optimization     →  volume · speed · queue · delay · V/C · OD · trajectory
gui4gmns 3D overlay                →  dynamic traffic layers above the 3D city base
gmns2optimization                  →  decision variables · constraints · shadow prices
   = an explainable 3D decision-support environment
```

**Live first cut:** a GMNS 3D overlay (volume→height, speed→color) is running now —
[West Jordan, AM peak](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/gmns3d/) (`renderers/gmns_3d.py`).
Composite it over an OpenCities KMZ/Collada export for the full scene.

## The visual grammar (one consistent language)

| GMNS output | 3D representation |
|---|---|
| `link_performance.volume` | extrusion **height** (or link width) |
| `link_performance.speed` / `speed_ratio` | link **color** (green free-flow → red slow) |
| `link_performance.voc` | saturation / warning halo |
| `queue_length` | red **spillback ribbon** from the stop line, upstream |
| `density` | semi-transparent tube thickness |
| `delay` | vertical **wall / column** above the link |
| `path_flow` | highlighted path bundle |
| `od_demand` | 3D **arc** between zones |
| `trajectory` | moving agents (cars / buses / peds) |
| optimization: decision variable | highlighted controlled links / signals / zones |
| optimization: constraint violation | red warning marker |
| optimization: binding capacity | thick red link |
| optimization: shadow / dual price | "pressure" heatmap |
| objective value | before/after KPI card |

## Export settings (OpenCities "Export 3D")

Start with **one corridor** (1–3 mi), not the whole city.
- **File type:** **KMZ** for Google Earth / outreach; **Collada** for Blender / Three.js / web editing.
- **Combined file** for a quick demo; **single files** to edit buildings/terrain separately.
- **Quality:** medium/high only for a small area. **Terraform:** off (only for flatten-and-re-import).
- Keep terrain + buildings + trees + road surface; **do not** include GMNS values here.

## Format guidance

```text
CityGML / GML   → semantic 3D city database / archive (OGC standard; not a runtime format)
3D Tiles        → web-scale streaming of massive 3D geospatial scenes (buildings, photogrammetry)
glTF / GLB      → browser-based 3D animation
KMZ / KML       → simple outreach / Google Earth
Collada / DAE   → editing / conversion bridge (Blender)
```
The stronger plan is **not** "export everything to 3D GML." It is: **3D city geometry as context, GMNS as the
simulation network, gui4gmns as the interactive visual-analytics layer.**

## Phased pipeline

1. **Base scene** — OpenCities → select a small corridor polygon → export KMZ/Collada (no GMNS values).
2. **GMNS layer** — from DTALite/TAPLite/DLSim: minimum `link.csv` + `link_performance.csv`; better add
   `queue_event.csv` + `signal_timing.csv`; advanced add `agent_trajectory.csv` + `path_flow.csv` +
   `objective_trace.csv` + `constraint_status.csv`.
3. **Overlay** — for each link: a 3D ribbon **~2–5 m above** the road surface; height = volume, color =
   speed ratio, red segment = queue length (offset avoids z-fighting with the base).
4. **Animate** — 5- or 15-minute bins; per step update height (volume), color (speed), queue ribbon, agents.

## First demonstration: "GMNS 3D Corridor Simulation Viewer"
One corridor: base 3D city scene → GMNS links overlaid → volume as height → speed as color → queue as red
spillback ribbon → time slider → before/after optimization comparison. Message: *a GMNS folder can become an
interactive 3D simulation scene — planners see volume/speed, operators see queues/signals, researchers see
optimization variables and constraints.*

## Status / roadmap
- **Done:** `renderers/gmns_3d.py` — extruded ribbons (volume→height, speed→color, V/C tooltip), deck.gl +
  OSM basemap, pitched 3D; West Jordan live.
- **Next:** queue spillback ribbons; time-slider animation (multi-bin `link_performance`); trajectory agents;
  OD arcs; composite over an actual OpenCities KMZ base; the gmns2optimization decision layer.

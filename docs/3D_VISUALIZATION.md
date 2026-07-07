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

**Live now:**
- [West Jordan static overlay](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/gmns3d/) — volume→height,
  speed→color (`renderers/gmns_3d.py`).
- [I-95 3D TMC timeline](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i95_tmc/) — **real** 24h×15-min
  TMC speeds, time slider, data-driven storyline (baseline → bottleneck → spillback → recovery).
- [I-405 N — observed (Caltrans PeMS)](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i405n_tmc/) — real
  full-year weekday-averaged **5-min speed+flow**, AM peak.
- [I-405 N — QVDF model](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i405n_qvdf/) — the **calibrated
  QVDF speed reconstruction** from the inflow demand-to-capacity ratio (polynomial arrival queue → VDF); full
  weekday, per-link **D/C on hover**, and a red tail driven by the **analytical queue length
  Q(t) ∝ (t−t₀)²(t₃−t)²** (cubic PAQ, m=0.5) — the queue grows from t₀, peaks at t₂, dissipates by t₃, exactly
  as the model predicts, not a speed proxy (`--qvdf handoff_avgweekday_timedependent.csv --paq daily_paq_all.csv`).
- [Event playbook — Chicago](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/chicago_tmc/) — 15-min
  volume + **measured** queue spillback (`queue_exb`) + blocked-link events firing on the clock.

Both timelines are `renderers/gmns_3d_time.py` (auto-detects the feed shape). For the operations reading —
vocabulary, event storyline, and what NOT to fake at each data level — see the **[3D TMC Playbook](3D_TMC_PLAYBOOK.md)**.
Composite any of these over an OpenCities KMZ/Collada export for the full 3D-city scene.

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
- **Done:** `renderers/gmns_3d_time.py` — **time-slider animation** over multi-bin feeds; **queue spillback
  ribbon** growing upstream (measured `queue_exb`, or speed-derived and labelled as such); incident/weather
  **event markers** with an influence zone; a **data-driven TMC storyline** detected from the real speed curve;
  KPI cards. Live on I-95 (real speeds) and Chicago (measured queue + events).
- **Next:** trajectory agents (`waypoints.csv`/`agent_trajectory.csv`); OD arcs (`od.csv`); VSL/ramp-meter/DMS
  control glyphs; composite over an actual OpenCities KMZ base; the gmns2optimization decision layer
  (binding capacity = thick red link, constraint violation = warning marker, before/after KPI card).

# Visualization landscape review — how the domain builds it, and what gui4gmns should adopt

Goal: for gui4gmns's four core viewers — **path viewing · capacity · time-dependent MOE · vehicle
trajectories** — survey how the major traffic tools and GIS/web stacks do it, offer alternatives, and
pick the technique to build each core in self-contained HTML dashboards. (Fable-5 synthesis; sources
at the end.)

## Part 1 — how the domain visualizes (delivery + the four cores)

| tool | delivery | network + capacity | path / route | time-dependent MOE | vehicle trajectory |
|---|---|---|---|---|---|
| **SUMO** | native `sumo-gui` (FOX/OpenGL); web only via bolt-ons (SUMO-Web3D = TraCI + three.js frame-diffs; Cesium WebGIS) | link color/width in gui | route inspection in gui | color-by-attribute over sim time | `fcd-output` XML → `fcdReplay.py`, `plotXMLAttributes.py` |
| **MATSim / SimWrapper** | **browser dashboards, YAML-configured, deck.gl** (no code) | **network link plots** (`viz-link-*`), capacity/volume bands | aggregate O/D flows, flowmaps | **X/Y/Time point data**, animated | **DRT/agent animation**, events viewer |
| **PTV VISSIM** | native Windows, 3D animation | 3D links, LOS color | dynamic assignment paths | micro time-step animation | full 3D vehicle animation |
| **PTV Visum** | native/GIS macro | bandwidth (flow bundles), volume bands | flow-bundle path isolation | time-interval assignment display | — (macro) |
| **TransCAD / TransModeler** | Caliper GISDK desktop | GIS themes, bandwidth | path/skim display | time-of-day layers | TransModeler micro animation |
| **Aimsun** | native + Aimsun Live (web ops) | link LOS | route editor | time-series MOE | micro animation |
| **kepler.gl** | **web, GPU (deck.gl)** | polygon/line layers | ArcLayer O→D | time filter/playback | **Trip layer** (geoJSON, 4th coord = timestamp) |
| **deck.gl** | **web, GPU primitives** | PathLayer / LineLayer / PolygonLayer | ArcLayer, GreatCircle | time-windowed props | **TripsLayer** (shader-interpolated `currentTime`) |
| **QGIS** | desktop GIS | graduated/bandwidth symbology | — | **Temporal Controller** | animated point layers |
| **Cesium** | web 3D globe | 3D extruded | — | time-dynamic (CZML) | 3D entity paths |

**The pattern.** The commercial/desktop tools (SUMO, VISSIM, Visum, TransCAD, Aimsun) are native GUIs;
their web stories are bolt-ons or ops portals. Only **SimWrapper** ships first-class *browser
dashboards* for simulation output — and it does so exactly the way gui4gmns is heading: point at files,
write small config, get a laid-out dashboard, rendered on **deck.gl** (GPU). The web-GIS libraries
(**deck.gl / kepler.gl**) are where the reusable *techniques* live.

## Part 2 — the four cores: alternatives → pick

### Core 1 · Path / route viewing
- **A. Polyline over links** (what gui4gmns does now) — top-K OD paths as colored polylines. Simple, exact, but overlapping paths hide volume.
- **B. Flow-bundle / bandwidth** (Visum, TransCAD) — merge paths sharing links; width = flow. Reads volume at a glance; needs an aggregation step.
- **C. deck.gl ArcLayer** (kepler.gl) — O→D arcs, height/color by volume. Great for desire-lines and long OD, weak for on-network routing.
- **PICK: B (bandwidth) for on-network paths + C (arcs) for OD desire-lines.** gui4gmns already has OD desire-lines (from plot4gmns) and volume bandwidth on links; the gap is **flow-bundle aggregation** so overlapping routes render as one widening band instead of spaghetti.

### Core 2 · Capacity / VOC
- **A. V/C color ramp** (current) — good, but capacity itself isn't visible, only the ratio.
- **B. Capacity as link width, volume as fill** (Visum bandwidth) — two variables at once: width = capacity·lanes, colored fill length = volume; instantly shows where demand meets/exceeds supply.
- **C. Small multiples / faceted** (SimWrapper) — side-by-side capacity vs volume vs V/C panels.
- **PICK: B (width=capacity, color=V/C).** gui4gmns's tiered draw already scales width by facility; bind width to **capacity·lanes** and keep the log-anchored V/C ramp — capacity and utilization in one glyph. Keep A as a toggle.

### Core 3 · Time-dependent MOE
- **A. 15-min bin recolor + time slider** (current gui4gmns; SimWrapper temporal). Robust, exact, cache-friendly.
- **B. Space-time contour** (already built for the QVDF corridor) — distance×time heatmap; the strongest single view of a corridor's day.
- **C. Continuous GPU interpolation** (deck.gl time props) — smooth between bins.
- **PICK: A as the map default + B (contour) as the corridor drill-down.** Both exist. Improvement: a **synchronized "MOE small-multiples" strip** (speed | volume | queue contours side-by-side, SimWrapper-style) so one glance covers all three measures over the day.

### Core 4 · Vehicle trajectories
- **A. Canvas dots interpolated on links** (gui4gmns web-lite) — simple, ~thousands of agents.
- **B. deck.gl / raw-WebGL2 TripsLayer** (kepler.gl, gui4gmns web-gl) — **shader-interpolated trips, 100k+ agents at frame rate**, fading tails. The domain standard for trajectory animation.
- **C. FCD replay** (SUMO) — event/XML replay; heavy, desktop.
- **PICK: B (TripsLayer technique).** gui4gmns's web-gl branch already implements it in raw WebGL2 (verified 746k segments). Improvement: **fading trails** (the deck.gl TripsLayer signature — a trail length so you see where a vehicle *came from*, not just a moving dot) and bring the GPU trips into the main generated dashboard, not only the separate web-gl viewer.

## Part 3 — improvement plan for gui4gmns (what to build)

Ranked by leverage. Most are *upgrades to techniques gui4gmns already has*, informed by how the domain does it — not rewrites.

1. **Flow-bundle path bandwidth** (Core 1B) — aggregate top-K paths into widening bands; the single biggest readability win for "path viewing." *New: `path_bundle` in the generator.*
2. **Capacity-width glyph** (Core 2B) — width = capacity·lanes, color = V/C; capacity becomes visible. *Change: bind link width to capacity in `volume`/`voc` MOE modes.*
3. **Fading trajectory trails + GPU trips in the main dashboard** (Core 4B) — port the web-gl TripsLayer trail into the generated `dashboard.html` so every dashboard animates trajectories at scale, with tails. *Merge web-gl technique into the generator.*
4. **MOE small-multiples strip** (Core 3) — speed | volume | queue space-time contours side-by-side for a selected corridor. *Extend the corridor panel.*
5. **YAML dashboard-as-code** (SimWrapper's model) — let a `dashboard.yaml` declare which panels/layers appear, so non-coders compose dashboards. This is the natural bridge to the catalog engine (roadmap B2): the catalog manifest *is* the dashboard spec. *New: `dashboard.yaml` → generator layout.*
6. **deck.gl as an optional GPU backend** — keep the zero-dependency canvas default (offline, self-contained — gui4gmns's edge over SimWrapper, which needs the SimWrapper app), but allow a deck.gl render path for regional-scale animation. *Optional; the raw-WebGL2 path already covers most of this offline.*

**gui4gmns's differentiator to protect:** SimWrapper is the closest peer but requires its hosted app +
YAML + file server. gui4gmns emits **one self-contained, offline, double-clickable HTML with the data
and basemap embedded** — no app, no server, no internet. That is the thing to keep while adopting
SimWrapper's *ideas* (YAML-as-code, small-multiples, the viz catalog) and deck.gl's *techniques*
(TripsLayer trails, bandwidth, arcs).

## Sources
- [SimWrapper docs](https://docs.simwrapper.app/docs/) · [examples](https://docs.simwrapper.app/docs/examples) · [network link plots](https://docs.simwrapper.app/docs/link-vols) · [dashboards as code](https://docs.simwrapper.app/docs/guide-dashboards-from-code) · [Billy Charlton — what is SimWrapper](https://billyc.github.io/blog/2023/11/what-is-simwrapper.html)
- [SUMO Visualization](https://sumo.dlr.de/userdoc/Tools/Visualization.html) · [FCDOutput](https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html) · [sumo-web3d](https://github.com/sidewalklabs/sumo-web3d)
- [deck.gl TripsLayer](https://deck.gl/docs/api-reference/geo-layers/trips-layer) · [kepler.gl Trip layer](https://docs.kepler.gl/docs/user-guides/c-types-of-layers/k-trip)
- [PTV Vissim (Wikipedia)](https://en.wikipedia.org/wiki/PTV_Vissim)

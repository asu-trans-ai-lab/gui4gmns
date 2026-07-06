# NeXTA-X Shared Contract — one data model + one presentation language for all branches

Every NeXTA-X branch (web-lite, web-gl, qgis-plugin, desktop-qt, python-lab) MUST implement this
contract, so users can move between branches without relearning anything and engines never special-case
a GUI. **This file is the single source of truth; branches conform to it, never the reverse.**

## 1. Input files (identical readers in every branch)
| role | file | required columns |
|---|---|---|
| network | `node.csv` | `node_id, x_coord, y_coord, zone_id` (zone nonempty = centroid) |
| network | `link.csv` | `link_id, from_node_id, to_node_id, lanes, capacity, free_speed, length` (+ optional `vdf_length_mi, geometry` WKT LINESTRING, `link_type, discharge_model`) |
| static MOE | `link_performance.csv` | `link_id` + `volume`\|`cum_departure`, optional `speed`, `max_queue_exb` |
| TD MOE | `link_performance_15min.csv` | `link_id, time_bin_start (hh:mm), inflow_veh, queue_exb` |
| paths | `path_flow.csv` / `route_assignment.csv` | `o_zone_id, d_zone_id, base_volume\|volume, route_share, link_ids ("1;2;3")` |
| trajectories | `agent_trajectory.csv` | `agent_id, link_id, time_min, buffer (ENB\|EXB), traffic_state` |
| calibration | `measurement.csv`, `od_adjustment_with_sensor_coverage.csv` | per encoding spec §6 / ODME outputs |
| run meta | `run_summary.json` (incl. `gridlock` block), `gridlock_events.csv` | dlsim_run package |
CSV parsing MUST be quote-aware (WKT/link_ids contain commas/semicolons). Missing ≠ zero.

## 2. Presentation semantics (identical look across branches)
- **MOE modes**: `volume` (bandwidth ∝ vol, color ramp), `voc` (V/C), `queue`, `td` (per-bin animate).
- **Color ramp**: green→yellow→red over [0,1]; green = free, red = congested. Selected = accent blue.
- **Nodes**: centroids gold, others gray. **Trajectory dots**: green = moving (ENB, position by
  linear interpolation along link geometry between ENB and EXB times), red = queued (EXB), hidden
  after `completed`.
- **Time control**: 15-min bins; play/pause/speed; label `hh:mm`; agent time = mid-bin.
- **Inspector**: click link → id, from→to, volume, V/C, queue, all GMNS attrs, current-bin MOE.
- **Summary statistics**: nodes/zones/links, Σ volume, VMT, volume histogram, top-10 congested
  (clickable), run summary incl. conservation + gridlock (oversaturated flag, first warning, cycles).

## 3. Branch charter
| branch | stack | purpose / unique capability | primary user |
|---|---|---|---|
| `web-lite/` | single HTML file, canvas (**v1 SHIPPED**: `nexta_x.html`) | zero-install QC viewer shipped inside every run folder; agency-lockdown-proof | anyone with a browser |
| `web-gl/` | deck.gl-class WebGL bundle + tiny Python run-server | **per-vehicle animation at regional/NGSIM scale (GPU TripsLayer)**; **live-follow of a running simulation** (server tails the run folder); basemaps; stakeholder demos | analysts, public meetings |
| `qgis-plugin/` | PyQGIS plugin | **network editing** (move/create nodes-links, subarea cut) with GMNS write-back; projections, basemaps, print layouts for free | MPO modelers |
| `desktop-qt/` | Qt/C++ linking DTALite/TAPLite/DLSim | **in-process live visualization while simulating**; native perf; the "classic NEXTA" desktop identity | power users, demos of the engine itself |
| `python-lab/` | pandas/pyqtgraph or notebook API | research scripting over the same contract; feeds dynamic-odme-lab diagnostics | students, researchers |

## 4. Conformance checklist (each branch must pass before release)
1. Loads the Chicago Sketch demo package (`web-lite` `demo/`) with zero configuration.
2. Renders the four layers (nodes/links/paths/trajectories) with §2 semantics.
3. Animates the 26-bin demo (TD recolor + agent dots) with correct clock labels.
4. Click-inspect returns the same attribute set as web-lite.
5. Statistics panel matches web-lite's numbers on the demo (Σ volume, VMT, top-10 congested).
6. Never writes network files except qgis-plugin explicit save (GMNS round-trip validated).

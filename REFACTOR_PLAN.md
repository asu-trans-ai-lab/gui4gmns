# NeXTA-X — cross-platform refactor of the NEXTA GUI for DTALite / TAPLite / Dynamic ODME / DLSim

## Why refactor
The archived NEXTA (`nexta_source-archive`, `NGSIM-NEXTA_GUI`) is **Windows-only MFC** Document/View
(`TLiteDoc.cpp` ~600 KB, `TLiteView.cpp` ~266 KB, GridCtrl, GDI drawing) reading **pre-GMNS** files
(`input_node.csv`, `input_link.csv`, `output_LinkMOE.csv`, `output_LinkTDMOE.csv`, `output_ODMOE.csv`,
`sensor_count.csv`, `AMS_movement/phasing/timing_plan.csv`). It cannot be built cross-platform, and each
engine grew its own file dialect.

## Architecture: one viewer, one contract, N engines
```text
NeXTA-X (single self-contained HTML/JS app — runs in any browser on Windows/macOS/Linux, no install)
├── io/        GMNS reader (CSV, drag-drop or served-folder fetch), WKT geometry parser
├── adapters/  engine output mapping -> one internal model
│   ├── DTALite   link_performance.csv, route_assignment.csv, agent.csv
│   ├── TAPLite   link_performance.csv (volume), od_performance.csv
│   ├── ODME      od_adjustment_with_sensor_coverage.csv, measurement.csv (obs vs sim)
│   └── DLSim     out/link_performance.csv, out_link_performance_15min.csv, agent_trajectory.csv,
│                 gridlock_events.csv, run_summary.json
├── view/      canvas renderer: pan/zoom, layers, MOE color+width scaling, click-to-inspect
├── anim/      time controller: play/pause/speed, link-MOE animation (15-min bins),
│              agent-dot trajectory playback (event lists / path+departure interpolation)
└── stats/     summary panel: network totals, VMT/VHT, volume histogram, top-N congested links,
               ODME before/after, gridlock events
```

### The unified I/O contract (all four engines already speak it or map to it)
| role | canonical file | notes |
|---|---|---|
| network | `node.csv`, `link.csv` (GMNS) | `geometry` WKT LINESTRING used when present; else straight from/to |
| static MOE | `link_performance.csv` | volume / speed / VOC (DTALite, TAPLite) or CA/CD/max_queue (DLSim) |
| time-dependent MOE | `out_link_performance_15min.csv` | inflow + queue per 15-min bin (DLSim; DTALite TDMOE maps in) |
| paths | `route_assignment.csv` / `path_flow.csv` | `node_ids` / `link_ids` sequences + volume/share |
| trajectories | `agent_trajectory.csv` | `(agent, link, time, buffer[, state])` event list = trajectory |
| calibration | `od_adjustment_with_sensor_coverage.csv`, `measurement.csv` | θ, sensor coverage, obs-vs-sim |
| run meta | `run_summary.json`, `gridlock_events.csv` | totals, conservation, warnings |

## NEXTA feature → NeXTA-X mapping
| NEXTA (MFC) | NeXTA-X |
|---|---|
| network display, pan/zoom (GDI) | canvas renderer, wheel-zoom / drag-pan |
| link MOE color & bandwidth (`output_LinkMOE`) | color+width by volume / VOC / speed / queue, legend |
| time-dependent MOE (`output_LinkTDMOE`) | animation over 15-min bins, time slider |
| vehicle animation (`g_Simulation…`) | agent-dot playback from event-list trajectories |
| path display (`input_path.csv`) | path layer from route_assignment / path_flow (top-K by volume) |
| click link → attribute grid (GridCtrl) | click-to-inspect panel (all fields of node/link) |
| ODME sensor layers (`sensor_count.csv`) | sensor/screenline layer + obs-vs-sim bars |
| summary statistics dialogs | stats panel (network totals, VMT/VHT, histograms, top-N) |
| scenario/AMS editing, VISSIM export | **out of scope v1** (viewer first; editing later phase) |

## Cross-platform choice
Single self-contained HTML file (no CDN, no install, offline): the one runtime every OS ships is a
browser. Same file doubles as a desktop app via any webview shell later. Data loads two ways:
1. **Drag-drop / file picker** (pure client-side, private by default), or
2. **served-folder mode** (`?data=<relative-dir>` when hosted by `python -m http.server`) for automation.

## DECISION (2026-07-02): NeXTA-X is a FAMILY — all four branches, one contract
Not one executable for all purposes. Every branch implements `SHARED_CONTRACT.md` (same GMNS readers,
same MOE semantics, same statistics), then serves its own audience:

| order | branch | unique capability | status |
|---|---|---|---|
| 1 | `web-lite/` | zero-install QC viewer shipped with runs | **v1 shipped + browser-verified** |
| 2 | `web-gl/` | GPU per-vehicle animation at regional/NGSIM scale + live-follow (poll mode) | **in progress** |
| 3 | `desktop-qt/` | in-process live visualization while simulating (classic NEXTA identity) | after contract proven at scale |
| — | `python-lab/` | research scripting + contract conformance tests (golden demo numbers) | grows alongside |
| deferred | `qgis-plugin/` | editing | **DEFERRED (2026-07-02): visualization first — the legacy NEXTA Windows exe remains the editing tool**; folder kept as placeholder |

Cross-branch features by request: sensors/screenline obs-vs-sim + ODME θ overlays land first in
web-lite/web-gl; live-follow in web-gl (file-tail polling — plain `python -m http.server`, no custom
server) and desktop-qt (in-process). web-gl implements the trips technique in **raw WebGL2** (segments
interpolated in the vertex shader) — no deck.gl dependency, no bundler, still one self-contained file.

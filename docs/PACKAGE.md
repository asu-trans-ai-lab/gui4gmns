# gui4gmns — package review (v0.1)

The final package for review. gui4gmns is **GUI-X** for GMNS: one pure-Python generator turns a GMNS
run folder into a self-contained, offline, double-clickable dashboard — and feeds the tools you already
use. Below is everything in the package, how to run it, and what to check.

## Install / run in 30 seconds
```bash
pip install gui4gmns                      # or: python ai-gen/gui4gmns.py <folder>
python ai-gen/gui4gmns.py datasets/01_sioux_falls      # -> dashboard.html (double-click)
python -c "import gui4gmns; gui4gmns.generate('datasets/02_chicago_sketch')"
```

## What's in the box
| area | file(s) | what it does |
|---|---|---|
| **Generator (core)** | `ai-gen/gui4gmns.py` | GMNS -> self-contained `dashboard.html`; pure-Python, pip-installable (`gui4gmns 0.1.0`, wheel builds) |
| **Dashboard features** | (embedded) | hybrid OSM/satellite basemap, MOE modes (volume/VC/queue/TD-flow/QVDF-speed/**path-bundle**), **fading trajectory trails + 3D tilt**, demand OD + distributions, corridor INRIX-vs-QVDF contour, **7-check SCI physics panel**, self-auditing data-quality footer, **auto sim2trajectory** |
| **Viewers** | `nexta_x.html`, `web-gl/`, `desktop-qt/` | zero-install QC · GPU regional animation + live-follow · Qt desktop (Run-engine, snapshots) |
| **Adapters (in)** | `adapters/` | ITS I-95 data-hub (2.3 GB->5 MB, 6 sources), **semi-dynamic trajectory synthesis** (TD link perf -> animatable vehicles) |
| **Exporters (out, GUI-X)** | `exporters/gmns_to_viz.py` | GMNS -> **kepler.gl** / **deck.gl** / **QGIS** (+.qml+loader) / **Google Earth KML** (3D bars + fly) |
| **Static MOE PNGs** | `renderers/moe_static.py`, `docs/moe_gallery/` | report-ready traffic-speed bandwidth + **space-time speed/density contours** (colorblind-safe, matplotlib) — no screen-copying |
| **Catalog** | `templates/catalog/` | dataset-first manifest + JSON schema (10 datasets); QA contracts incl. the 7 SCI checks |
| **Engine** | `engine/DLSim_STE/` | the space-time-event engine source (C++17) + build.sh (drives `dashboard` Run-engine) |
| **Docs** | `docs/` | Users Guide (md+pdf), `REVIEW_FABLE5.md`, `VIZ_LANDSCAPE_REVIEW.md`, `TRB_VIZ_REVIEW.md`, `ROADMAP.md`, this file |

## Verified on real networks
- **ARC Atlanta (145,971 links)** — bandwidth map in ~5 s, real congestion; I-75 corridor (241 links, speed dips where volume peaks ~40k veh).
- **Tucson I-10** — `--corridor-name "I-10 WB"` connectivity-chained (52 links, 22.8 mi).
- **Chicago Sketch (2,950 links)** — full package (MOE, TD, paths, 1.13 M-agent run, trajectories); semi-dynamic synthesis = 2,000 vehicles.
- **ITS I-95 (VA)** — 6-source data hub sample + layered `its_datahub.html`.
- **NVTA I-395** (private, local) — QVDF space-time contour showing the AM breakdown; kept out of the repo.

## What to check in review
1. **Correctness** — every dashboard's **SCI physics panel** should be all-green on clean data (conservation, non-negativity, capacity, topology, speed bounds); fault-inject to see it fail loudly.
2. **Offline** — open any `dashboard.html` with the network off: map, basemap, animation all work (data + tiles embedded).
3. **Privacy** — `python validate_no_private_data.py` must say *clean*; agency data (NVTA/VDOT/INRIX) is git-ignored and never in the release.
4. **Colorblind safety** — MOE PNGs and dashboards default to blue->red bands + cividis contours (no green/red).
5. **Reproducibility** — `import gui4gmns; gui4gmns.generate(folder)` reproduces any dashboard.

## Known limitations (honest)
- Static PNGs on ARC/Tucson are *space* profiles (space-**time** needs time-dependent link data).
- Some DTALite period-column schemas (Tucson) need column mapping for volumes (partly handled).
- CDN dependency only in exported deck.gl/`apache_*` templates, never in the core dashboard.
- **AZ subarea tool** (Maricopa/MAG subarea extraction + corridor MOE) is planned, not built — roadmap D5.

## Workspace + release
Dev: `gui4gmns/github_dev` (this tree). Public: `gui4gmns/github_release` (clone, remote
`asu-trans-ai-lab/gui4gmns`, zero private data). Raw sources in `_raw_sources/` (outside git). See
`../WORKSPACE.md`. Ship: `cd ../github_release && python validate_no_private_data.py && git push`.

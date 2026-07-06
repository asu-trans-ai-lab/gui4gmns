# exporters — GUI-X: GMNS out to the tools you already use

gui4gmns is **GUI-X**, not just a GUI: besides its own self-contained dashboard, it exports your GMNS
network + results into the best external visualization tools, so you **bring your own layers**, styling,
and 3D. Each target is an independent pipeline — pick one, or `all`.

```bash
python exporters/gmns_to_viz.py <gmns_folder> [-o out_dir] [--target kepler|deckgl|qgis|kml|all]
```
Pure-Python stdlib. Reads `node.csv`, `link.csv` (+`link_performance.csv`), `agent_trajectory.csv`,
`demand.csv`. Needs geographic coords (lon/lat); add `crs.txt` (EPSG) to reproject first.

## Targets
| target | output | how to use |
|---|---|---|
| **kepler** | `network.geojson` · `trips.geojson` (4th coord = timestamp, kepler Trip format) · `od_arcs.csv` · `kepler_config.json` | drag the files into [kepler.gl/demo](https://kepler.gl/demo); load the config for styled layers. Add your own layers freely. |
| **deckgl** | `data.json` (PathLayer / **TripsLayer** / ArcLayer) · `index.html` (standalone, animated, pitched 3D) | open `index.html` (loads deck.gl from CDN). Edit the layer list to add your own. |
| **qgis** | `network.geojson` + `od.geojson` · `network.qml` (graduated-by-volume style) · `load_layers.py` | drag the GeoJSON in (auto-applies the `.qml`), **or** run `load_layers.py` in the QGIS Python console to add all layers styled by template. |
| **kml** | `gmns.kml` — links as **volume-extruded 3D bars** + time-stamped trajectory points | open in Google Earth (Pro/web); tilt to **fly** the 3D corridor; use the time slider to animate. |

## Why this shape
The viz landscape review (`docs/VIZ_LANDSCAPE_REVIEW.md`) found the reusable *techniques* live in
kepler.gl / deck.gl, GIS work lives in QGIS, and Google Earth gives free 3D + fly-through. Rather than
re-implement all of that, gui4gmns **feeds** them — the catalog manifest can declare an `export:` target
so any dataset ships kepler/qgis/kml bundles alongside its dashboard. The self-contained offline
`dashboard.html` stays the default; these exporters are the "escape hatches" to specialist tools.

## Verified (2026-07)
West Jordan (378 links, 300 OD) and Chicago Sketch (2,950 links, 500 trajectories) → all four targets;
GeoJSON valid, kepler trip coords 4-element, QGIS QML graduated, KML `extrude=1` 3D bars, deck.gl
data with color/width/timestamps.

# What gui4gmns AI-Gen learned from plot4gmns

[plot4gmns](https://github.com/jiawlu/plot4gmns) (ASU-Trans-AI-Lab) is a clean, pip-installable GMNS
visualization package: `import plot4gmns as pg; mnet = pg.generate_multi_network_from_csv(dir)` then a
family of `pg.show_*` verbs (matplotlib + kepler.gl). We studied its API and gallery and adopted the
capabilities gui4gmns was missing.

## API comparison
| plot4gmns (`pg.show_*`) | gui4gmns status |
|---|---|
| `show_gmns_nodes / links / zones / geometries` | ✅ had (network map) |
| `show_network_by_link_free_speed / lanes / length / types` (attribute filter) | partial — had tier LOD + min-vol; **now + distributions** |
| `show_network_by_link_{capacity,free_speed,lane}_distribution` (histograms) | ❌ → ✅ **ADOPTED** (distributions panel) |
| `show_network_demand_matrix_heatmap` | ❌ → ✅ **ADOPTED** (demand heatmap, top-24 zones) |
| `show_network_by_demand_OD` (desire lines) | ❌ → ✅ **ADOPTED** (OD desire-line layer) |
| `show_gmns_poi / location / movements / lanes` | ❌ not yet (see "next") |
| `generate_visualization_map_using_keplergl` | different path — gui4gmns embeds its own canvas + OSM/satellite tiles |

## Adopted now (verified on Sioux Falls, 2026-07-04)
1. **Demand OD desire lines** — `demand.csv` (`o_zone_id,d_zone_id,volume`) aggregated to zone centroids
   (mean of a zone's nodes), top-400 desire lines drawn centroid→centroid, width + red by volume.
   Toggle: "demand OD". Verified: 528 OD pairs, 360,600 veh, 4,629 desire-line px over the network.
2. **Demand matrix heatmap** — busiest 24 zones as an O×D grid (green→red by volume), in the
   "distributions" panel. Direct analogue of `show_network_demand_matrix_heatmap`.
3. **Attribute distributions** — capacity / free-speed / lanes / volume histograms in the
   "▦ distributions" panel. Direct analogue of plot4gmns's `*_distribution` verbs.

All three ride the split-layer architecture: a new lightweight `demand.js` sidecar; the audit footer
now reports `demand: N OD pairs, total V veh (learned from plot4gmns)`.

## What made plot4gmns worth copying (design lessons)
- **Verb API discoverability**: one `generate_*` loader + many small `show_*` views. gui4gmns's
  equivalent is one `gui4gmns` preprocess + composable layers; we mirror the *catalog* in
  `VIZ_SCHEMA.md` §2 so an AI can pick views the same way a user picks `pg.show_*`.
- **Distributions are cheap QC gold**: a histogram of capacity/speed instantly exposes coding errors
  (e.g. the ARC 99,999 capacity sentinel we already flag). Now every dashboard carries them.
- **Demand is a first-class object**: AMS = demand + supply + assignment. gui4gmns had supply
  (network/MOE) and assignment (paths/trajectories) but not **demand** — this closes that gap.

## Next (plot4gmns features still worth porting)
- POI / activity-location layer (`show_gmns_poi`), zone polygons (we draw centroids only).
- Intersection **movements** layer (`show_gmns_movements`) — the classic NEXTA turning-movement view.
- Modal filtering (`show_network_by_modes`) for multimodal GMNS.


## Real adoption (2026-07): calling plot4gmns directly
Beyond re-deriving its ideas, gui4gmns now **calls the real plot4gmns engine** via
`renderers/p4g_export_all.py` — imports `plot4gmns` (vendored at `plot4gmns-main/` or pip), stubs the
optional keplergl dep, and exports **all 21 plot4gmns figures** for a demo network (Berlin): nodes,
links, POI, zones, geometries, by-mode, by-node-type, by-link-type/length/free-speed/lanes, the
lane/capacity/free-speed **distributions**, POI types + attraction/production distributions, and the
**demand-matrix heatmap**. Gallery: `docs/p4g_gallery/`. These are genuine plot4gmns output, not a
lookalike — so the network-attribute + distribution views are best done by plot4gmns; gui4gmns keeps
its own renderers only for what plot4gmns doesn't do (space-time contours, bottleneck ranking PeMS/RITIS,
the offline embedded dashboard, global multi-city montage).


## Tight integration (2026-07): native rewrite `renderers/gmns_figures.py`
The external-call path (`p4g_export_all.py`, keplergl-stubbed) proved the figures but is fragile (heavy
deps, hardcoded save dir, a `ZoneStyle.edgecolors` crash on demand-OD). So the plot4gmns catalog is now
**reimplemented natively** in gui4gmns: pure matplotlib + the same WKT reader the rest of the codebase
uses — **no pandas / Shapely / keplergl**, no hardcoded paths, the demand-OD bug fixed, one automatable
`export_all()`. It keeps plot4gmns's visual language (violet links, orange/blue zones, yellow POI, blue
demand desire lines, 'jet' OD heatmap) and, unlike the original, runs on **any** GMNS folder (Berlin
demo AND our West Jordan/Chicago/etc.) with graceful skips for missing layers. 13 figures:
links, nodes, zones, POI, by-link-type/free-speed/lanes/length, capacity/free-speed/lanes distributions,
demand matrix heatmap, demand-OD. Gallery: `docs/p4g_native_gallery/`. `p4g_export_all.py` stays as the
optional "exact plot4gmns output" path.

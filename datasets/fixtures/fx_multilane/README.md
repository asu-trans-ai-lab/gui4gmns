# fx_multilane — L7 (rich attributes) fixture

A tiny 4-way intersection (5 nodes / 4 links) built specifically to exercise **input level L7** — the
one no shipped dataset lit up: real zone **polygons** (not just centroid dots), POI footprints,
lane-offset rendering, and turning-movement diagrams.

```
        4
        │
        │ L3 (3 lanes)
        │
1 ──L1──2──L2── 3
(1 lane)│(2 lanes)
        │ L4 (4 lanes)
        │
        5
```
Node 2 is the intersection (zone Z1); node 5 sits in zone Z2 with its own polygon. Two POI footprints
(school, hospital) sit inside Z1.

## What this fixture found

Generating it exposed a **real bug in `fig_movements()`** (`renderers/gmns_figures.py`): the turning-path
geometry used `ib_link.pts[-1]` (inbound link's end point) and `ob_link.pts[0]` (outbound link's start
point) as the turn's endpoints. In GMNS, a link's endpoints **are** its from/to node coordinates — so
both points, and the node itself, are literally the same coordinate. Every turning-movement segment
collapsed to zero length: the figure ran, saved a non-empty PNG, but drew nothing but the legend. No
shipped dataset ever had `movement.csv`, so this was never caught.

**Fixed**: the approach/depart points are now set back 15% along each link, so every turn renders as a
visible colored path through the node. Same class of "runs without error, but the content is empty/
degenerate" bug as F-006/F-009/F-010 — this fixture is what caught it.

## Golden values (`EXPECTED.json`)

MOE volume = `cum_departure`; V/C = volume ÷ (capacity/lane × lanes):

| link | lanes | volume | cap total | V/C |
|---|---|---|---|---|
| 1 | 1 | 600 | 1800 | 0.333 |
| 2 | 2 | 2100 | 3600 | 0.583 |
| 3 | 3 | 1200 | 5400 | 0.222 |
| 4 | 4 | 3600 | 7200 | 0.500 |

`required_figures` lists the 5 figures this fixture specifically proves are non-degenerate — checked by
`qa/verify_output.py` (method M-D): `gmns_zones.png` (real polygons), `gmns_poi.png`, `gmns_lanes.png`
(lane-offset rendering across 1–4 lanes), `gmns_movements.png` (turning paths), `gmns_by_lanes.png`
(a real [2,4]-lane match — every other dataset has uniform lanes=1 and reports `NA` here).

## Use

```
python ai-gen/gui4gmns.py datasets/fixtures/fx_multilane
python qa/verify_output.py datasets/fixtures/fx_multilane
```

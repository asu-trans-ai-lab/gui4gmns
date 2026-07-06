# Skill: GMNS → dashboard folders (package + LLM), city by city

How to turn a city's raw data into a **GMNS folder** and then into a **dashboard/portal folder** — with the
`gui4gmns` package for the mechanical 90%, and an LLM (Claude / GPT) for the custom 10%. The design is
**dataset-first, dashboard-second**: a *dataset manifest* is the unit of work, not an HTML file.

```text
user query ─▶ dataset catalog ─▶ geofence/time/scenario filter ─▶ data adapter ─▶ QA gate ─▶ dashboard template
```

## 1. The data elements (what a GMNS folder is made of)

| element | file(s) | required for | notes |
|---|---|---|---|
| **nodes** | `node.csv` | everything | id, x/y (lon-lat or projected + `crs.txt`), zone_id |
| **links** | `link.csv` | everything | from/to, lanes, capacity, free_speed, length, geometry |
| **zones / demand** | `zone.csv`, `demand.csv` | OD, ODME | production/attraction, OD volume |
| **movements / signals** | `movement.csv`, `signal_timing.csv` | intersection ops | turning connectivity, phases, cycles |
| **link performance** | `link_performance.csv` | MOE, contours | time-dependent volume / **speed** / queue |
| **transit (GTFS)** | `stops.txt`, `trips.txt`, `stop_times.txt` | multimodal twin | snap stops to the road network |
| **sensors / TMC** | `sensor_15min.csv`, `tmc_speed_15min.csv` | ITS data hub | detector + probe/INRIX speed time-series |
| **trajectories** | `trajectory.csv` / probe `trips.csv`+`waypoints.csv` | animation, FD | agent → trace → sample-point → event |

**Input → output, in one line:** a GMNS folder (the elements above) **in** → a self-contained
`dashboard.html` + a `figures/` set + a `portals/` set (Kepler / deck.gl / QGIS / Google Earth) **out**.

## 2. The decomposed pipeline (worked example: Tempe)

The Tempe foundation network (`dtalite_with_taplite_Cpp_kernel/.../data_Tempe_network`) is the reference for
seeing **every piece integrated** — and it ships the pipeline as three readable steps:

```text
step1_osm2gmns.py        OSM  ──▶  GMNS network (node.csv, link.csv)         [decompose the map]
step2_zones_demand_run.py           + zones + OD demand                       [add demand]
step3_meso_assignment.py            + assignment ──▶ link_performance.csv      [add flow/speed]
        │
        ▼  (+ GTFS, + signals, + sensors as available)
gui4gmns generate  ──▶  dashboard.html + figures/ + portals/                   [integrate & visualize]
```

Decompose (understand each layer alone), then integrate (fuse into one hub). The **ITS I-95 data hub** is
the fully-integrated end state — network + INRIX/RITIS speed + VDOT sensors + probe + OD in one corridor
(`docs/portal_demo/i95/`).

## 3. Two ways to build the dashboard folder

**A. The package (mechanical 90%).**
```bash
python step1_osm2gmns.py                       # OSM -> GMNS (any city; ADOT: point at the Arizona extract)
python ai-gen/gui4gmns.py <gmns_folder>        # -> dashboard.html + figures/ + portals/{kepler,deckgl,qgis,kml}
python renderers/kepler_demo.py <folder> "<label>" -o out --top 6000   # live Kepler map (+ reproject via crs.txt)
```

**B. The LLM (custom 10% — Claude / GPT).** When a city needs something the templates don't do, hand the
model: (1) this skill, (2) the target `dataset_catalog.json` entry, (3) a header sample of each CSV, and ask:
> "Write a `<city>` adapter that maps these columns to the GMNS schema, then customize
> `templates/dashboards/gmns_dashboard_03_corridor_simulation.html` for this corridor's fields and QA gate."

The LLM writes the **adapter** + **template tweaks**; the package + QA gate keep it honest. That is the
"customize further" loop — the GUI *selects, validates, transforms, and explains*, not just displays.

## 4. The catalog (dataset-first)

Every dataset is a manifest entry (`templates/catalog/dataset_catalog.json`) — the GUI searches/filters these,
not the HTML files. First-level categories = the gallery tabs:

`regional_inventory` · `signal_intersection_ops` · `corridor_simulation` · `multimodal_digital_twin` ·
`odme_calibration` · `highway_sensor_timeseries` (ITS data hub) · `rail_freight_network` · `teaching_problem`

A manifest entry names its `category`, `required_files`, `capabilities`, and — critically — a **`qa_contract`**.

## 5. The QA gate (why the GUI is "intelligent")

**Not** `file exists → show dashboard`. Instead: `schema ✓ → spatial ref ✓ → topology ✓ → timestamps ✓ →
units ✓ → analysis-specific QA ✓ → show`.

| dataset type | mandatory QA |
|---|---|
| GMNS network | node/link connectivity, direction, geometry, units |
| corridor sensor | station order, missing intervals, speed/flow units |
| trajectory | timestamp gaps, coordinate bounds, speed/accel bounds |
| ODME | count coverage, assignment connectivity, residual diagnostics |
| GTFS | required files, stop-to-network snap, service calendar |
| rail | yard-node match, train-event sequence, milepost/LRS |

## 6. City by city, transferable (data hub)

The whole point is **transferability**: the same pipeline moves from Tempe → any city.

1. **Get the map** — `osm2gmns` on the city's OSM extract. For **ADOT** (Arizona), run osm2gmns on the
   statewide/metro extract to produce the big base map, then geofence to a corridor/subarea.
2. **Add what you have** — demand, signals, GTFS, sensors, probe/TMC. Missing layers just switch off; the
   dashboard degrades gracefully.
3. **Catalog it** — add a manifest entry (category + required_files + qa_contract).
4. **Generate** — `gui4gmns generate` → dashboard + figures + portals; `kepler_demo.py` → live map.
5. **Publish** — drop the outputs into `docs/templates/` (gallery) or `docs/portal_demo/<city>/` (live).

Same five steps, any city. The **data hub** (I-95) is the fully-fused example; the **template gallery**
(`docs/templates/`) is the menu of what each integrated result can look like.

---
*This file is the shippable skill. To use it as a Claude Code skill, drop a copy at
`.claude/skills/gmns-to-dashboard/SKILL.md`. Restricted templates (I-17/CBI, NVTA) are intentionally excluded
from the public gallery — see `docs/DATASETS_COVERAGE.md`.*

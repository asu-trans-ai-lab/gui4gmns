# ITS I-95 (VA) — multi-source data-hub SAMPLE

**Data source:** the multi-source I-95 dataset comes from the USDOT JPO CodeHub
**Data Cleaning and Fusion Tool** — https://github.com/usdot-jpo-codehub/data-cleaning-and-fusion-tool
(Fredericksburg/Stafford VA corridor), released as **public ITS demonstration data**. This is the published
flagship data hub: GMNS network + INRIX/RITIS TMC speed + VDOT loop sensors + probe trips/waypoints + OD,
fused into one corridor. Live: [data hub](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i95/datahub.html)
· [Kepler.gl](https://kepler.gl/demo?mapUrl=https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i95/map.kepler.json)
· [Google Earth](https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/i95/gmns.kml). (Only the multi-GB
raw source stays out of the repo; this extracted sample ships.)

Space-saving sample extracted from the 2.3 GB source (`../../../../_raw_sources/08_public_ITS_VA_1-95/`, moved out of the repo tree) by
`../../templates/adapters/its_i95_sample.py`. **2.3 GB -> 5.2 MB**, all six ITS layers preserved for
Fredericksburg/Stafford VA, 2024-08-05:

| layer | file | source |
|---|---|---|
| GMNS network | `network/node.csv`, `network/link.csv` (+ crosswalks) | OSM-derived |
| TMC speed (15-min) | `tmc_speed_15min.csv` | INRIX / RITIS |
| loop sensors | `sensor_points.csv`, `sensor_15min.csv` | VDOT detectors |
| probe trips | `trips.csv` (link-id paths + times) | probe trajectories |
| GPS waypoints | `waypoints.csv` (downsampled 1/180) | probe GPS |
| probe OD | `od.csv` (top 300 pairs) | probe OD |

Open **`its_datahub.html`** (self-contained, 4.2 MB) — toggle each layer, scrub the 15-min clock,
play the day. Regenerate: `python ../../templates/adapters/its_datahub.py .`
Re-extract a different day/size: `python ../../templates/adapters/its_i95_sample.py <src> <out> --day 2024-08-05 --trips 300`

Catalog entry: `templates/catalog/dataset_catalog.json` -> `public_ITS_VA_I95` (category `highway_sensor_timeseries`).

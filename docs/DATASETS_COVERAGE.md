# Dataset coverage — one flagship (all capabilities) + partial-coverage demos

The showcase strategy: **one comprehensive network exercising every visualization capability**, plus
several networks that each light up a subset — so a reviewer sees the full range without one giant
dataset hiding the individual features.

> **What ships publicly:** **Chicago Sketch** is the public showcase (richest shipped coverage). ITS I-95
> is a **local-only** demo — it fuses INRIX TMC + VDOT sensors + probe data, which are restricted and
> **never committed** (guarded in `.gitignore`); it is rendered locally for demonstration, not shipped.

| dataset | network | MOE (vol/VC/queue) | time-dep MOE | QVDF/TMC speed | paths / bundle | trajectories | space-time contour | sensors | OD | 3D/KML export |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **ITS I-95 (VA)** — local demo, **not shipped** | ✓ | ✓ | ✓ | ✓ (TMC) | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Chicago Sketch** ★ PUBLIC SHOWCASE | ✓ | ✓ | ✓ | (BPR) | ✓ | ✓ (+auto-synth) | ✓ | – | – | ✓ |
| ARC Atlanta (145k) | ✓ | ✓ | – | – | – | – | – (static profile) | – | – | ✓ |
| NVTA I-395 (TMC, local) | ✓ | ✓ | ✓ | ✓ (QVDF+INRIX) | – | (semi-dyn) | ✓ real breakdown | – | – | ✓ |
| Tucson (I-10) | ✓ | ✓ | – | – | – | – | – (static profile) | – | – | ✓ |
| West Jordan (UT) | ✓ | ✓ | – | – | ✓ (routes) | – | – | – | ✓ | ✓ |
| Sioux Falls | ✓ | – | – | – | – | – | – | – | ✓ | – |
| toy bottleneck/merge/signal | ✓ | ✓ | ✓ | – | – | – | ✓ (teaching) | – | – | – |

**ITS I-95 (VA)** is the **local-only** demo for **digital-infrastructure demonstration**: one corridor
fusing GMNS network + INRIX TMC speed + VDOT loop sensors + probe trajectories + GPS waypoints + probe OD
— the "connect-from-the-DataHub" data hub (`adapters/its_datahub.py`, `its_datahub.html`). Data source:
the USDOT JPO CodeHub **Data Cleaning and Fusion Tool**
(https://github.com/usdot-jpo-codehub/data-cleaning-and-fusion-tool). Because the
speeds/sensors/probes are INRIX/VDOT-restricted, **this dataset and its rendered dashboard are never
committed** (`datasets/08_public_ITS_VA_1-95_sample/` is git-ignored). It demonstrates the full capability
locally; the **shipped** public showcase is **Chicago Sketch** (network + MOE + time-dependent flow +
paths/bundle + trajectories + space-time contour + 3D/KML export).

**NVTA I-395** uses the **TMC-converted GMNS corridor network** (`cases/05_nvta_nb_am/network/`) — small,
corridor-only — for the real congested space-time speed contour (green free-flow -> red AM breakdown).
Kept local (INRIX-derived speeds are restricted); rendered for review, not committed.

**I-210E corridor state-views** (`docs/dashboards/I210E_*.html`) are gui4gmns samples that demonstrate
the corridor time-series capability: **calendar** (whole year by day/year), **network** (corridor map by
mean speed), **space-time** (milepost×time speed heatmap). Corridor speeds derive from **Caltrans PeMS**
(public agency data), packaged in the released **TrafficFlowBench-CA** benchmark. **Cleared for public
release** — attributed in each page footer and the gallery corridor section. They are the template for the
"ask the AI for more" capability: the same three views can be generated for other corridors (e.g. ITS I-95)
or other years from a GMNS network + a link speed / `link_performance` table (or an AI solver's output).

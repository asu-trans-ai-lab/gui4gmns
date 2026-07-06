# Dataset coverage — one flagship (all capabilities) + partial-coverage demos

The showcase strategy: **one comprehensive network exercising every visualization capability**, plus
several networks that each light up a subset — so a reviewer sees the full range without one giant
dataset hiding the individual features.

| dataset | network | MOE (vol/VC/queue) | time-dep MOE | QVDF/TMC speed | paths / bundle | trajectories | space-time contour | sensors | OD | 3D/KML export |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **ITS I-95 (VA)** ★ FLAGSHIP | ✓ | ✓ | ✓ | ✓ (TMC) | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Chicago Sketch | ✓ | ✓ | ✓ | (BPR) | ✓ | ✓ (+auto-synth) | ✓ | – | – | ✓ |
| ARC Atlanta (145k) | ✓ | ✓ | – | – | – | – | – (static profile) | – | – | ✓ |
| NVTA I-395 (TMC, local) | ✓ | ✓ | ✓ | ✓ (QVDF+INRIX) | – | (semi-dyn) | ✓ real breakdown | – | – | ✓ |
| Tucson (I-10) | ✓ | ✓ | – | – | – | – | – (static profile) | – | – | ✓ |
| West Jordan (UT) | ✓ | ✓ | – | – | ✓ (routes) | – | – | – | ✓ | ✓ |
| Sioux Falls | ✓ | – | – | – | – | – | – | – | ✓ | – |
| toy bottleneck/merge/signal | ✓ | ✓ | ✓ | – | – | – | ✓ (teaching) | – | – | – |

★ **ITS I-95 (VA)** is the flagship for **digital-infrastructure demonstration**: one corridor fusing
GMNS network + INRIX TMC speed + VDOT loop sensors + probe trajectories + GPS waypoints + probe OD —
the "connect-from-the-DataHub" data hub (`adapters/its_datahub.py`, `its_datahub.html`).

**NVTA I-395** uses the **TMC-converted GMNS corridor network** (`cases/05_nvta_nb_am/network/`) — small,
corridor-only — for the real congested space-time speed contour (green free-flow -> red AM breakdown).
Kept local (INRIX-derived speeds are restricted); rendered for review, not committed.

# gui4gmns sample datasets — see docs/gui4gmns_Users_Guide.md §9
01_sioux_falls (classic 24-node) · 02_chicago_sketch (full DLSim package: MOE + 26 TD bins + 250
paths + 30k vehicle trajectories + run/gridlock) · 03_chicago_regional (39,018 links, 20k vehicles) ·
04_arc_atlanta (145,971 links, real DTALite assigned volumes) · 05_toy_* (bottleneck/merge/signal
teaching cases with 15-min TD animation). Open with any branch:
  web:     python -m http.server 8765   ->  nexta_x.html?data=datasets/02_chicago_sketch
  desktop: python desktop-qt/nexta_qt.py datasets/02_chicago_sketch
Attribution/disclaimers: dynamic-odme-lab DATA_SOURCES.md (Sioux Falls/Chicago: Transportation
Networks repo; ARC: converted research copy — ARC retains all rights).

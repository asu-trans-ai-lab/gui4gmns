# gui4gmns / web-gl — GPU animation + live-follow (NEXT UP)
Stack: WebGL (deck.gl-class TripsLayer, bundled offline, no CDN) + tiny Python run-server that tails a
run folder (websocket push of new 15-min bins / trajectory chunks while DLSim or DTALite runs).
Unique: per-vehicle animation at regional/NGSIM scale; live-follow; basemap. Conformance: contract §4.
Milestones: M1 static GPU render of Chicago Regional (39k links) · M2 TripsLayer trajectories (>=100k
agents) · M3 run-server live-follow · M4 offline bundle + Tauri desktop wrapper (optional).

## Status (2026-07-02) — M1+M2+M3 VERIFIED
Implemented as **raw WebGL2 in one self-contained file** (`nexta_xgl.html`) — no deck.gl, no bundler,
zero-install property preserved. Trips technique: one GPU point per trajectory segment
`(x0,y0,x1,y1,t0,t1,queued)`, position interpolated in the vertex shader from uniform `u_time`
(green = moving, red = queued); links drawn as normal-extruded quads with per-bin MOE color/width.
- **M1/M2 (scale)**: Chicago Regional — 39,018 links (234k quad verts) + **746,892 trip segments**
  (20k agents) draw in **0.02 ms/frame**, 0 GL errors; Sketch demo: 307k segments from 30k agents.
- **M3 (live-follow)**: checkbox polls the served folder every 5 s (plain `python -m http.server`,
  no custom server); verified end-to-end (file mutated -> auto refetch -> "live update" status).
Demos: `?data=../demo` (Sketch, 30k agents) · `?data=demo_regional` (Regional, 20k agents).
Next: M4 optional Tauri wrapper; sensor/ODME overlays; smooth polyline-following dots (currently
straight-line within link).

# fx_synth — semi-dynamic trajectory synthesis fixture (adapters, L4→L5)

A 3-node / 2-link corridor with **paths + time-dependent link performance but NO agent trajectory** —
the exact situation `adapters/semidynamic_trajectories.py` (and the generator's built-in auto-synth)
exist for: propagate vehicles along their paths using the link travel time at each entry, turning
Eulerian (per-link) results into Lagrangian (per-vehicle) animatable trajectories.

Every value is chosen so travel time is unambiguous physics — the 15-min data carries a `speed` column,
so `tt = length / speed`:

| link | length (mi) | free_speed | 07:00 speed → tt | 07:15 speed → tt |
|---|---|---|---|---|
| 1 (1→2) | 1.0 | 60 | 60 → **1.0 min** | 30 → **2.0 min** |
| 2 (2→3) | 1.0 | 60 | 20 → **3.0 min** | 60 → **1.0 min** |

Path: `link_ids = 1;2`. A vehicle entering link 1 during the 07:00 bin should take 1.0 min on link 1,
then (entering link 2 still in the 07:00 bin) 3.0 min on link 2 — slowing to a crawl exactly where the
data says link 2 is congested.

## What this fixture verifies

Two independent synthesis paths, both exercised:

1. **The standalone adapter** — `qa/verify_semidynamic.py` runs `adapters/semidynamic_trajectories.py`
   on this folder, then asserts **every** synthesized `(ENB→EXB)` traversal equals `length / speed` from
   the 15-min `speed` column — an independent first-principles ground truth (method M-B), not a
   reimplementation of the adapter's internal BPR logic. Result: **4000/4000 traversals exact**. Proven
   to have teeth: perturbing the adapter's tt formula makes the check fail.

2. **The generator's built-in auto-synth** — `gui4gmns.py` fires its inline "auto sim2trajectory" block
   when a dataset has paths + time-dependent performance but no real trajectory. `verify_output.py`
   confirms the resulting animation covers 2/2 links (100%).

## Use

```
python qa/verify_semidynamic.py datasets/fixtures/fx_synth   # adapter, checked against distance/speed
python ai-gen/gui4gmns.py datasets/fixtures/fx_synth          # built-in auto-synth -> animated dashboard
python qa/verify_output.py datasets/fixtures/fx_synth         # topology + auto-synth animation coverage
```

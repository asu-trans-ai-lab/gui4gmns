# fx_grid — comprehensive hand-verifiable fixture

A deliberately tiny synthetic GMNS network (6 nodes / 6 links, ~1 mi across, near Tempe AZ) whose every
value is chosen so the *expected* visualization can be computed by hand. It exercises input levels
**L1–L6** at once (network → demand → static MOE → time-dependent → trajectories → observed corridor).

On a 2950-link showcase you can only say "looks right"; here you can say "agent 0 at t=0.5 is at 40% of
link 1, exactly." The golden values live in [`EXPECTED.json`](EXPECTED.json) and are asserted by
`qa/verify_output.py --fixture` (method M-D in `qa/TEST_PLAN.md`).

All data is synthetic — no agency/private source.

## The network

```
   4 ── L3 ──▶ 5 ── L4 ──▶ 6          rows at y=33.430 (zones 3, ·, 4)
   │                                   L5: 2→5 (vertical)
   L6 (1→4)                            L6: 1→4 (vertical)
   │
   1 ── L1 ──▶ 2 ── L2 ──▶ 3          rows at y=33.420 (zones 1, ·, 2)
```

| link | from→to | lanes | cap/lane | free_speed | type | length(mi) |
|---|---|---|---|---|---|---|
| 1 | 1→2 | 1 | 1800 | 25 | 1 | 0.6 |
| 2 | 2→3 | 2 | 1800 | 35 | 1 | 0.6 |
| 3 | 4→5 | 3 | 1800 | 45 | 2 | 0.6 |
| 4 | 5→6 | 2 | 1800 | 55 | 2 | 0.6 |
| 5 | 2→5 | 1 | 1800 | 30 | 3 | 0.7 |
| 6 | 1→4 | 1 | 1800 | 40 | 3 | 0.7 |

Chosen so the static figures light up meaningfully: `by_lanes` (lanes 2–4 → links 2,3,4), `by_link_type`
(3 classes), and the free-speed / capacity distributions all have real spread. No link is a connector
(max cap·lanes = 5400 « 40000), so nothing pollutes the real-road stats.

## Hand-computed expectations

**MOE / V·C** (V/C = volume ÷ (cap/lane × lanes)):

| link | volume | total cap | V/C | queue |
|---|---|---|---|---|
| 1 | 900 | 1800 | **0.50** | 0 |
| 2 | 3600 | 3600 | **1.00** | 50 |
| 3 | 1350 | 5400 | **0.25** | 0 |
| 4 | 2700 | 3600 | **0.75** | 0 |
| 5 | 450 | 1800 | **0.25** | 0 |
| 6 | 1800 | 1800 | **1.00** | 30 |

**Conservation:** `run_summary.json` = 3 agents / 3 completed → audit "conservation OK 3/3".

**Corridor "Main"** (`corridor_speed.csv`, 3 segments × 3 times = 9 cells, all speeds > 0). With every
cell's |observed − model| = 2 mph:
- **RMSE** = √(mean(2²)) = **2.0** mph
- **bias** = mean(model − obs) = (+2·5 − 2·4)/9 = 2/9 = **0.22** mph
- observed mean = 40; SST = Σ(obs−40)² = 1500; SSE = 9·4 = 36 → **R² = 1 − 36/1500 = 0.976**
- free-flow = **60**

**Trajectories** (3 vehicles, hand-written events; position along a link at clock t is linear between
the bracketing events). Sample assertions (agent, t → link, fraction):
- agent 0 at t=0.5 → link 1 @ 0.50; at t=1.5 → link 2 @ 0.50
- agent 1 at t=0.5 → link 6 @ 0.50; at t=1.5 → link 3 @ 0.50
- agent 2 at t=1.0 → link 1 @ 0.50; at t=2.0 → link 2 @ 0.50

Coverage: 3 agents traverse links {1,2,3,4,6} = 5 of 6 links (link 5 carries none, by design).

## Use

```
python ai-gen/gui4gmns.py datasets/fixtures/fx_grid          # generate
python qa/verify_output.py datasets/fixtures/fx_grid          # M-A invariants + M-D golden (EXPECTED.json)
```

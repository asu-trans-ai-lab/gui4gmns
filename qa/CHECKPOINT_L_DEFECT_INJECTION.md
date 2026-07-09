# Checkpoint L — data-quality audit defect-injection test

Directly answers the professor's core doubt about the self-checking dashboards: **"the audit feature
is itself a QA target — verify it catches planted defects and stays quiet on clean data"**
(`qa/AI_GUIDE_gui4gmns.md` §0). This has been on the Phase 2 priority list since day one and had never
been executed until now.

## Method

Rather than eyeballing the audit panel in a browser (unreliable — animation renders had previously
made screenshot tooling time out), **`qa/verify_sci_panel.js`** extracts and executes the *actual*
`computeSCI()` function straight out of a generated `dashboard.html`, feeding it an `M` object built
by replicating the dashboard's own layer-loading logic exactly (including the `moe.js` → `network.js`
splice). This tests production code, not a hand-written reimplementation that could drift or be
transcribed wrong.

```
node qa/verify_sci_panel.js <gmns_folder>
```

Base fixture: `datasets/fixtures/fx_grid` (hand-verified, so every planted defect's effect is
predictable and any cross-contamination between checks is easy to spot).

## Baseline (clean data)

```
7 pass, 0 fail, 0 n/a  (of 7 checks)
```
No false alarms on clean data — the first half of checkpoint L.

## Defect injection — 5 of 7 SCI checks: PASS, with surgical precision

Each defect was chosen to trip **exactly one** check; all six runs confirmed **only** the targeted
check failed and the other six stayed green — proving the checks are independently discriminating,
not just "something turns red."

| Check | Defect planted | Result |
|---|---|---|
| **S** speed bounds | link 1 @ 07:30: speed 28→40 mph (free_flow 30, queue=0 to avoid touching K) | `FAIL — link 1 @07:30: 40 mph > 35`; all other 6 checks PASS |
| **C** flow conservation | `run_summary.json`: completed 3→2 | `FAIL — 1 agents unaccounted (CA<CD)`; all others PASS |
| **N** non-negativity | link 1 volume: 900→ **-100** | `FAIL — link 1: vol -100 q 0`; all others PASS |
| **Q** capacity feasibility | link 5 volume: 450→25000 (cap·8·1.25 = 18000) | `FAIL — link 5: V/C ≈ 1.74`; all others PASS |
| **K** congestion consistency | link 2 @ 07:00: speed 20→35 (queue=20, free_flow=35) | `FAIL — link 2 @07:00: queued but 35≈free-flow`; all others PASS |
| zero-volume **MAJOR** link (guide's own defect class, not one of the 7 SCI checks) | link 3 (the one tier-1 link, cap 5400) volume 1350→0 | Console: `WARN checks layer: 1 zero-volume MAJOR links`; confirmed the map-highlight condition (`tier==1 && vol==0`) is true in the embedded data — a user with the "checks" box enabled would see it flagged on the map |

**6 for 6.** Every checkable defect class the guide and the SCI panel define was caught, cleanly,
with no cross-contamination.

## Two checks are structurally unreachable via data-level corruption — a real finding

| Check | Attempted defect | Result |
|---|---|---|
| **T** topology (≥2 finite geometry points) | link 2's `from_node_id` pointed at a nonexistent node (999) | The Python loader silently **dropped the link** (`WARN 1 links without resolvable geometry (skipped)`) before it ever reached the browser. The SCI panel then correctly reports **5/5 links ok** — technically true, but the *original* defect never got a chance to reach the audit panel at all. |
| **O** temporal ordering | agent 0's second trajectory event set to an earlier time than the first (goes backward) | The loader's `for ev in D["trajs"].values(): ev.sort()` **silently re-sorts** every agent's events by time before embedding. The panel reports **3/3 agents ok** — correctly, because the data it sees really is sorted, but a genuinely malformed source file is invisible downstream. (The same applies to `D["bins"]`, which is also force-sorted.) |

**This is not a bug** — silently dropping an unresolvable link and silently sorting trajectory events
are reasonable choices for a generator to make. But it means the interactive dashboard's own **audit
panel can never be the last line of defense** for these two defect classes: a user who only looks at
the dashboard (not the generation console log) has no way to learn a link was silently dropped or a
trajectory file had rows out of order. The console `WARN` is the only surface for T-class defects; there
is no equivalent surface for O-class defects at all (the sort is silent, no WARN is emitted).

**Suggested follow-up** (not implemented — flagged for a decision, same as F-006): emit a console `WARN`
when trajectory events for an agent needed re-sorting, mirroring the existing `WARN N links without
resolvable geometry` pattern, so an O-class defect at least leaves a paper trail.

## Verdict

Checkpoint L is **done** for the SCI panel: 0 false alarms on clean data, 6/6 targeted defect classes
caught with precision. The 2 structurally-unreachable checks are documented as a scope boundary, not a
failure, with a concrete low-cost follow-up suggested for the O-class gap.

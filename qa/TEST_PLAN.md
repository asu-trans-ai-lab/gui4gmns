# gui4gmns — Visualization Acceptance Test Plan

**Why this exists.** Our first pass at QA tested the *developer's* question — "does it run without an
error?" — and passed things that were, from a *user's* seat, wrong or empty: an animation covering 1%
of the network, a "corridor contour" that rendered blank, distributions polluted by placeholder values,
a quickstart that produced an empty map, an export counter that lied. Every one of those ran without
raising. This plan makes QA test **both lenses on every artifact**:

- **Developer lens** — does it run, load, and stay within budget? (no errors, no failed requests, no
  crashes, sizes/timing sane)
- **User lens** — did the user get what they came for, and is it *correct and honest*? (the picture
  matches the data, nothing claimed is empty, derived numbers check out, units/legends are present, no
  fabricated or misleading elements)

A cell **passes only when both lenses pass.** "It generated" is necessary, not sufficient.

This plan complements `qa/AI_GUIDE_gui4gmns.md`: the guide's checkpoints **A–N** say *which artifact /
feature* to look at; this plan adds the **correctness dimensions (D1–D10)** that define what "pass"
*means* for each, the **methods (M-A–M-F)** for proving it, and the **input ladder (L1–L7)** that
decides which checks apply. It also formalizes the two proposed checkpoints **O** (effective output)
and **P** (first-run experience).

---

## 1. The user's contract

Frame every test as a promise: *"the user brings input X; we promise output Y; each property of Y has a
checkable correctness criterion."* Testing = verifying the contract holds. The loop for any scenario:

> **What they bring (input) → what they expect to see (output) → what "correct" means for each output
> (verification).**

---

## 2. Input ladder (L1–L7) — what a user actually brings

Expected outputs are unlocked layer by layer. A comprehensive suite needs a dataset (ideally a
hand-verifiable fixture, §7) at **every** level — today the shipped datasets only cover a few, which is
why capabilities like the corridor contour (L6) and trajectories (L5) had thin or no coverage.

| Level | User brings (files) | Their goal | Unlocks |
|---|---|---|---|
| **L1** network only | node, link | QC the topology | network/nodes/zones figures, by-attribute & distribution figures |
| **L2** + demand | + demand / OD | see demand pattern | OD desire lines, demand matrix heatmap, zones |
| **L3** + static assignment | + link_performance | see congestion (MOE) | volume / V/C / queue coloring + legend |
| **L4** + time-dependent | + link_performance_15min | see time-varying congestion | time-dependent MOE, time slider, QVDF speed layer |
| **L5** + simulation | + agent_trajectory / path_flow | watch vehicles move | animated vehicles (green moving / red queued), trails, `--max-traj` |
| **L6** + observed corridor | + corridor_speed / TMC | validate against reality | INRIX-vs-model space-time contour, RMSE / R² / bias |
| **L7** + rich attributes | + zone polygons, lane, movement, poi | lane/intersection detail | lane-offset figure, turning-movement figure, POI, zone polygons |

Every level also expects the **always-on** promises: self-contained & offline, the four portal
exports, the static PNG catalog, and the data-quality audit panel.

---

## 3. Expected-output inventory

For each artifact the tool produces, its *reason to exist* (what the user reads from it). "Correct"
in §4 is judged against this intent.

| Artifact | The user should be able to read… |
|---|---|
| Network / nodes / zones figures | the shape and extent of the network; where zones/centroids are |
| by-attribute figures (link_type, free_speed, lanes, length) | where each road class / speed band / lane count / length band is |
| distribution histograms (capacity, free_speed, lanes) | the spread of each attribute across **real roads** |
| MOE coloring (volume, V/C, queue) | where it's congested, quantitatively, against a legend |
| time-dependent MOE + slider | how congestion evolves across the modeled period |
| animation (vehicles + trails) | how vehicles actually flow across the **whole** network |
| OD desire lines + demand heatmap | the dominant travel patterns and their magnitudes |
| corridor space-time contour + stats | how the model matches observed speeds, quantified |
| data-quality audit panel | whether the inputs are physically consistent |
| portal exports (kepler/deckgl/qgis/kml) | the same network/MOE, faithfully, in their tool of choice |

---

## 4. Correctness dimensions (D1–D10) — the ways a visualization is "wrong" even when it runs

**This is the core of the plan.** A visualization can pass the developer lens and still fail the user.
Each dimension has a definition, how to check it, and a real bug from this project that is an instance
of it — proof these are concrete, not abstract.

| # | Dimension | "Correct" means | How to check (method §5) | Instance we hit |
|---|---|---|---|---|
| **D1** | Fidelity to input | drawn counts/values/geometry equal the data | M-A counts; M-B spot-recompute | — (baseline) |
| **D2** | Completeness | everything that should appear does; nothing claimed is empty | M-A per-layer non-empty; M-F | **F-009** vehicles on undrawn links; **F-006** empty corridor |
| **D3** | No misrepresentation | sampling unbiased; binning/scale/color mapping faithful | M-A coverage %, M-D golden | **F-008** biased sample; **F-010** polluted bins, hardcoded range |
| **D4** | Derived-quantity correctness | computed stats (V/C, RMSE, R², conservation, percentiles) are right | M-B recompute from CSV by hand | to verify: audit totals, corridor stats |
| **D5** | Interpretability | units, legend, scale, readable labels all present & correct | M-A presence check + M-E eye | **F-010** no-unit axis, raw "1/2/3" legend |
| **D6** | Cross-view consistency | same quantity agrees across dashboard / figure / portal / geojson | M-C compare extracts | to verify |
| **D7** | Honesty / no silent failure | claims match reality; missing→clear message, not blank/lie | M-A + read the console | **F-010** "15 figures" but 8 written; by_length silent no-op |
| **D8** | Graceful degradation & environment | missing optional data degrades clearly; offline truly offline; pip == repo | M-A no external refs; M-D pip-vs-repo | **F-007** empty quickstart, pip-only dead-end |
| **D9** | Geographic correctness | CRS projected right; aligns with basemap; no mirror/offset | M-B coord check + M-E eye | to verify (CRS path) |
| **D10** | Temporal correctness | time bins ordered; vehicle direction right; frame T == data bin T | M-B frame spot-check + M-E eye | to verify |

Mapping to the guide's checkpoints A–N (+O/P): the checkpoints are the *rows* (which artifact); D1–D10
are the *criteria* applied within each. E.g. checkpoint **D (MOE)** must satisfy D1 (counts), D3 (color
mapping), D4 (V/C recompute), D5 (legend/units). Checkpoint **O (effective output)** = D2 made
mechanical (every claimed layer non-empty & non-degenerate). Checkpoint **P (first-run)** = D8 for the
README quickstart datasets.

---

## 5. Verification methods (M-A – M-F), highest-confidence first

| Method | What it is | Best for | Automatable? |
|---|---|---|---|
| **M-A** Machine invariants | script asserts counts, non-empty layers, no external URLs, sizes/timing, no sentinel pollution | D1, D2, D3, D5(presence), D7, D8(offline) | **yes** → `qa/verify_output.py` |
| **M-B** Ground-truth recompute | independently compute a value from raw CSV, compare to what's shown | D1(spot), D4, D9, D10 | partly |
| **M-C** Cross-view consistency | extract the same quantity from ≥2 representations, assert equal | D6 | yes |
| **M-D** Golden reference | store key numbers/screens for a fixed fixture; diff on every run | regression across all D | yes |
| **M-E** Human eye | judgment on the genuinely subjective, with the screenshot **pre-prepared** | D5(aesthetic), D9/D10(plausibility) | no (`needs_human`) |
| **M-F** Fixture coverage | purpose-built tiny datasets so every capability has a controlled, hand-checkable test | prerequisite for all | — |

Rule: push each check to the **highest** method it can reach. Anything M-A can assert should not be
left to M-E. Human eyes are the last resort, not the default.

---

## 6. Execution matrix (how to actually run a cell)

For a given `dataset × component`, determine the input level (§2), then walk the applicable checkpoints;
for each checkpoint apply its correctness dimensions via the highest method:

```
pick dataset + component
  -> input level L? -> which checkpoints A..P apply (per DATASETS_COVERAGE + this plan)
  -> for each checkpoint: run its D-dimensions
       M-A invariants (auto)  -> pass/fail with reason
       M-B recompute one value by hand where D4/D1 applies
       M-C compare across views where D6 applies
       remaining subjective -> screenshot + needs_human (M-E)
  -> verdict = pass only if BOTH lenses (dev: ran/loaded/in-budget; user: D-dimensions) pass
  -> evidence + note -> qa_report.html ; fail/partial -> issue
```

---

## 7. Fixture datasets (`datasets/fixtures/`) — the missing foundation

The deepest reason the first pass wasn't comprehensive: datasets were "test what we happen to have,"
not "designed to cover the capability matrix." Only Chicago had trajectories; **no** dataset ships a
`corridor_speed.csv`; multi-lane figures were empty everywhere. Fix this with **tiny, hand-verifiable
fixtures** — small enough that every expected value can be computed by hand and asserted exactly (on
Chicago you can only say "looks right"; on a 4-link net you can say "vehicle 3 at t=5 is at 40% of
link 2, exactly").

Proposed minimal set (each isolates one capability, all public/synthetic):

| Fixture | Adds | Makes hand-checkable |
|---|---|---|
| `fx_grid_traj` | 4 nodes / 4 links / 3 vehicles, hand-written trajectory | animation frame positions, coverage %, connector underlay |
| `fx_corridor` | 3-segment corridor + `corridor_speed.csv` | the contour renders; RMSE/R²/bias recomputed by hand |
| `fx_multilane` | links with lanes 1–4, zone polygons, POI | by_lanes figure, lane-offset figure, zone polygons, POI |
| `fx_moe` | tiny net + link_performance with known volumes | V/C coloring maps to the right legend band |
| `fx_crs` | a net in a projected CRS (state-plane) + `crs.txt` | reprojection lands on the correct lon/lat (D9) |

---

## 8. Definition of done (per artifact, both lenses)

A `dataset × component` cell is **pass** when, for every applicable checkpoint:

1. **Dev lens:** loads from `file://` with zero console errors, no failed external requests, within the
   size/time budget.
2. **User lens (D1–D10 as applicable):** counts match the input; every claimed layer is non-empty and
   non-degenerate; at least one derived quantity was recomputed and agreed; units/legend present; the
   same quantity is consistent across views; the console/report claims match what was actually produced;
   missing optional inputs degrade with a clear message.
3. **Evidence** recorded (invariant output, recomputed number, or prepared screenshot). Any fail/partial
   has an issue. Genuinely subjective residue is `needs_human` with the screenshot ready.

---

## 9. Rollout

1. **This document** — the shared definition of "what correct means," agreed with Prof. Zhou.
2. **`qa/verify_output.py`** — the M-A invariant harness (**built**). Give it any generated GMNS folder;
   it prints `PASS/FAIL/NA + reason` for every machine-checkable dimension (D1, D2, D3, D7, D8),
   input-level aware (checks that don't apply to a dataset report `NA`, not `FAIL`), exit 1 on any
   `FAIL`. Turns O/P into code. Self-tested: injecting a clustered trajectory sample (F-008), a deleted
   portal, and an external URL each produce `FAIL`.
   ```
   python qa/verify_output.py datasets/02_chicago_sketch
   ```
3. **`datasets/fixtures/`** — the hand-verifiable fixtures from §7, so every capability has a controlled
   test with a known answer. *(next)*
4. Re-walk the QA matrix under this plan; the two-lens verdict replaces the old "it generated" pass.

### Current results (M-A harness)

| dataset | result |
|---|---|
| chicago_sketch (L5) | **7 pass, 0 fail** — topology, MOE values, layers, animation (3000 agents / 394 links / 100% id-span), offline, portals, figures all green |
| west_jordan (L3) | 6 pass, 1 n/a (no trajectories) |
| sioux_falls / toys (L1–L2) | 5 pass, 2 n/a (no MOE, no trajectories) |

Machine-checkable dimensions are green on every shipped dataset. What remains per cell is the human-eye
residue (M-E): D4 recompute of audit/corridor stats, D5 legend aesthetics, D9/D10 geographic & temporal
plausibility — plus the corridor contour (D2/M) still blocked on F-006.

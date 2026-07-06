# Review from the lens of the TRB Standing Committee on Visualization in Transportation (AED30)

A structured critique of the NeXTA/gui4gmns MOE gallery — Traffic-Speed bandwidth, Bottleneck /
congestion-age, Queue duration, and the dynamic Speed Contour (see `docs/2_NeXTA_Visualization.pptx`
and `docs/moe_gallery/`) — written as a committee would review a candidate visualization method:
against perceptual effectiveness, accessibility, reproducibility, and fitness for practice. Comments are
paired with improvement plans and mapped to the roadmap.

## What is strong (keep)
- **Bandwidth (width = volume) is Tufte/– sound**: an honest area-proportional encoding of flow; the
  eye reads corridor loading instantly. NeXTA has done this well for 15+ years.
- **Space-time speed contour** (Edie/Treiterer lineage) is the single most information-dense traffic
  view: it exposes shockwaves, queue growth/discharge, and bottleneck activation on one axis pair.
  Keeping distance-on-y / time-on-x with a speed colorbar is textbook-correct.
- **Congestion-*age*** (bottleneck new-vs-1-hour-old) is a genuinely good idea rarely seen elsewhere —
  it encodes *when* a bottleneck formed, not just that it exists.
- **Both interactive and static** outputs now exist (dashboard + `moe_static.py` PNGs) — practitioners
  need report-ready figures, not only a live tool.

## Comments → improvement plans
| # | committee comment | severity | improvement plan |
|---|---|---|---|
| V1 | **Red–green ramps fail for ~8% of male viewers** (deuteranopia). | minor (per user) | **DEFAULT stays the intuitive green→red ramp** — practitioners read it instantly and it carries meaning first; colorblind-safe cividis/blue-red is an **opt-in** (`--cmap cb`). Mitigation kept: **redundant width encoding** (width = volume, color = speed), so a colorblind reader still gets flow from width. |
| V2 | **Rainbow/banded colormaps distort continuous fields** (perceptual non-uniformity creates false edges). | major | use perceptually-uniform colormaps for the space-time contours (matplotlib PNGs already use RdYlGn — switch continuous density/speed to `cividis`/`viridis`; reserve RdYlGn for the LOS-style *classified* speed bands only). |
| V3 | **Figures lack provenance** — a reader can't tell scenario, date, period, or units. | major (for practice) | stamp every static PNG with scenario name, analysis period, generator version, and a data-source line; add **scale bar + north arrow** to map PNGs. |
| V4 | **Space-time is shown for speed only**; density and flow complete the picture and tie to the fundamental diagram. | moderate | ship the **speed + density + flow** trio (density done, `moe_spacetime_density.png`); add an optional **q–k / v–k fundamental-diagram** panel sampled from the same cells. |
| V5 | **Double-encoding legends are cramped** (width legend + color legend competing). | moderate | separate the two legends; label width in real units (veh/h) and color as a classified LOS or a continuous bar with ticks. |
| V6 | **No uncertainty / coverage cue** — sparse or missing data reads identically to real free-flow. | moderate | render missing cells as hatched/neutral (the contour already leaves NaN white — make that explicit with a "no data" legend entry); in bandwidth, dim links with no observation. |
| V7 | **Accessibility of the interactive dashboard** (keyboard, text contrast, colorbar) trails the static PNGs. | minor | add a colorblind toggle + a visible colorbar to the dashboard MOE modes; ensure ≥4.5:1 text contrast. |
| V8 | **Corridor selection for space-time is manual.** | minor | auto-rank corridors (busiest/most-congested sorted-link chains) and offer a picker — the "sorted links → space-time" workflow the analyst already does by hand. |

## Verdict (committee-style)
The method set is **publication-worthy and practice-relevant**; its gaps are the field's usual ones —
**colorblind safety, perceptual colormaps, and figure provenance**. None require new science; all are
craft. Addressing V1–V3 would move these from "good research figures" to "figures an agency can put in
a public report without a second thought."

## Mapped to the roadmap
- V1/V2/V7 → **new E9 Colorblind-safe + perceptual colormaps** (dashboard + PNGs).
- V3/V5 → **new E10 Publication furniture** (provenance stamp, scale bar, north arrow, split legends).
- V4 → extends **E4 MOE small-multiples** (add density/flow + FD panel).
- V6 → folds into the **SCI/data-quality** layer (coverage as a first-class cue).
- V8 → **E11 Corridor auto-ranking** for the space-time picker.

*(These are a Fable-5 synthesis of how the TRB visualization community reviews such methods — perceptual
effectiveness, accessibility, reproducibility, decision-relevance — not statements attributed to any
individual. To make it a real review, circulate `docs/moe_gallery/` + this file to AED30 members.)*

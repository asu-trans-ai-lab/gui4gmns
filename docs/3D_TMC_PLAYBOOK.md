# 3D TMC Playbook — event-driven corridor animation for gui4gmns

**What this is.** A Traffic-Management-Center-grade storyline and control playbook for the gui4gmns 3D
scene. It upgrades the loose language of `3D_VISUALIZATION.md` into precise traffic-operations vocabulary,
then scripts a scene-by-scene incident animation an operator could narrate live. Companion to
`3D_VISUALIZATION.md` (the *how-to-render*); this doc is the *what-it-means-and-how-to-read-it*.

**The discipline — "see, then believe."** Every visual cue below is tied to a real column in a shipped
gui4gmns dataset. If a field is not in the data, the layer does not exist — we do **not** paint invented
incidents, invented weather, or invented trajectories. The [Fidelity ladder](#6-fidelity-ladder) states
exactly what is honest to show at each data level. Ground truth for this doc:

- **Static assignment** — `datasets/07_west_jordan/link_performance.csv`
  (`volume, speed, speed_ratio, VOC, DOC, capacity, queue, avg_waiting_time_in_min, congestion_duration_in_h`).
- **Time-dependent link_performance (multi-bin)** — `datasets/*/link_performance_15min.csv`
  (`link_id, time_bin_start, inflow_veh, queue_exb` / `exb_queue_at_bin_start` = *existing/excess bottleneck queue*).
- **Real corridor time series** — `datasets/08_public_ITS_VA_1-95_sample/`:
  `tmc_speed_15min.csv` (INRIX/RITIS TMC speed by 15-min bin), `sensor_15min.csv`
  (VDOT loop `speed, volume, occupancy`), `waypoints.csv` (probe GPS `t_unix, lat, lon, speed_mph, heading`),
  `trips.csv` (link-id paths + start/end times), `od.csv` (probe OD pairs).
- **Event mechanism** — `control_event.csv`
  (`control_id, type, location_type, location_id, start_time, end_time, parameter, value, priority`;
  an incident ships as `type=incident, parameter=capacity_factor, value=0.50` on a link).

> Honesty flag used throughout: **[MEASURED]** = a real column exists in a shipped dataset ·
> **[MODELED]** = produced by DTALite/DLSim from inputs (e.g. a `capacity_factor` event) ·
> **[DERIVED]** = computed from measured/modeled fields (e.g. TTI from speed) ·
> **[NOT IN DATA]** = would require a source we do not ship — do **not** render it as fact.

---

## 1. Vocabulary upgrade

Replace vague/marketing language with the term a TMC actually uses. The right column is what the cue
*means*; the honesty flag says whether gui4gmns data can back it.

| Weak / vague term (avoid) | Precise TMC / traffic-science term | What it actually means | Honesty in gui4gmns |
|---|---|---|---|
| "traffic backing up" | **queue spillback** (queue growing upstream past the link where it formed) | queue on link *i* reaches its upstream end and blocks the junction feeding it | **[MODELED/MEASURED]** `queue_exb` rising bin-over-bin on consecutive upstream links |
| "the jam spreads into other roads" | **queue spillover** (queue crosses a node into a *different* facility, e.g. off-ramp queue backs onto the mainline) | spatial propagation of blockage across the network | **[MODELED]** DLSim spillback stage; **[MEASURED]** upstream TMC speed drop |
| "the slowdown moves back" | **shockwave / kinematic (Lighthill-Whitham-Richards) wave** | a moving boundary between two traffic states; a stopping wave travels **upstream**, a recovery wave follows | **[DERIVED]** the *bin-to-bin migration* of the low-speed front across ordered links |
| "the road narrows" | **taper** (lane-drop transition) and **gore point** (the paved triangle where a ramp diverges/merges) | fixed geometry that fixes where merge turbulence and bottlenecks recur | **[MEASURED]** link `lanes`, `facility_type`; ramp `lane_type` in `sensor_points.csv` |
| "capacity goes down in a jam" | **capacity drop** (discharge rate after breakdown is ~5–15% below pre-queue capacity) | the queue discharges *slower* than the flow that caused it — why clearing is sticky | **[MODELED]** via `capacity_factor<1`; **[DERIVED]** discharge vs `capacity` |
| "congestion starts" | **breakdown / onset of congestion** and **bottleneck activation** | the moment demand exceeds capacity at a fixed location and a queue begins to form | **[MEASURED]** first bin where `speed` falls through the FD knee / `VOC≥1` |
| "the crash" | **primary incident** vs **secondary crash** (a crash inside the queue *caused by* the first) | secondary-crash risk rises with queue length and speed differential | **[MODELED]** exposure window; the crash record itself is **[NOT IN DATA]** in the sample |
| "we cleared it" | **roadway clearance time** vs **incident clearance time** | *roadway clearance* = travel lanes reopened; *incident clearance* = all responders/debris gone. Two different clocks. | **[MODELED]** `control_event` `start_time`→`end_time`; real timestamps **[NOT IN DATA]** |
| "handling the crash" | **TIM — Traffic Incident Management**; phases: **detection → verification → response → clearance → recovery ("return to normal")** | the standard incident lifecycle every TMC runs on | framing only; drives the [storyline](#3-event-driven-storyline--playbook) clock |
| "coordinating the freeway and the streets" | **ICM — Integrated Corridor Management** | jointly managing freeway + arterial + transit + ramps as one corridor | **[MODELED]** diversion in demand/assignment; requires arterial network |
| "smart-highway tools" | **ATM — Active Traffic Management** | the toolbox: VSL, ramp metering, hard-shoulder running, dynamic lane use | control layer; see the [visual grammar](#2-the-visual-grammar-enriched) |
| "slowing cars before the jam" | **VSL — variable speed limits / speed harmonization** | posted-speed control upstream to smooth the flow and soften the shockwave | **[MODELED]** as an upstream `free_speed`/`capacity_factor` scenario |
| "the on-ramp light" | **ramp metering** (fixed-rate / demand-responsive / ALINEA) | metering the on-ramp inflow to protect mainline merge capacity | **[MODELED]** as a metered inflow at the ramp link |
| "the highway signs" | **DMS / VMS** (dynamic/variable message sign) + **HAR** (highway advisory radio) | operator-facing traveler information and diversion messaging | annotation layer; message text is an operator input |
| "opening the shoulder" | **hard-shoulder running** (temporary use of the shoulder as a running lane) | a capacity-adding ATM response | **[MODELED]** as a temporary `lanes+1` / `capacity` bump |
| "bad-weather traffic plan" | **WRTM — weather-responsive traffic management** | speed/advisory/metering strategy triggered by weather-driven capacity loss | **[MODELED]**; weather record itself **[NOT IN DATA]** in the sample |
| "how bad is it" (generic) | **MOEs — measures of effectiveness** | the agreed KPIs a decision is judged on (see below) | **[DERIVED]** from measured/modeled fields |
| "travel time is worse" | **TTI** (Travel Time Index = actual ÷ free-flow travel time), **PTI** (95th-pctile / free-flow = reliability), **buffer index** (extra time to be on-time 95%) | congestion *and* reliability, not just a single number | **[DERIVED]** from `travel_time`/`TT_*` vs `free_speed` |
| "cars per hour" | **person-throughput** (people, not vehicles, moved past a point) | the outcome that actually matters for ICM/transit priority | **[MEASURED]** `person_volume` in West Jordan; else vehicle-only |

Two honesty guardrails on the whole table: (1) the shipped I-95 sample has **no incident and no weather
table** — those enter only as `control_event.csv` *scenarios* or from an external PeMS/RITIS feed, and must
be labeled as such; (2) "clearance" in the model is a `capacity_factor` returning to 1.0, **not** a
responder-timestamped clearance — keep the two clocks distinct in narration.

---

## 2. The visual grammar, enriched

The original table maps *field → static representation*. This extends it with **animation semantics**: what
**moves**, what **changes color**, what **grows/shrinks** across the time slider, and the one-line **operator
read** for each cue. Base scene (OpenCities buildings/terrain/road surface) stays static; everything below is
an overlay ~2–5 m above the road surface (offset avoids z-fighting).

| Layer / cue | Driving field(s) | Static encoding (today) | Animation semantics (what changes per bin) | Operator read |
|---|---|---|---|---|
| **Link volume ribbon** | `volume` / `inflow_veh` | extrusion **height** | height rises/falls per bin | taller = more vehicles loaded on the link |
| **Speed color** | `speed` / `speed_ratio`; TMC `speed` | green free-flow → red slow | color **shifts** green→amber→red as the bin's speed drops | red = at/under the FD knee; congestion present |
| **Shockwave front** | ordered-link `speed` across bins | (n/a) | a **red band that migrates upstream** frame-to-frame — the moving state boundary | the *slope* of its migration is the wave speed; steeper-upstream = fast-growing jam |
| **Queue spillback ribbon** | `queue` / `queue_exb` | red segment from the stop line | **grows upstream** (lengthens) each bin as `queue_exb` rises; **retreats** downstream on recovery | ribbon reaching the upstream node = **spillover imminent** |
| **Bottleneck-activation marker** | first bin with `VOC≥1` / speed break | (n/a) | a pin **drops** at the activation link at the onset bin | the fixed point congestion organizes around — usually a taper/gore/merge |
| **Incident marker + influence zone** | `control_event` (`location_id`, `start/end`, `capacity_factor`) | pin | pin appears at `start_time`; a translucent **influence disk expands** upstream with the queue; fades at `end_time` | disk radius ≈ physical queue reach = the exposure footprint |
| **Secondary-crash risk halo** | queue length × upstream speed differential (DERIVED) | (n/a) | an **amber→red halo pulses** at the *tail* of the queue while the differential is high | high-pulse tail = rear-end exposure; target of upstream warning |
| **VSL gantry state** | scenario posted speed (MODELED) | gantry glyph | gantry **step-changes** its number/color (e.g. 65→55→45) per bin as harmonization engages | stepping-down gantries upstream of the tail = speed harmonization active |
| **Ramp-meter rate** | metered ramp inflow (MODELED) | signal glyph at ramp | meter glyph **cycles faster/slower**; a small held-back queue grows on the ramp | slower meter + short ramp queue = mainline merge being protected |
| **DMS / VMS panel** | operator message + diversion state | sign glyph | text **swaps** ("INCIDENT 2 MI — DELAYS", "USE RT-3000") when the message posts | reads the traveler-facing action and its timing |
| **Trajectory agents** | `waypoints` (`t_unix, lat/lon, speed_mph`), `trips` | moving dots | dots **move along paths**, **slow and bunch** entering the queue, thin out on diversion | visible platoon compression = the queue as a driver experiences it |
| **OD arcs** | `od.csv` volume | 3D arc between zones | arcs **pulse / thicken** with demand; a diversion arc **re-routes** to the alternate | thickening origin arcs into the corridor = demand pressure feeding the bottleneck |
| **Binding-capacity link** | optimization: active capacity constraint | thick red link | link **thickens to max + locks red** when its constraint binds | this link is the corridor's limiting throughput |
| **Constraint-violation marker** | optimization: infeasibility | red warning marker | marker **flashes** on the bin/link where a constraint is violated | control target infeasible as posed — relax or re-time |
| **Shadow-price heatmap** | optimization: dual price | "pressure" heatmap | heatmap **intensifies** where the dual is largest | highest pressure = where added capacity/metering buys the most |
| **Before/after KPI card** | objective / MOEs | KPI card | two-state card **flips** baseline ↔ response (TTI, veh-hr delay, queue length, throughput) | the number that proves the control worked |

**Reading the shockwave (the one cue people get wrong).** It is *not* the cars moving backward; it is the
**boundary between two flow states** moving. On the slider, watch which *link in the ordered chain* first
turns red, then which turns red next: if red propagates to progressively-upstream links, that is the
**stopping wave**; when the trailing edge turns green in the same upstream order, that is the **recovery
wave**. The gap between them at any point is the delay each vehicle absorbs.

---

## 3. Event-driven storyline / playbook

One corridor, one incident, narrated on the TMC clock. Source: an I-95 (Fredericksburg/Stafford VA) AM-peak
**[MEASURED]** speed/volume backdrop with a lane-blocking incident injected as a `control_event`
(`capacity_factor` drop) **[MODELED]** — because the sample ships no incident table, the crash itself is a
labeled scenario, while the surrounding congestion is real corridor data. This is the "see, then believe"
contract: real background, clearly-flagged injected event.

Per scene: **(a)** operations phase · **(b)** what the 3D scene shows · **(c)** driving data field ·
**(d)** operator/ICM decision · **(e)** confirming MOE.

### Scene 0 — `t+0` · AM-peak baseline (normal operations)
- **(a) Phase:** pre-incident, recurring AM peak.
- **(b) Scene:** ribbons mostly green→amber, moderate height; heights taller at the RT-3000 merge; trajectory
  agents flow steadily; OD arcs pulse at typical AM demand. No incident pin, no queue ribbon.
- **(c) Data:** `tmc_speed_15min` / `sensor_15min` at the pre-onset bins; `od.csv` baseline. **[MEASURED]**
- **(d) Decision:** monitor only; confirm detectors/TMC feeds healthy; note the merge as a known recurring
  bottleneck to watch.
- **(e) MOE:** **TTI ≈ 1.0–1.2** corridor-wide; speeds within normal AM band. Establishes the baseline the
  later before/after card compares against.

### Scene 1 — `t+2` · Incident onset → **bottleneck activation**
- **(a) Phase:** detection (the event begins; TMC not yet notified).
- **(b) Scene:** at the incident link a **pin drops**; that link's ribbon **flips to red** and its **speed
  color crashes**; a short red **queue stub** appears at its upstream end. One lane-equivalent of capacity is
  gone.
- **(c) Data:** `control_event` `start_time`, `capacity_factor=0.50` on `location_id`; first bin with
  `VOC≥1`. **[MODELED]** onset · **[MEASURED]** the speed drop if it coincides with a real TMC dip.
- **(d) Decision:** **verify** — pull the nearest camera/TMC confirmation before committing responders
  (verification precedes response in TIM).
- **(e) MOE:** activation-bin speed at the incident link < FD-knee speed; `VOC` crosses 1.0. Confirms a true
  breakdown, not noise.

### Scene 2 — `t+6` · **Shockwave & queue spillback growth**
- **(a) Phase:** verification complete → response dispatched; queue building.
- **(b) Scene:** the **red front migrates upstream** link-by-link (the stopping shockwave); the **queue
  spillback ribbon lengthens upstream** as `queue_exb` climbs each bin; the incident **influence disk
  expands**; agents entering the tail **slow and bunch**. **Capacity drop** shows as discharge downstream of
  the incident staying *below* the link's `capacity` even though flow wants more.
- **(c) Data:** `queue_exb` rising on consecutive upstream links; ordered-link `speed` migration;
  discharge vs `capacity`. **[MODELED/MEASURED]**
- **(d) Decision:** stage ICM response — arm **VSL** upstream, prepare **ramp metering** at the feeding ramp,
  draft the **DMS** message. Alert adjacent arterials for possible diversion.
- **(e) MOE:** upstream shockwave speed (links/bin) and queue growth rate. A steep upstream migration =
  fast-growing exposure = escalate.

### Scene 3 — `t+15` · **Secondary-crash risk window**
- **(a) Phase:** response on scene; peak exposure.
- **(b) Scene:** the **secondary-crash risk halo pulses amber→red at the queue tail**, where high-speed
  upstream traffic meets the standing queue (large speed differential). Queue tail may reach the upstream
  **gore/taper**; if it touches an off-ramp node, **spillover** onto the ramp begins.
- **(c) Data:** DERIVED = queue-tail location × (upstream `speed` − in-queue `speed`). **[DERIVED]**
- **(d) Decision:** post **DMS** "INCIDENT AHEAD — SLOW"; drop **VSL** upstream (speed harmonization) to shrink
  the differential; if warranted, open **hard-shoulder running** to add capacity; begin diversion via DMS/HAR
  and adjacent-arterial signal support (**ICM**).
- **(e) MOE:** **upstream speed differential shrinks** after VSL engages (the halo cools); queue-tail growth
  rate flattens. Lower differential = lower rear-end risk. Real secondary-crash outcomes are **[NOT IN DATA]**
  — report the *risk-exposure reduction*, not an avoided-crash count.

### Scene 4 — `t+25` · **Coordinated ATM/ICM response in effect**
- **(a) Phase:** active management; incident still present but managed.
- **(b) Scene:** **VSL gantries** upstream show stepped-down speeds; the **ramp meter** cycles slower with a
  small held ramp queue; **DMS** shows the diversion; a **diversion OD arc** re-routes demand to the alternate
  (RT-3000); trajectory agents visibly **peel off** at the diversion point; the mainline queue ribbon **stops
  lengthening**.
- **(c) Data:** MODELED VSL/meter scenario + re-assigned `od.csv`/`trips`. **[MODELED]**
- **(d) Decision:** hold the coordinated plan; balance mainline vs arterial so diversion does not simply move
  the bottleneck (watch the arterial's own queues).
- **(e) MOE:** mainline **queue length peaks and holds** (growth ≈ 0); person-throughput past the bottleneck
  recovers toward capacity-drop-limited discharge; arterial does not exceed its own `VOC=1`.

### Scene 5 — `t+40` · **Roadway clearance**
- **(a) Phase:** lanes reopened (roadway clearance) — distinct from full incident clearance.
- **(b) Scene:** incident pin **dims**; the influence disk **stops expanding**; the incident link's speed
  color begins **green-shifting**; the **recovery shockwave** appears — the queue ribbon starts **retreating
  downstream** (trailing edge turns green in upstream-to-downstream order).
- **(c) Data:** `control_event` `end_time` / `capacity_factor→1.0`; queue ribbon shrinking; discharge rising
  back toward `capacity`. **[MODELED]**
- **(d) Decision:** begin **unwinding** ATM — raise VSL back up in steps, ease ramp metering, update DMS to
  "INCIDENT CLEARED." Unwind gradually so you don't re-trigger breakdown.
- **(e) MOE:** discharge rate returns to `capacity` (capacity-drop recovers); queue length monotonically
  falling. **Roadway clearance time** logged here; **incident clearance time** (all responders gone) is later.

### Scene 6 — `t+60+` · **Recovery / return to normal**
- **(a) Phase:** recovery.
- **(b) Scene:** the **recovery wave** sweeps the last red back to the incident location and clears it; queue
  ribbon **gone**; ribbons return to the Scene-0 green/amber pattern; agents flow freely; diversion arc
  fades as demand returns to the mainline.
- **(c) Data:** speeds back within normal AM band across bins; `queue_exb → 0`. **[MEASURED/MODELED]**
- **(d) Decision:** stand down ATM; log timeline; compute the after-action MOE card.
- **(e) MOE:** **before/after KPI card** — Δ vehicle-hours of delay, peak queue length, corridor TTI/PTI,
  person-throughput, and **time-to-return-to-normal** (onset bin → first all-green bin). This is the number
  the response is judged on.

### Parallel WEATHER mini-storyline (WRTM)
- **`w+0` Rain onset.** Scene tints the corridor with a rain overlay; **no incident pin** — this is a
  *distributed* capacity loss, not a point event. Driving trigger is a weather condition; in the shipped
  sample this is **[NOT IN DATA]**, so it enters as a labeled WRTM scenario or an external PeMS/RITIS weather
  feed.
- **`w+10` Capacity drop.** Speeds sag corridor-wide (not at one link); ribbons amber broadly; `VOC` creeps
  up everywhere at once. **[MODELED]** via a corridor-wide `capacity_factor≈0.8–0.9`.
- **`w+15` Speed harmonization.** **VSL** steps every gantry down together (harmonization, not a localized
  shockwave fix); **DMS** posts "WET — REDUCED SPEED." **MOE:** speed *variance* across links drops (smoother,
  safer flow) even though mean speed is lower; fewer flow-breakdown bins than an unmanaged wet peak.
- Key distinction to narrate: an **incident** is a *point* capacity drop that spawns a *localized upstream
  shockwave*; **weather** is a *distributed* capacity drop managed with *corridor-wide harmonization*. Same
  MOE family, different spatial signature.

---

## 4. Playbook table for reuse

Compact, reusable TMC lookup: event → trigger data → 3D cues → recommended control → success MOE. Honesty
flags mark what the shipped data supports vs what needs an external feed.

| Event type | Trigger data | 3D cues to watch | Recommended control response | Success MOE |
|---|---|---|---|---|
| **Incident / crash** | `control_event type=incident, capacity_factor<1` **[MODELED]**; real CHP/RITIS feed **[NOT IN DATA]** | incident pin + expanding influence disk; red speed at link; upstream stopping shockwave; queue spillback ribbon; secondary-crash halo at tail | TIM lifecycle; **DMS** warning + diversion; **VSL** speed harmonization upstream; **ramp metering** to protect merge; hard-shoulder running if capacity-critical; **ICM** arterial support | Δ veh-hr delay; peak queue length; **roadway clearance time**; secondary-crash *risk-exposure* reduction; time-to-return-to-normal |
| **Weather (rain / fog / snow)** | weather condition + corridor-wide speed sag **[MODELED / NOT IN DATA]** | *distributed* amber shift (no single pin); broad `VOC` creep; smaller safe speeds | **WRTM**: corridor-wide **VSL / speed harmonization**; advisory **DMS/HAR**; pre-emptive ramp metering; reduced-speed enforcement | speed-*variance* reduction across links; fewer breakdown bins; maintained throughput at the lower safe speed |
| **Recurring bottleneck** | fixed link with daily `VOC≥1` at a taper/gore/merge **[MEASURED]** | same red link/queue activates at the *same clock time daily*; bottleneck-activation pin recurs | **ramp metering (ALINEA/demand-responsive)**; managed lanes; geometric/taper fix (planning); pre-timed **VSL** | earlier onset avoided / delayed; lower peak queue; higher bottleneck discharge (mitigated capacity drop) |
| **Special-event surge** | scheduled demand spike in `od.csv` / arcs **[MODELED]** | OD arcs thicken from event zones; volume-height spikes on access links; queues at egress | proactive **ICM** signal-timing plans; **DMS** wayfinding; transit priority (**person-throughput** focus); ramp metering on surge corridors | person-throughput sustained; egress queue cleared within target; corridor TTI within event-plan threshold |
| **Work zone** | lane-closure `control_event` (`lanes−1` / `capacity_factor`) **[MODELED]** | persistent taper at the closure; steady queue ribbon during work hours; recurring merge turbulence at the taper | **DMS** lane-merge guidance; **VSL** through the zone; off-peak scheduling; **ICM** diversion for long closures | queue held below threshold length; merge-speed differential kept low (rear-end safety); delay within the work-zone MOT plan |

---

## 5. Data-to-animation mapping

Exactly which columns feed each animated element. **Minimum viable** = renders the frame honestly with what
ships today; **Better / advanced** = richer cues when the extra schema is present.

### Time slider (per-bin link state)
- **Key:** `link_id` × `time_bin_start` (or TMC `time`) → one frame per bin.
- **Minimum viable** (ships today): `time_bin_start`, `inflow_veh` (→ height), `queue_exb` /
  `exb_queue_at_bin_start` (→ spillback ribbon length); for real corridors `tmc_speed_15min.time, speed`
  (→ color) and `sensor_15min.speed, volume, occupancy`.
- **Better / advanced:** full `link_performance` per bin with `speed, density, VOC, delay, capacity` →
  color from `speed`, tube thickness from `density`, shockwave from the ordered-link speed field,
  capacity-drop from discharge vs `capacity`.

### Events (incident / weather layer)
- **Minimum viable** (ships today): `control_event.csv` = `type`, `location_type`, `location_id`,
  `start_time`, `end_time`, `parameter=capacity_factor`, `value`, `priority` → incident pin at `location_id`,
  appears/fades on the `start/end` clock, disk radius scaled by the modeled queue.
- **Better / advanced (external feed, must be labeled [NOT IN DATA] until connected):** an incident/weather
  record with `lanes_affected` / `lanes_blocked`, `severity`, `event_type` (crash/debris/disabled),
  `weather_condition` (rain/fog/snow), verified `detection/response/clearance` timestamps → true lane-count
  visuals, WRTM triggers, and a real TIM-phase clock instead of a modeled one. This is where a **PeMS
  incident+weather** or **RITIS** feed plugs in.

### Trajectories (agent layer)
- **Minimum viable** (ships today): `waypoints.csv` = `journey_id`, `t_unix`, `latitude`, `longitude`,
  `speed_mph`, `heading` → agents move along real GPS, slow/bunch by `speed_mph`. `trips.csv`
  (`link_ids`, `t_start`, `t_end`) → link-path animation.
- **Better / advanced:** per-agent `agent_trajectory.csv` with mode/vehicle-type and dense timestamps →
  mode-colored agents (car/bus), platoon compression, transit person-throughput.

### OD arcs
- **Minimum viable** (ships today): `od.csv` = `o_zone`, `d_zone`, `volume`, `o_lon/lat`, `d_lon/lat` →
  arcs pulsing/thickening by `volume`; a diversion scenario re-routes an arc.
- **Better / advanced:** time-sliced OD (per-bin demand) → arcs that pulse with the actual demand profile
  feeding the bottleneck.

### Optimization decision layer
- **Minimum viable:** `objective_trace.csv` (before/after objective) → KPI card.
- **Better / advanced:** `constraint_status.csv` (binding/violated, dual price) → thick-red binding link,
  flashing violation marker, shadow-price pressure heatmap.

**Minimum viable schema (one line to remember):** `node.csv` + `link.csv` + `link_performance*` (per bin) +
`control_event.csv` gives you the full incident storyline honestly. Add `waypoints/trips`, `od.csv`, then an
external incident/weather feed, then optimization traces, to climb the ladder.

---

## 6. Fidelity ladder

*"We need to see and then believe."* Each rung says what is honest to show — and, critically, **what NOT to
fake** at that rung. Never render a layer whose data you don't have; label every modeled/scenario element.

**Rung 0 — Static assignment only** (`07_west_jordan/link_performance.csv`)
- **Honest:** one snapshot — volume-height, speed-color, `VOC` tint, static `queue`, congestion-duration.
  Recurring-bottleneck *identification*.
- **Do NOT fake:** any motion. No shockwave, no growing queue, no time slider — there is only one time
  period. Don't animate a single snapshot into a fake "playback."

**Rung 1 — Time-dependent link_performance** (`*_15min.csv`, I-95 `tmc_speed_15min`)
- **Honest:** the time slider; real per-bin color/height; **shockwave** as the migrating low-speed front;
  **queue spillback** as `queue_exb` growing upstream; onset/recovery waves.
- **Do NOT fake:** a *cause*. Without an event table you may show *that* a queue formed, not *why*. Don't
  drop an incident pin or a weather tint on Rung-1 data — that's inventing the trigger.

**Rung 2 — + incident / weather events** (`control_event.csv` [MODELED], or external PeMS/RITIS [MEASURED])
- **Honest:** incident pin + expanding influence disk tied to `start/end`; the queue *attributed* to a
  modeled `capacity_factor`; WRTM corridor-wide sag; the TIM-phase clock.
- **Do NOT fake:** responder timestamps or lane counts you don't have. A *modeled* `capacity_factor` is not
  a *verified* clearance time — label it. Don't claim a **secondary crash occurred**; only show
  risk-*exposure*. Don't paint weather you didn't observe.

**Rung 3 — + trajectories** (`waypoints.csv`, `trips.csv`)
- **Honest:** real probe agents moving on real GPS; platoon compression at the queue tail; observed diversion.
- **Do NOT fake:** density of agents. Waypoints are downsampled (~1/180) probes — show them as *sampled
  probes*, not "every vehicle." Don't synthesize cars to fill gaps and imply full penetration.

**Rung 4 — + optimization** (`objective_trace.csv`, `constraint_status.csv`)
- **Honest:** binding-capacity link, constraint-violation marker, shadow-price pressure heatmap, before/after
  KPI card — each tied to a solver output.
- **Do NOT fake:** a "recommended" control the model didn't actually evaluate. Every decision-layer cue must
  trace to a solved scenario. Don't show a shadow price without a dual; don't show a before/after without an
  actual re-run.

**The one rule that spans the ladder:** the base city scene is *context* (static geometry); every dynamic
cue must resolve to a real column at its rung. If it doesn't, it doesn't render — the operator has to be
able to trust that red means measured-or-modeled congestion, never decoration.

# Part 1 — Speaker Notes & Running Order

**Talk:** *AI + Open-Source Engines for Transportation Planning Workflows*
**Speaker:** Xuesong (Simon) Zhou, ASU
**Slot:** 20 minutes (Part 1 of a 45-minute joint talk with Taehooie Kim, MAG)

---

## Running order

The deck contains 24 slides. **20 are in the live 20-minute path**; 4 move to appendix or shift to Taehooie's lead-in.

| Time      | Slide | Title                                              | Section                |
| --------- | ----- | -------------------------------------------------- | ---------------------- |
| 0:00–0:30 | 1     | Title                                              | Open                   |
| 0:30–1:15 | 2     | What does a planner actually need?                 | Problem (1/3)          |
| 1:15–2:15 | 3     | Today's workflow is fragmented                     | Problem (2/3)          |
| 2:15–3:05 | 4     | Why analytics remain fragmented                    | Problem (3/3)          |
| 3:05–4:15 | 5     | AI is a workflow accelerator, not magic            | Opportunity            |
| 4:15–5:30 | 7     | GMNS — the open data grammar                       | Standard (1/2)         |
| 5:30–6:20 | 8     | GMNS as a transportation systems language          | Standard (2/2)         |
| 6:20–7:30 | 9     | The open-source engine stack                       | Stack                  |
| 7:30–8:20 | 10    | From raw data to decision dashboard                | Workflow (1/2)         |
| 8:20–9:10 | 11    | Multi-resolution modeling — planner translation    | Workflow (2/2)         |
| 9:10–10:00| 12    | Concrete workflow: Tempe corridor                  | Example intro          |
|10:00–10:40| 13    | Operationalizing GMNS through dashboards           | Dashboards intro       |
|10:40–11:40| 14    | Tempe Signal Timing Explorer (Stage 1)             | Dashboard 1            |
|11:40–12:40| 15    | ASU Intersection Movements — CV (Stage 2)          | Dashboard 2            |
|12:40–13:40| 16    | Tempe Integrated — Transit × Signals (Stage 3)     | Dashboard 3            |
|13:40–14:50| 17    | Apache Blvd 3-int simulation (Stage 4)             | Dashboard 4            |
|14:50–16:20| 18    | How the 4 dashboards map onto the FTT pipeline     | Tie-in                 |
|16:20–17:20| 19    | ODME — closing the loop with observations          | Calibration math       |
|17:20–18:20| 20    | ODME demo — assignment → calibrated OD             | Calibration tool       |
|18:20–19:20| 24    | From workflow to computational graph (hand-off)    | Bridge to Taehooie     |

**Total live: 19:20 + 40 s buffer = 20:00.**

### Slides moved out of the live path

| Slide | Title                                | Where it goes                                                                                                                                                                                |
| ----- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6     | Where does ML fit in transportation? | **Appendix.** Use only if a question forces the deep-learning / RL backstory. The doc explicitly recommends compressing ML/DL history.                                                       |
| 21    | FTT + Traffic Data Hub workflow      | **Hand to Taehooie** as his lead-in slide. It's already half-FTT — better said by him.                                                                                                       |
| 22    | Why this matters for MPOs and DOTs   | **Appendix / Q&A.** Strong consulting message but burns a minute on a point planners already feel. Keep ready in case a council-member-style question comes up.                              |
| 23    | GMNS community, GitHub, learning     | **Joint closing slide** (after Taehooie). Better as the "what's next" slide of the *whole* talk than as a Simon slide.                                                                       |

---

## Section arc

**0–5 min · The problem (slides 1–5).** Open at the planner's pain point. The workflow is fragmented across silos. AI accelerates the glue, but needs structured data.

**5–10 min · The standard and the stack (slides 7–11).** GMNS is the grammar. OSM2GMNS, Path4GMNS, DTALite, dashboards are the executable workflow. Multi-resolution is the planner translation.

**10–15 min · Dashboards in action (slides 12–17).** Live or recorded demos of four progressively richer dashboards. Each one is a window into one tensor of the same graph.

**15–19 min · Closing the loop (slides 18–20).** Tie the dashboards to the FTT pipeline. Show ODME as the backward pass. Demo it on a toy network.

**19–20 min · Hand-off (slide 24).** Six tensors already on the table. Taehooie's job: name them and unify them.

---

## Speaker notes — slide by slide

> *Style: short declarative sentences, physical content in every clause. No padding. Built to be read aloud.*

---

### Slide 1 — Title

**Key message:** This is Part 1 of a two-part talk. Planner-facing first, theory second.

> Good morning. I'm Simon Zhou from Arizona State. This is a joint talk in two halves. I take the first twenty minutes; Taehooie Kim from MAG takes the next twenty. My job is the planner's view — where the workflow breaks today, and how AI and open-source engines fix it. Taehooie's job is the architecture underneath: the Flow-Through-Tensor framework that unifies what I'm about to show you. By the end of Part 1 you should see a clear arc from your daily dashboards, through GMNS and DTALite, to the calibration loop that hands off to FTT.

---

### Slide 2 — What does a planner actually need?

**Key message:** Start at the planner's question, not the equations.

> I want to start where you live, not where the equations live. A planner already has the raw material — networks, counts, OD tables, GIS layers, subarea questions. You don't need more data; you need the data to *connect*. The four needs on the right — network, OD, performance, scenarios — are what every defensible answer is built from. The quote on the left is what I hear from Tempe and ADOT staff almost verbatim: how do I get from raw data to a defensible answer my agency can act on, without writing glue code for three weeks. That's the question this talk answers.

---

### Slide 3 — Today's workflow is fragmented

**Key message:** Six-step pipeline, four pain points at every handoff.

> Look at the six-step pipeline at the top: GIS, network coding, paths, assignment, ODME, dashboard. Every box is a different tool. Often a different person. Almost always a different file format. The four red boxes at the bottom name the cost. Format conversions cost time. Manual glue code costs time and breaks on staff turnover. Buried assumptions cost trust. And without an end-to-end story, it's hard to explain to a council member how counts shaped the answer. This isn't a critique of any agency. It's the state of the practice. Now let's look at why it stays this way.

---

### Slide 4 — Why analytics remain fragmented

**Key message:** Six modeling silos. Each excellent. None speaks the same network.

> Same problem, different lens. Most agencies maintain six separate modeling environments: travel demand model, signal timing, transit GTFS, GIS layers, operations dashboards, simulation models. Each is excellent at what it does. None of them speaks the same network definition. When you ask a question that crosses two of them — say, how signal coordination affects bus on-time performance — you start a small consulting project just to reconcile the network. GMNS fixes that by giving us one shared definition. From six silos to one digital foundation.

---

### Slide 5 — AI is a workflow accelerator, not magic

**Key message:** AI compresses the glue work. Structured data makes that possible.

> One slide on AI, because it's what funded a lot of these conversations. Generative AI — Claude, Copilot, Codex — is great at the work *between* the boxes. Cleaning data, writing glue code, summarizing dashboards. That's the green column on the left. The amber column is what AI does not replace. It doesn't know which counts to trust. It doesn't know flow and density physics. It doesn't defend a plan in front of a council. Those are still our jobs. The line at the bottom is the takeaway: AI compresses the glue. Structured transportation data — GMNS, paths, OD, counts — makes that compression possible. AI without GMNS is a wood chipper without wood.

---

### Slide 6 — Where does ML fit? *(appendix — skip in live)*

**Key message:** Three families of ML, three planning use-cases each. Reserve for Q&A.

> Quick orientation. Three families of ML, three places they show up. Supervised: trip generation, mode choice, travel-time prediction. Unsupervised: corridor typology, OD clusters, anomaly detection in counts. Reinforcement: adaptive signal control, dynamic routing. The bridge at the bottom is the only thing to remember: AlphaGo and ChatGPT both run on computational graphs. FTT borrows that idea.

---

### Slide 7 — GMNS — the open data grammar

**Key message:** Six objects. Plain CSV. Real, open, in use today.

> This is the slide that earns the rest of the talk. GMNS is six objects — node, link, signal, zone, path, demand. That's it. A common, human-readable, machine-readable format. The code on the right is real — that's actual node.csv and link.csv. Anyone in this room could open it in Excel. The point is not the format. The point is the *grammar*. Once your network speaks GMNS, every tool that also speaks GMNS plugs in. No converters. No silent format losses. No staff member who is the only one who knows where the lane field went. Volpe Center built it; the Zephyr Foundation oversees it; the group has MPO, city, industry, and US DOT participation.

---

### Slide 8 — GMNS as a transportation systems language

**Key message:** One schema, eight applications, zero reformatting.

> Same idea, integration view. GMNS in the middle. Eight applications around it: geometry, traffic control, lanes and turns, demand, transit, simulation, assignment, dashboards. One schema, eight applications, zero reformatting between them. Remember this slide when you hear "data standard." A data standard sounds like a compliance burden. GMNS is the opposite — it's the thing that lets you stop writing converter scripts.

---

### Slide 9 — The open-source engine stack

**Key message:** Four tools, one grammar. Hours, not weeks.

> Four tools. One grammar. OSM2GMNS turns an OpenStreetMap tile into a GMNS network — that's the build step. Path4GMNS computes paths and initial assignment — the route step. DTALite runs dynamic traffic assignment and simulation — the assign step. And the dashboard layer interprets — counts, OD, performance, bottlenecks. The blue bar at the bottom is the shared bus: GMNS files moving between tools. No tool has its own private format. A planner can go from an OSM tile to a performance dashboard in hours, not weeks. And every artifact between is auditable.

---

### Slide 10 — From raw data to decision dashboard

**Key message:** The full pipeline on one slide. Reproducible, auditable.

> The whole pipeline on one slide. Five raw inputs at the top: OSM, signal timing, GTFS, counts, TMC speeds — real things you have on your hard drive today. They flow into the GMNS Data Hub, the integration layer. The hub feeds three analytics layers: assignment, simulation, accessibility. Out the bottom: interactive dashboard, scenario evaluation, planning decisions. The point is reproducibility. Every step is GMNS-native. Every artifact is auditable. If a council member asks how the answer was made, the answer fits on this slide.

---

### Slide 11 — Multi-resolution modeling — planner translation

**Key message:** Same network, four lenses. Match each to a planning question.

> A word on resolution before we look at concrete dashboards. The banner at the top is Net2Cell, our converter — from a regional view down to a cell-based microscopic representation, same underlying GMNS data. The table is the translation planners want. Macroscopic is regional planning. Mesoscopic is corridor analysis. Microscopic is intersection operations. Dynamic assignment is congestion propagation in time. GTFS integration is multimodal accessibility. The right column is what planners actually care about — the executive dashboard view. The technical layer is the means. The dashboard is the end.

---

### Slide 12 — Concrete workflow: Tempe corridor

**Key message:** Four steps from OSM tile to dashboard, on a real corridor.

> One concrete example before we open the dashboards. Apache Boulevard in Tempe. Four steps. Build the network from OSM. Pull signal data from the ADOT TMC. Run assignment with Path4GMNS and DTALite. Interpret in our Tempe Signal Timing Explorer dashboard. On the right is the dashboard — KPIs at the top, delay-by-intersection bars, a performance table by signal. This is what comes out the other end. Now let me show you four dashboards that together form a teaching sequence.

---

### Slide 13 — Operationalizing GMNS through dashboards

**Key message:** Dashboards are visualization layers over GMNS intelligence, not standalone apps.

> Quick framing before the live dashboards. Dashboards are not standalone web apps. They are visualization layers over GMNS-based network intelligence. The stack on the left makes that concrete: raw data, GMNS hub, analytics engine, query layer, dashboard UI. Four of those five layers are GMNS-native. On the right, two of the dashboards we're about to open. Same network underneath. Different lenses on top.

---

### Slide 14 — Tempe Signal Timing Explorer (Stage 1)

**Key message:** Regional inventory. 206 signals. The map before any model.

> This is the regional inventory dashboard. 206 signalized intersections in Tempe. 16 corridors. 2,353 phase images. All loaded from ADOT TMC and ATSPM data. The four-step workflow on the right is the user journey: pick a corridor, click an intersection, read the timing plan, compare along the corridor. Why it matters: before anyone runs any model, this is where you discover that signal X has a 60-second cycle and signal Y next door has 120 — and progression is impossible. GMNS layer: signal nodes plus TMC controller timing plus ATSPM phase images.

---

### Slide 15 — ASU Intersection Movements — CV (Stage 2)

**Key message:** Intersection-level diagnostics. CV journeys map to NEMA movements.

> Intersection-level diagnostic. 102 intersections, 20,374 connected-vehicle journeys, 682 turning movements. Each intersection is a card with a NEMA 12-movement grid. Journeys per movement. Delay per turn. Click an intersection and the right panel updates the timing plan from ATSPM next to the observed movements. Why it matters: this is where you find a protected-left-turn candidate. High left-turn volume plus long delay equals an upgrade case backed by data, not by guess. GMNS layer: CV BSM journey data plus GMNS movement objects plus Tempe ATSPM.

---

### Slide 16 — Tempe Integrated — Transit × Signals (Stage 3)

**Key message:** Multimodal canvas. Transit, signals, GTFS, one basemap.

> The multimodal canvas. 206 signals, 117 transit routes, 8,029 stops. All on one GMNS basemap. Toggle layers: signals, rail, bus, circulators, express, all stops. Drill into any route or stop with the right-panel tabs. Why it matters: this is where transit-signal-priority candidates emerge naturally. A high-frequency bus crossing three multi-phase signals with poor offsets — that's a TSP target you can quantify, not just nominate. GMNS plus Valley Metro GTFS plus ATSPM, fused at the link level.

---

### Slide 17 — Apache Blvd 3-int simulation (Stage 4)

**Key message:** Dynamic simulation with physics-informed checks. Forward pass made visible.

> The dynamic simulation dashboard. Three intersections on Apache Boulevard. Fixed versus actuated control. Coordination on or off. Demand low to extreme. Press play and vehicles propagate through three intersections with realistic car-following and signal logic. The SCI panel on the right — the Stochastic-Consistency Index — runs seven physics-informed checks in real time. Gap-out, max-out, queue conservation, fundamental diagram, Webster delay. Why it matters: this is the forward pass of the FTT pipeline made visible. We'll see that explicitly on the next slide. GMNS plus DTALite physics plus UTDF turn ratios plus signal plans.

---

### Slide 18 — How the 4 dashboards map onto the FTT pipeline

**Key message:** Each dashboard is a window into one tensor of the same graph. This is the slide that earns the hand-off.

> This slide is the bridge to Taehooie's part. Take a moment with it. On the left is the FTT computational graph: demand T, OD-to-path matrix B, path flow f, path-to-link matrix A, link flow v, and link performance c(v). That's the forward pass. On the right, the four dashboards we just saw. Each one is a window into one slot of this graph. Tempe Explorer defines c(v) — the signal control parameters in the performance function. ASU intersection CV gives us f and v and the observed counts y-hat — the data we calibrate against. Tempe Integrated extends T to a multi-mode tensor. Apache simulation runs the whole forward pass dynamically. The bottom strap is the backward pass: minimize the count residual, calibrate T. That's ODME. That's the next two slides.

---

### Slide 19 — ODME — closing the loop with observations

**Key message:** Standard ODME math. Already produces A and B — the FTT matrices.

> The math. Don't be scared. Three inputs on the left: an initial OD T-zero, the path-link matrix A from assignment, and observed link counts y-hat. The ODME box minimizes the count residual plus a soft regularizer that keeps the OD close to the prior. Standard, well-posed. Out the right side: a calibrated OD T-star that fits the counts within tolerance. The key insight at the bottom is what matters here: this loop *already* produces the A matrix and the B matrix. FTT will name them and chain them. We're already most of the way there.

---

### Slide 20 — ODME demo — assignment → calibrated OD

**Key message:** Same math, live tool. Slide lambda, watch OD recalibrate.

> Same math, but as a tool you can drive. This is a screenshot of a small demo I'm shipping with the slides. Toy network. Three OD pairs. Three sensor links. On the left: the network, the assignment artifact, the prior OD, the path-link A matrix. In the middle: the FTT pipeline, the loss function, the observed counts, a lambda slider. On the right: calibrated OD updates live, link residuals shown, RMSE and drift KPIs reported. Slide lambda small — you trust the counts. Slide lambda large — you trust the prior. This is the FTT backward pass on a network you can hold in your head.

---

### Slide 21 — FTT + Traffic Data Hub *(handed to Taehooie)*

**Key message:** Architecture: Hub → FTT → calibration / verification / dashboard.

> *If Simon does cover this — 60 s.* Left: a Traffic Data Hub feeding detector counts, CV trajectories, TMC probes, transit AVL, signal logs, cameras. Center: FTT as the path-based assignment foundation, forward and backward. Right: three outputs — calibration, verification on hold-out, and dashboards with uncertainty bands. This is the architecture that scales the toy demo to a real region. Same loop, bigger tensors.

---

### Slide 22 — Why this matters for MPOs and DOTs *(appendix)*

**Key message:** Reproducible, transparent, multimodal, AI-ready infrastructure.

> *If used in Q&A — 60 s.* Eight benefits, two rows. Reproducible workflows. Less consultant duplication. Faster scenario testing. Common data standards. Multimodal coordination. Transparent decisions. Digital-twin foundation. AI-ready infrastructure. The strategic line at the bottom is the one to remember: GMNS plus FTT is a scalable transportation digital infrastructure — not just another modeling tool.

---

### Slide 23 — GMNS community, GitHub, learning sessions *(joint closing)*

**Key message:** The standard is public; sessions are monthly.

> *Best used as the joint closing slide.* Two pointers. Left: the GitHub repo — 132 stars, 17 forks, schema, docs, examples. Public, free, fork-able. Right: the Zephyr Events page — monthly Learning Sessions. GMNS Assignment Tools. Multimodal Accessibility. NetworkWrangler. Hands-on sessions for planners. You don't have to wait for the next conference.

---

### Slide 24 — From workflow to computational graph (hand-off)

**Key message:** Six tensors already on the table. Taehooie takes it from here.

> The hand-off slide. Left: what we have. Demand T, paths, link flows, the B map from OD to path, the A map from path to link, link performance c(v), and observed counts y-hat. Already six tensors on the table. Right: what FTT adds. The unified computational graph. Forward and backward. Differentiable. Demand and supply in one architecture. Scales to multi-modal, space-time. Next, Taehooie Kim is going to take exactly these objects — T, B, f, A, v, c(v), and y-hat — and show you the engine that ties them into one differentiable system. Over to Taehooie.

---

## Delivery checklist

- [ ] Run a 20-minute clock on slide 1. Keep glancing at it.
- [ ] If running long at slide 13, compress slides 14–17 to ~45 s each.
- [ ] Slide 18 is the most important slide of Part 1. Do not rush it.
- [ ] On slide 20, mention that the demo HTML is in the handout — even better, open it live for 30 s.
- [ ] Slide 24 ends with three words: "Over to Taehooie."

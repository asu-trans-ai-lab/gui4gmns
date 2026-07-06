# DLSim STE kernel (Phase 1) — space-time-event engine skeleton

Minimal single-thread C++17 implementation of the Qu & Zhou (2017) space-time-event framework,
driven **purely by the encoding files** of `../DLSim_Encoding_Spec.md` (encoding-first: no C++ edits
to define a scenario). See `../DLSIM_STE_DEVELOPMENT_PLAN.md` for the full roadmap.

## Layout
```
core/Event.h       (agent, link, tick, buffer, traffic_state, control_state) — trajectory = event list
core/Agent.h       id + path + schedule
core/Link.h        double buffer ENB/EXB, storage cap (kjam·len·lanes), fractional-carry capacity
core/Scheduler.h   the paper's five-task synchronous pipeline per tick (parallel decomposition target)
io/Reader.h        encoding reader: node/link/demand/phi-profile/control_event/run_config
tests/test_main.cpp  stage tests with hard assertions
testdata/          stage1_one_link (bottleneck), stage2_spillback (spec §10 verbatim)
```

## Build & run
```bash
bash build.sh                                     # g++ -O2 -static-libgcc -static-libstdc++
./dlsim_test.exe testdata/stage1_one_link stage1
./dlsim_test.exe testdata/stage2_spillback stage2
```

## Stage results (2026-07-02, all assertions PASS)
| stage | scenario | result |
|---|---|---|
| 1 | one-link bottleneck, incident 07:20–07:40 halves capacity | 7/7: conservation 1800/1800; discharge **700.0 veh/h** during incident, **1401 veh/h** queued; max queue 635 (theory 634); clears 08:30 (theory 08:29); no spillback |
| 2 | spec §10 verbatim (3000 veh, small storage) | 5/5: conservation 3000/3000; **spillback 359/360 storage cap**; loading blocked 64 min; clears **09:20 = hand-computed prediction** |
| 3 | merge: heavy (1500) + light (750) approaches → 1800/h bottleneck | 6/6: **proportional allocation — service ratio exactly 2.00**, merge throughput exactly 1800 veh/h, queues 302/151, clears 08:17 |
| 4 | signal, green_ratio 0.45 on saturation 1800/h, 07:10–07:50 | 5/5: discharge **810.8 ≈ 0.45×1800 veh/h** in green window, 1800 after; clears 08:08 (= prediction) |
| 5 | **Chicago Sketch** (2,950 links, 387 zones; published benchmark) @ 50% demand | 3/3: conservation **569,751/569,751**, clears 16:52; **simulate 3.7 s single-thread** (6,000 ticks); routing 93k OD in 0.3 s |
| 6 | Chicago Sketch @ **FULL demand (1.13 M agents)** with **MSA-8 path diversification** | 3/3: conservation **1,128,857/1,128,857**, clears 13:16; max queue 8,747 → **350**; 65,607/93,135 OD rows diversified; explicit `path_flow.csv` (DTALite hook) also supported |
| 7 | QVDF **capacity drop** (C=1800, f_d=1.2 → μ=1500 while queued) | 6/6: free-flow 900.0 (demand-limited, no drop), queued discharge **exactly 1500.0 = C/f_d**, queue 301 vs theory 300, clears 08:08 vs theory 08:07 |
| 8 | **OpenMP node-partition parallelism**, full-demand Chicago | **bit-identical checksum at 1/2/4/8/16 threads**; simulate 9.3 s → **4.6 s @ 4 threads (2.0×)**; per the paper, speedup grows with network size |
| 9 | **Closed ODME loop** (truth run → measurement.csv → gated/bounded recovery) | 7/7: RMSE **126.4 → 0.84**; θ(1→3)=**1.0879** (ideal 1.0909), θ(2→3)=**0.9313** (ideal 0.9231); **φ = (.1501,.3499,.3500,.1500) vs truth (.15,.35,.35,.15)**; unobservable OD frozen at θ=1; all θ within ±10% |
| 10 | **Chicago Regional** (39,018 links, 12,982 nodes, 1,790 zones, 817k agents, 21,600 ticks) | 3/3: conservation **817,231/817,231**; **identical checksum at 1/4/8/16 threads**; simulate **292 s → 62 s @4 (4.7×) → 53 s @16 (5.5×)**; MSA routing parallelized (integer milli-veh accumulation ⇒ order-invariant) |

Each small-net run writes `out_link_performance_15min.csv` and prints agent 0's event list
(trajectory-as-event-list demonstration). Every run prints a `determinism_checksum` (link-CD hash +
completion-tick sum) — the formal acceptance gate for thread-count invariance.

## Parallel design (Phase 4, implemented)
- Tasks 2/3/5 parallel over **links** (each iteration writes only its own link).
- Task 4 parallel over **nodes**: a node owns its incoming links' EXBs and outgoing links'
  ENBs/`avail_in` — race-free by construction. Merge allocations stored on the downstream link
  (single writer in Task 3, single reader-node in Task 4).
- **Race found & fixed during stage 8:** `occupancy()` in the Task-4 storage check read `exb` while
  another node's thread popped it → thread-dependent admissions. Fix: **snapshot admission**
  (`occ_snap + admitted`, taken at Task 3, same-tick pops conservatively ignored) — deterministic and
  faithful to the paper's task separation.
- No RNG in the kernel yet; when stochastic rounding lands, it uses per-object seeds (paper §3.1).

## Gridlock management layer (stage 11 — replaces the earlier blanket guard)
The first guard (timeout-based storage relaxation anywhere) was **too permissive: overload could be
silently absorbed**. Redesigned as detect → warn early → meter → logged last resort:
1. **Detection**: per-tick `blocked_by` edges (who blocks each link's FIFO head) form a functional graph —
   **deadlock = a cycle**, found in O(#blocked); plus network blocked-share tracking.
2. **Early warning**: `gridlock_events.csv` — per-link blocked warnings, network congestion warnings,
   cycle detections; `first_warning` surfaced in every summary (overload case: alert at **07:37**, 7+ hours
   before the failure end-state).
3. **Origin metering** (`gridlock_policy=meter|meter+relax`): when blocked share ≥ 3% (hysteresis off at
   1.5%), demand is **held at origins** — physically meaningful staging, visible as entry delay — instead
   of being crammed into a saturated network.
4. **Relaxation = logged last resort**: storage bypass ONLY for links in a *detected deadlock cycle*,
   counted and reported; capacity blocking never relaxes.
5. **Oversaturated flag**: peak blocked share ≥ 5%, bypasses > 0.1% of moves, or non-conservation ⇒ the
   run is flagged — **overload is managed and reported, never hidden**.

Overload benchmark (Chicago Sketch, full 1.13 M AON demand — the case that used to lose 332k silently):
| policy | result |
|---|---|
| `report_only` | 6/6: fails loudly (720k/1.13M), first warning 07:37, **1,351 cycles detected**, 0 bypasses, flagged OVERSATURATED, 2,858 events |
| `meter+relax` (default) | 5/5: **conserves 1,133,783/1,133,783**, metering 757 min, cycles 1,351→**68**, bypasses 0.31% (all logged), still flagged OVERSATURATED |

## Findings & safeguards
- **Full-demand Chicago (1.13 M agents)** completes 1.05 M: all-or-nothing shortest-path routing
  concentrates equilibrium-scale demand (max queue 8,747 on one link) beyond serviceable capacity.
  **This is the architecture lesson, not a kernel bug:** at full scale the kernel must consume DTALite's
  diversified `path_flow.csv` (encoding spec §2) — exactly Phase 3 of the plan. `demand_scale` is a
  `run_config.json` parameter.
- GMNS unit handling: `vdf_length_mi`/`vdf_free_speed_mph` preferred; meters/kmh fallback for
  real-world exports; centroid connectors (zero-length, touching a centroid) get unlimited storage.

## Production runner (Phase 5)
`dlsim_run.exe <scenario_dir> [--odme N]` — runs the engine (optionally with the closed ODME loop) and
writes the **queryable run package** into `<dir>/out/`: `link_performance.csv`, `run_summary.json`
(agents/conservation/VMT/VHT/CPU/checksum), `odme_summary.json` (RMSE history, gate counts, bounded θ,
recovered φ), `privacy_manifest.json` (default export level 2 — no raw trajectories), `run_log.md`.
This binary is the engine behind the planned DTALite switch `simulation_engine = DLSim_STE`.

| 12 | **Backward wave (F2)** — DTALite `kinemative_wave` CA/CD-lagged admission (`CA − CD(t−1−BWTT) < kjam·L·eff_lanes`), Riemann clearance test | 5/5: entry resumes **exactly 07:40 = clearance + L/w** (analytic); KW corrections propagated: stage-1 entry gating, stage-2 sub-jam discharge density, envelope slack, effective-lanes storage; stage-6 now conserves with **zero** gridlock events; **F3 first cross-model check: R²=0.993 vs TAPLite UE** (2,928 links) |

## Status vs the development plan (2026-07-02) — ALL PHASES EXERCISED
- Phase 0 encoding spec ✅ (v0.2, decisions D1–D5)
- Phase 1 kernel ✅ (stages 1–5) · Phase 2 discharge/control ✅ (QVDF drop, signal, incident/work zone)
- Phase 3 ✅ (`path_flow.csv` + MSA diversification; **closed ODME loop with observability gate,
  ±10% bound, φ(t) recovery — stage 9 recovers ground truth**)
- Phase 4 ✅ (OpenMP node partition; bit-deterministic 1–16 threads on Sketch AND Regional; 5.5× @16)
- Phase 5 ✅ first cut (`dlsim_run` JSON package + privacy manifest)

## Remaining for production hardening
- Embed as an engine option inside the actual DTALite codebase (`simulation_engine` switch in settings)
- Movement-level signals (Vol2Timing normalization), managed-lane eligibility, demand_event.csv
- ODME at agency scale (sensor sets from real measurement.csv; screenline explainability report port)
- Sub-tick timestamps in exports (spec D3); 15-min link_performance at regional scale (chunked I/O)

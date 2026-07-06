# gui4gmns roadmap (v0.2 — post-review)

Supersedes the scattered plan notes. Ordered by the review (`REVIEW_FABLE5.md`): stabilize the
workspace first, then turn the catalog spec into an engine, then grow coverage. Each phase has a
concrete done-test so "done" is not a matter of opinion.

## Phase A — stabilize (do first; addresses Sev-1)
- [x] **A1 Consolidate to one dev + one release folder.** DONE 2026-07: canonical = `gui4gmns/github_dev` (dev, superset, 5 commits) + `gui4gmns/github_release` (public, cloned from dev, remote → `asu-trans-ai-lab/gui4gmns`). Deleted the 4 redundant copies (`gui4gmns_dev`, `gui4gmns_release_github`, old `gui4gmns/github_release`, locked `guiagent4gmns`).
  *Done-test met:* two repo folders (`gui4gmns/github_dev`, `gui4gmns/github_release`); remote set only on release. See `../../WORKSPACE.md`.
- [x] **A2 Move raw sources out of the repo.** Relocate `datasets/08_public_ITS_VA_1-95/` (2.3 GB) to a sibling `_raw_sources/` outside any git tree; adapters take an explicit source path.
  *Done-test:* repo working tree < 250 MB; `git ls-files | xargs du` unchanged; adapters still regenerate the sample.
- [ ] **A3 One generator, synced by build not by hand.** The release folder's generator is produced from dev by a script/CI, never `cp` by hand.
  *Done-test:* `make release` (or a 5-line script) rebuilds the release tree; no manual copy step.

## Phase B — trust (Sev-2)
- [ ] **B1 Tests + CI.** `tests/` golden checks (Chicago Sketch conserved 1,128,857; ITS sample = 6 layers with row counts; every sample dataset generates and its embedded JSON parses). GitHub Actions on push.
  *Done-test:* `pytest` green; CI badge on the release README.
- [ ] **B2 Catalog engine — `catalog_run.py`.** `catalog_run.py <query>` → match manifest (category/facets) → run the manifest's QA gates → bind adapter → emit dashboard. This is the "Dataset Librarian".
  *Done-test:* `catalog_run.py "corridor simulation apache"` produces the Apache dashboard after QA passes; a bad dataset is refused with the failing gate named.
- [ ] **B3 QA validators — `qa/`.** `validate_gmns.py`, `validate_trajectory.py`, `validate_corridor.py`, `validate_odme.py`, each returning pass/fail keyed to `qa_contract` names (topology, units, timestamps, `q=k·v`). Reuse the 7 SCI checks as the shared library.
  *Done-test:* each `qa_contract` string in the catalog resolves to a validator; the ITS sample passes its 6 gates; a corrupted copy fails the right one.
- [ ] **B4 Stronger privacy gate.** Add content heuristic (private column names / TMC-ID regex) + size gate (> 5 MB tracked file warns) to `validate_no_private_data.py`.
  *Done-test:* a renamed private file (no `nvta` in the name) is still caught.

## Phase C — maintainability (Sev-3)
- [ ] **C1 De-monolith the generator.** `src/gui4gmns/core.py` + `template.html` (package data) + `adapters/`. Wheel bundles the template.
  *Done-test:* editing the dashboard means editing `template.html`, not a Python string; wheel still self-contained.
- [ ] **C2 Offline templates.** Inline Leaflet + fonts in `apache_*` (or finish porting their panels onto the gui4gmns canvas — SCI already ported). Every shipped template works with no network.
  *Done-test:* load each template with the network disabled; nothing 404s.
- [ ] **C3 CHANGELOG + version bump to 0.2.0** on the above.

## Phase D — coverage (grow the catalog)
- [ ] **D1 Caltrans PeMS** highway detector template (`highway_sensor_timeseries`) — the corridor-detector counterpart to the trajectory-rich ITS I-95 hub.
- [ ] **D2 NGSIM I-80/US-101** trajectory template (`highway_vehicle_trajectory`) — lane-change / car-following / FD sampling.
- [ ] **D3 GTFS multimodal** real dataset behind `gmns_dashboard_04`.
- [ ] **D4 ITS DataHub geofence query** template (`its_open_data_geofence_query`).

## What's already done (v0.1)
Generator (pure-Python, pip-installable, self-contained offline output) · web-lite / web-gl / desktop-qt
viewers · hybrid OSM+satellite embedded basemaps · QVDF time-dependent speed + corridor INRIX-vs-model
contour · demand OD + distributions (from plot4gmns) · **7-check SCI physics panel in every dashboard**
· ITS I-95 6-source data hub (2.3 GB → 5.2 MB) · dataset catalog + manifest schema (spec) · privacy gate.

## Sequencing rationale
A before B: no point building the catalog engine four times across four folders. B before C: enforce
correctness before refactoring internals. D anytime after B2/B3 exist (new datasets then plug into a real
engine with real gates, not a folder of HTML).

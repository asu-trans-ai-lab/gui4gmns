# gui4gmns — AI Agent Working Guide (QA, Release & Documentation) · v1.1

> **Audience:** an AI coding agent (Claude Code or similar) working with Ziyi Zhang.
> **Repo:** `asu-trans-ai-lab/gui4gmns` · Site: https://asu-trans-ai-lab.github.io/gui4gmns/
> **Human roles:** Prof. Xuesong (Simon) Zhou develops the core generator/engine; Ziyi is the
> package maintainer, first user, QA lead, and release manager.
> **Read this file at the start of every session. Then read `qa/qa_state.json` to see where work left off.**
>
> **v1.1 (2026-07-06):** aligned with the consolidated repo (dtalite/ + C++ kernel workspace +
> dynamic_ODME merged 2026-07; "releases happen in ONE place"). Changes: SHARED_CONTRACT.md is now
> the QA baseline; portals auto-export with every dashboard run; new checkpoints K–N (auto-portals,
> data-quality audit, CLI flags, import API); new matrix columns ENG and FIG; DATASETS_COVERAGE.md
> is the authority for n/a cells; local-only restricted datasets and a private-data guard test added.

---

## 0. Mission and definition of success

gui4gmns turns a GMNS run folder (node.csv, link.csv, optionally link_performance.csv,
trajectory/agent files) into (a) one self-contained `dashboard.html` (plus split
`dashboard_layers/*.js` unless `--single`), (b) **automatically** a `portals/` folder beside it
(kepler / deckgl / qgis / kml), and (c) static figures. It is the cross-platform successor to the
NEXTA GUI (NEXTA remains the editor; gui4gmns is the viewer + generator), covering DTALite /
TAPLite / Dynamic ODME / DLSim outputs. All viewers implement one data contract:
**`SHARED_CONTRACT.md`** — that file is the QA baseline for what "correct" means.

The professor's concerns define success:

1. **End-to-end verification with human eyes.** Exporters and adapters have never been
   demonstrated to him. → Every matrix cell exercised, evidence recorded, human-eye pass cheap.
2. **The release pipeline has never fired.** GitHub shows "No releases published" while the
   README already advertises `pip install gui4gmns` — the command publicly fails today. → v0.1.0.
3. **The dashboards now claim to check themselves** (built-in data-quality audit: MOE coverage,
   flow conservation, oversaturation, suspicious zero-volume links, connector sentinels). A QA
   feature is itself a QA target: verify the audit catches planted defects and stays quiet on
   clean data.

**Definition of done:** v0.1.x live on PyPI; QA matrix has no `untested` cells; every
`fail`/`partial` has an issue; guard test passes; SKILL docs merged; weekly report sent.

---

## 1. Hard rules (never violate)

1. **Private data is a red line.** Restricted sources: NVTA, VDOT, INRIX, CBI, probe data, any
   QVDF corridor derived from them, `*PRIVATE*`/`*nvta*` patterns, and
   `datasets/08_public_ITS_VA_1-95_sample/` (git-ignored despite the name). Never commit,
   export, screenshot-into-repo, or embed any of it. Run `python validate_no_private_data.py`
   before **every** commit and **every** release tag.
2. **Local-only datasets stay local.** ITS I-95 (VA) and NVTA I-395 rows in the QA matrix are
   marked `local` — they may be exercised on Ziyi's machine for demonstration, but their
   evidence screenshots go to a local folder, never into `qa/evidence/` in the repo.
3. **Guard test is mandatory** (Phase 0.7): plant a decoy file matching a private pattern in a
   scratch clone, confirm `.gitignore` excludes it AND `validate_no_private_data.py` flags it.
   The guard protecting rule 1 must itself be proven.
4. **Public datasets only** for anything committed: shipped samples (01/02/05/07), I-210E
   PeMS-derived views (cleared, attributed), TransportationNetworks-derived nets.
5. **Do not invent paths or flags.** §2 reflects the 2026-07 consolidation but Phase 0 still
   re-verifies everything with `ls` and `--help` and corrects this guide.
6. **No force-push, no history rewrites on shared branches, no deleting releases.**
   Destructive git actions require Ziyi's explicit confirmation.
7. **One issue per defect** (template §8). **Every claim needs evidence** (screenshot path or
   console excerpt); "looks fine" without evidence = `untested`.
8. Semver; exporter/contract output-format changes bump minor.

---

## 2. Repo map (post-consolidation, verify in Phase 0)

| Area | Location | Role |
|---|---|---|
| Generator core | `ai-gen/gui4gmns.py` | GMNS folder → dashboard + auto `portals/` + figures; pure Python, no deps |
| Generator docs | `ai-gen/VIZ_SCHEMA.md`, `ai-gen/LEARNINGS_FROM_PLOT4GMNS.md` | AI-guided portal building; design provenance |
| web-lite viewer | **`nexta_x.html` (repo root)** + `web-lite/` | zero-install drag-drop QC |
| web-gl viewer | `web-gl/nexta_xgl.html` | GPU regional animation, live-follow a running sim |
| desktop-qt | `desktop-qt/nexta_qt.py` | desktop app: open folders, **Run engine**, basemaps, headless snapshots |
| Engine | `engine/DLSim_STE/` (C++17 src + toy testdata + `build.sh`); `engine/bin/` git-ignored | build from source; feeds desktop-qt Run button |
| Exporters | `exporters/gmns_to_viz.py` (`--target kepler/deckgl/kml/qgis/all`), `exporters/README.md` | manual export path (auto path is via generator) |
| Adapters | `adapters/` (`its_datahub.py`, `semidynamic_trajectories.py`, …) | external data → GMNS; trajectory synthesis |
| Renderers/figures | `renderers/`, dashboards' `figures/` output | static PNG for papers |
| QGIS plugin | `qgis-plugin/` | QGIS-side integration (scope: discover in Phase 0) |
| Python lab | `python-lab/` | scratch/experiments (confirm whether shipped in wheel) |
| Datasets | `datasets/`: `01_sioux_falls`, `02_chicago_sketch` ★showcase, `05_*` toys (bottleneck/merge/signal), `07_west_jordan` | public samples |
| Corridor views | `docs/dashboards/I210E_*.html` (calendar / network / space-time) | PeMS-derived, public, the "ask AI for more" template |
| Contract & plans | `SHARED_CONTRACT.md` (QA baseline), `NAMING.md`, `REFACTOR_PLAN.md` | read in Phase 0 |
| Docs & site | `docs/` (Users Guide md+pdf, VISUALIZATION_PORTALS.md, DATASETS_COVERAGE.md), gallery, `portal_demo/` | GitHub Pages |
| Guard | `validate_no_private_data.py`, `.gitignore` | private-data defense |
| Packaging & CI | `pyproject.toml`, `.github/workflows/` | PyPI trusted publisher (configured 7/5, never fired) |

External but referenced (do **not** expect in-repo): ARC Atlanta & Chicago Regional large nets →
`asu-trans-ai-lab/dynamic-odme-lab`; DTALite/TAPLite C++ kernels → their own dev repos.

---

## 3. Phase 0 — Discovery & environment

0.1 Access check: clone, org membership/admin rights, push+delete a trivial branch.
0.2 Read in order: README → **SHARED_CONTRACT.md** → NAMING.md → REFACTOR_PLAN.md →
    docs/VISUALIZATION_PORTALS.md → docs/DATASETS_COVERAGE.md → exporters/README.md →
    ai-gen/VIZ_SCHEMA.md → workflow YAMLs → pyproject.toml.
0.3 Inventory `ls -R` (depth 3); `--help` on gui4gmns.py, gmns_to_viz.py, nexta_qt.py, each
    adapter. **Correct this guide** (§2 table, §5 axes) where reality differs; commit the diff.
0.4 Environment: venv; `pip install -e .`; record packaging errors (Phase 1 blockers → issues).
0.5 QA scaffold on a working branch: `qa/qa_state.json`, `qa/qa_report.html`, `qa/evidence/`
    (+ local-only evidence dir **outside** the repo, e.g. `~/gui4gmns_local_evidence/`).
0.6 Smoke test: generator on a toy dataset → does a dashboard + `portals/` appear at all.
0.7 **Guard test** (rule 3). Record verdict in the report as a finding.
0.8 Presence check: confirm which DATASETS_COVERAGE rows physically exist in-repo (Tucson I-10?
    ARC Atlanta?) vs referenced-elsewhere vs local-only; set matrix rows accordingly.

**Exit:** corrected guide + scaffold committed; smoke + guard verdicts recorded.

---

## 4. Phase 1 — Release v0.1.0 to PyPI (highest priority; README already advertises the command)

1.1 Fix packaging until `pip install -e .` and `python -m build` pass. Check: name lowercase
    `gui4gmns`, version single-sourced, entry point / `from gui4gmns import generate` works
    post-install, package-data includes runtime templates and basemap assets, decide whether
    `python-lab/` and `engine/` are excluded from the wheel (they should be).
1.2 TestPyPI dry-run if the workflow supports it (else add a TestPyPI job); clean-venv install.
1.3 `python validate_no_private_data.py` must pass.
1.4 Tag `v0.1.0` + GitHub Release: auto notes + honest human summary (works / experimental),
    sourced from QA findings so far.
1.5 Watch Actions. Likely failure: trusted-publisher name mismatch (the 7/5 session initially
    confused workflow-name vs publisher config). Capture exact error, fix, document, retry.
1.6 Verify from a user's seat: clean venv → `pip install gui4gmns` → generate on a toy →
    dashboard opens; `import gui4gmns; generate(...)` also works. Screenshot both.
1.7 Write `docs/RELEASING.md` (one page, exact commands, the publisher-config gotcha).

**Exit:** v0.1.0 installable; import API verified; RELEASING.md merged; evidence recorded.

---

## 5. Phase 2 — Systematic QA

### 5.1 Matrix axes

**Rows (datasets)** — public, in-repo: `toys (05_*)`, `sioux_falls (01)`,
`chicago_sketch (02 ★ deepest coverage)`, `west_jordan (07)`, `i210e (docs/dashboards views)`.
Marked `local`, optional, evidence stays off-repo: `its_i95 (VA)`, `nvta_i395`.
Presence-dependent (Phase 0.8): `tucson_i10`, `arc_atlanta`.

**Columns (components):**

| Code | Component | How to exercise |
|---|---|---|
| GEN | ai-gen dashboard **+ auto-portals** | `python ai-gen/gui4gmns.py <ds>` → dashboard.html, `dashboard_layers/`, `portals/`, `figures/` |
| LITE | web-lite | open root `nexta_x.html`, drag node.csv/link.csv in |
| WGL | web-gl | `web-gl/nexta_xgl.html`, load run; GPU animation; live-follow if engine running |
| QT | desktop-qt | `python desktop-qt/nexta_qt.py`: open folder, basemap, snapshot |
| ENG | DLSim_STE engine | `engine/DLSim_STE/build.sh` from source → run on toy testdata → QT **Run engine** button end-to-end |
| K / D / KML / QGS | portal exports | prefer the **auto** `portals/` output; spot-check `gmns_to_viz.py --target X` produces the same; load each in its portal (kepler.gl/demo, browser, Google Earth Web, QGIS) |
| FIG | static figures | `figures/` PNGs + `renderers/`: render, labels legible, match data |
| AD | adapters | each adapter on its sample input → output feeds GEN; incl. trajectory **auto-synthesis** on Chicago Sketch |
| GAL | gallery / site / portal_demo | click every link on the live Pages site; record 404s; dashboards/ index |

**n/a authority:** `docs/DATASETS_COVERAGE.md`'s capability table decides which checkpoints apply
per dataset (e.g. Sioux Falls ships no MOE → checkpoint D there is `na` citing the table, not a
gap). Any n/a **not** derivable from that table needs a one-line reason.

### 5.2 Checkpoints per artifact

- **A. Loads clean** — opens from `file://`; zero console errors.
- **B. Offline honesty & packaging modes** — DevTools Network: no failed external requests.
  Default mode: dashboard + `dashboard_layers/*.js` travel together and load; `--single` mode:
  one file truly self-contained; hybrid basemap (OSM + satellite) embedded and works offline.
- **C. Topology sanity** — rendered node/link counts match CSVs (±header); geography recognizable.
- **D. MOE layers** — volume / V/C / queue / time-dependent flow / **QVDF speed** color + legend;
  spot-check 2–3 rows against link_performance.csv.
- **E. Animation** — play/scrub 15-min bins; green-moving/red-queued dots follow links;
  `--max-traj N` respected.
- **F. Demand views** — OD desire lines, demand matrix heatmap, attribute distributions.
- **G. Basemap** — `--basemap osm|satellite|none` each work; alignment/projection correct.
- **H. Size & speed** — file sizes (dashboard, layers, portals) + cold-load time; flag >30 MB
  or >10 s; note the embedded-tiles cost.
- **I. Cross-browser** — Chrome + one of Edge/Firefox.
- **J. Export fidelity** — same counts/geometry/styling after the round trip into each portal;
  per-portal README present and its instructions actually work.
- **K. Auto-portal completeness** — one GEN run wrote all four portal folders; `--no-portals`
  skips them.
- **L. Data-quality audit** — on clean data: no false alarms. Then plant one defect per class
  (break conservation on a node, zero-out a major link's volume, oversaturate a link, orphan a
  connector) → audit flags each. Record per-class hit/miss.
- **M. Corridor contour & validation stats** — space-time contour renders; RMSE / R² / bias
  displayed and plausible (recompute one by hand from the CSV).
- **N. Import API** — `from gui4gmns import generate` produces identical output to the CLI.

### 5.3 Per-cell workflow

```
generate/export → open → walk applicable checkpoints (per DATASETS_COVERAGE)
→ screenshot each → qa/evidence/<dataset>__<component>__<checkpoint>.png   (local-only ds → local dir)
→ verdict + notes into qa_report.html RESULTS → fail/partial ⇒ GitHub issue, link #
→ update qa/qa_state.json
```

Agent pre-screens all machine-checkable items (console, counts, sizes, headless screenshots);
visual-judgment items get `needs_human` with artifact + screenshot prepared, so Ziyi's pass is
confirm/overturn only.

**Priority order** (professor's doubts first, showcase second):
1. GEN + auto-portals on **chicago_sketch** (the public showcase must be flawless), incl. K/D/KML/QGS loads
2. AD adapters — `its_datahub.py` (on public sample structure only), `semidynamic_trajectories.py` auto-synth
3. Checkpoint **L** audit verification on toys (plant defects there, cheap to reason about)
4. GEN on remaining public datasets; I-210E three views
5. ENG build + QT Run-engine loop
6. Viewers LITE / WGL / QT; FIG
7. GAL full link sweep

**Exit:** no `untested` cells; L has per-defect-class results; issues filed; report regenerated.

---

## 6. Phase 3 — Generality (template reuse with new data)

6.1 One external public network (TransportationNetworks city or osm2gmns export) through the
    full GEN + portals pipeline → new matrix row.
6.2 **Ziyi's Bay Area network** (AMS-for-GMNS) through the pipeline — generality QA + UAM
    simulator visualization in one. Outputs stay local until provenance is confirmed public.
6.3 Synthesize minimal link_performance.csv + trajectory.csv for a toy → prove D/E/K light up on
    user-supplied data, not just shipped demos.
6.4 I-210E recipe reuse: regenerate the calendar / network / space-time trio for a different
    corridor or year from a GMNS net + link-speed table (this validates the "ask the AI for
    more" claim and directly serves Ziyi's PeMS calibration work).
6.5 Log every friction point (column names, CRS, encoding, required-vs-optional fields) — raw
    material for Phase 4.

---

## 7. Phase 4 — Documentation

- `docs/SKILL_gui4gmns.md` — for humans *and* AI agents: minimal GMNS input contract (distilled
  from SHARED_CONTRACT.md), one-command dashboard recipe, portals recipes (auto + manual),
  swapping a dataset into a template (`DATA = {...}` / `dashboard_layers` structure), using
  VIZ_SCHEMA.md to have an AI build a new portal, the I-210E corridor-trio reuse recipe,
  troubleshooting seeded from every Phase 2/3 issue.
- `docs/RELEASING.md` (from Phase 1).
- Style: imperative, copy-pasteable, one worked example per recipe.

---

## 8. Issue template

```
Title: [component][dataset] one-line symptom
## Environment      gui4gmns version/commit · OS · browser · Python
## Steps            exact commands, exact dataset
## Expected / Actual  one line each
## Evidence         qa/evidence/<file>.png · console excerpt
## Severity         blocker / major / minor / cosmetic
## Matrix cell      <dataset> × <component> × <checkpoint letter>
```

Labels: `qa`, component, severity. Blockers pinged to Ziyi immediately.

---

## 9. Reporting — `qa/qa_report.html`

Single self-contained HTML (gui4gmns philosophy). Agent edits only `window.RESULTS`:

```js
window.RESULTS = {
  meta: { project, repo_url, updated, release_version, reporter },
  summary_note: "3–5 sentences: changes since last report, top risks, asks for Prof. Zhou",
  phases: [ { id, name, status: "done|active|blocked|todo", note } ],
  components: [ { code, label } ],
  datasets:   [ { id, label } ],          // suffix " (local)" for restricted rows
  cells: [ { dataset, component, verdict: "pass|partial|fail|needs_human|na|untested",
             checkpoints: {A:"pass", ...}, note, evidence: [], issue: "" } ],
  findings: [ { id, severity, title, detail, issue, evidence } ]
}
```

Verdicts render as Level-of-Service grades (A/C/D/F). Update after every session; before the
weekly meeting export (or print-to-PDF) and send with summary_note as the email body. The report
must answer in one glance: what is verified, what is broken, what needs the professor's decision.

---

## 10. Session protocol

1. Read this guide → `qa/qa_state.json` → announce a ≤5-line plan.
2. Work highest-priority open item (Phases 1→2→3→4; §5.3 order within Phase 2).
3. Before ending: update RESULTS + qa_state.json; run `validate_no_private_data.py` if anything
   staged; commit to working branch; list files touched + issues filed.
4. Never end a session with work done but unrecorded.

## 11. Backlog (Phase 5 — after 1–4 green)

- Dashboard enhancements: corridor comparison view (feeds future corridor2GMNS multi-source
  diff), UAM-corridor views for the Bay Area simulator, legend polish.
- `qgis-plugin/` deeper QA once its scope is clear from Phase 0.
- Nightly link-checker for the Pages site; headless screenshot harness so a full matrix re-run
  is one command; TestPyPI job in CI if absent.

# gui4gmns — critical review (Fable 5)

Reviewer's stance: assume this ships to strangers next week. What breaks, what's fragile, what's a
spec pretending to be a tool. Findings are ranked by severity, each with the fix. Strengths are listed
honestly at the end so the plan doesn't throw them away.

## Severity 1 — will bite soon
| # | finding | evidence | fix |
|---|---|---|---|
| 1 | **Four redundant working copies** of the repo (`gui4gmns/github_dev`, `gui4gmns/github_release`, `gui4gmns_dev`, `gui4gmns_release_github`) plus a locked leftover `guiagent4gmns` and the `gui4gmns/` intermediate. The generator is hand-copied across them. | This turn alone I `cp`'d `gui4gmns.py` into 3 siblings. | **Collapse to ONE dev + ONE release folder.** Everything else deleted once the file locks clear. Single source of truth. |
| 2 | **A folder move already destroyed 8 files + git history** earlier this session (partial `Move-Item` + delete). Recovered from a stray copy, but it proves the churn is dangerous. | `nexta_x.html`, `README`, `LICENSE`, etc. lost and rebuilt. | Stop moving 250 MB trees. Use `git clone` (lock-immune) for any restructure; keep raw data OUT of the repo. |
| 3 | **The 2.3 GB raw ITS source sits inside the repo tree** (git-ignored, but one `git add -f` from a leak). | `datasets/08_public_ITS_VA_1-95/` = 2.3 GB inside `github_dev`. | Move raw sources to a sibling `_raw_sources/` OUTSIDE any git repo; adapters read from there by path. |

## Severity 2 — quality / trust gaps
| # | finding | fix |
|---|---|---|
| 4 | **No automated tests.** SCI panel, adapters, generator all verified by hand in-browser. A refactor could silently break generation. | Add `tests/` with golden-number checks (Chicago Sketch: 2,950 links, conserved; ITS sample: 6 layers, row counts) + a headless "does it generate + JSON parses" smoke test. Wire GitHub Actions. |
| 5 | **The catalog is a spec with no engine.** `dataset_catalog.json` + `qa_contract` strings exist, but nothing reads the catalog to pick a template, and nothing runs the declared QA gates before generation. | Build `catalog_run.py`: query → match manifest → run `qa/validate_*.py` → bind adapter → emit dashboard. This is what makes the GUI "intelligent" rather than a folder of HTML. |
| 6 | **QA gates are declared, not enforced.** SCI runs *inside* the dashboard (good), but the manifest's `qa_contract` is inert. The user's design doc §6 explicitly wanted a pre-generation gate. | Implement `qa/validate_gmns.py`, `validate_trajectory.py`, `validate_corridor.py`; each returns pass/fail keyed to the `qa_contract` names. The catalog engine blocks generation on failure. |
| 7 | **Privacy validator is filename-pattern only.** A private file without `nvta`/`private` in its name slips through. | Add a content heuristic (scan committed CSVs for known private column names / TMC-ID formats) and a size gate (warn on any tracked file > 5 MB). |

## Severity 3 — maintainability / polish
| # | finding | fix |
|---|---|---|
| 8 | **The generator is a 35 KB monolith** with a ~10 KB HTML template as an inline string. Editing the template means editing a Python string literal. | Split: `gui4gmns/core.py` (load/preprocess) + `gui4gmns/template.html` (read at build). Package it as `src/gui4gmns/` with the template as package data. |
| 9 | **CDN dependencies in some templates** (`apache_traffic_simulation.html` pulls Leaflet + Google Fonts). Breaks the offline/self-contained promise; fails under a strict CSP. | Inline Leaflet + fonts, or port the physics panel onto the gui4gmns canvas (already partly done via the SCI port). Mark CDN templates clearly in the catalog (done). |
| 10 | **Two brand names** (NeXTA-X product / gui4gmns package). Fine, but state it once, everywhere. | One line in README (present); keep it consistent. |
| 11 | **No dependency/version pinning, no CHANGELOG.** | Add `CHANGELOG.md`; pin optional deps to major versions (done in pyproject: `pyproj>=3`, `PySide6>=6`). |

## Strengths (keep these — the plan must not regress them)
- **Core generator is genuinely good**: pure-Python stdlib, zero required deps, self-contained *offline* HTML output, embedded hybrid OSM/satellite basemap, split lightweight layers, self-auditing data-quality footer. Now a clean pip package (`gui4gmns 0.1.0`, wheel installs, CLI + `import gui4gmns`).
- **The ITS adapter is real engineering**: streams 2.3 GB without loading it, 6 sources → 5.2 MB, all layers preserved and joined via SegmentId/tmc/zone → link geometry.
- **SCI physics panel** is a real, fault-injection-verified feature in every dashboard.
- **The catalog architecture is sound** — dataset-first with QA contracts is the right model; it just needs the engine (finding 5/6).
- **Privacy discipline held** even through the data-loss incident: 0 private files ever tracked.

## The one-sentence verdict
The *product* (generator + dashboards + ITS data hub + SCI gates) is strong and shippable; the
*workspace* (four copies, raw data in-tree, no tests, catalog-without-engine) is where the risk lives —
so the improved plan front-loads consolidation, tests, and turning the catalog spec into a running engine.

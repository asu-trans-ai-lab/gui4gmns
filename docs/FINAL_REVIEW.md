# gui4gmns — final review before GitHub upload (go/no-go)

Pre-publication checklist. Everything below was verified this session in the `github_dev` tree; the
public `github_release` is a clone with zero private data.

## Go/no-go checklist
| check | status | evidence |
|---|---|---|
| **Privacy** — no agency data tracked | ✅ GO | `validate_no_private_data.py` = *clean*; NVTA/VDOT/INRIX/CBI git-ignored; NVTA I-395 rendered locally only |
| **Core generates** | ✅ GO | `gui4gmns.generate(folder)` -> self-contained `dashboard.html` + `figures/`; verified on 9 datasets |
| **Offline** | ✅ GO | data + OSM/satellite tiles embedded as data-URIs; opens with no network |
| **PyPI package** | ✅ GO | `python -m build` -> wheel + sdist; **`twine check` PASSED**; `pip install` -> `import gui4gmns 0.1.0`, CLI on PATH |
| **Figures auto-export** | ✅ GO | generator writes `figures/` (15 native plot4gmns-style PNGs) alongside every dashboard; `--no-figures` to skip; skips gracefully w/o matplotlib |
| **Dashboard gallery (one folder)** | ✅ GO | all dashboards in `docs/dashboards/` w/ a browsable `index.html` (base = network dashboards; + corridor state-views); 6 self-contained dashboards shipped, each <5 MB, zero external refs |
| **Gallery index** | ✅ GO | `docs/gallery.html` — dashboards (base) + 22 additional static figures, 9 datasets, all load |
| **AI-generation note** | ✅ GO | gallery states users can ask the AI to regenerate views for more data (ITS I-95 corridors, other years) — the capability, surfaced |
| **Real networks** | ✅ GO | ARC 145k links (~5 s), Tucson I-10, Chicago, ITS I-95 hub, global 15-city montage |
| **Reviews attached** | ✅ GO | Fable-5, TRB-viz (AED30), stakeholder (7-audience), viz-landscape |
| **License / provenance** | ✅ GO | MIT; sample data attributed (TransportationNetworks, OSM, Esri); ARC = converted research copy w/ disclaimer |
| **Corridor sample provenance** | ✅ GO | `docs/dashboards/I210E_*.html` (calendar/network/space-time) — **approved for public release** (user decision, 2026-07-06). NeXTA-AI-Gen samples from the *TrafficFlowBench-CA* benchmark; corridor speeds derive from **Caltrans PeMS** (public agency data). Attributed in the gallery corridor section + `DATASETS_COVERAGE.md` + page footers. |
| **Tests / CI** | ⚠️ NOT YET | roadmap B1 — no automated tests; verification is manual. Recommend before a v1.0 tag. |
| **Size** | ⚠️ WATCH | a few tracked figures/templates > 5 MB (size gate warns); trim before heavy public traffic |

**Verdict: GO for an initial public v0.1.0** (clearly labeled pre-1.0). The one remaining gap is automated
tests/CI (B1) — fine for a research/preview release, needed before a 1.0 tag. The I-210E corridor samples
are cleared to ship (attributed to Caltrans PeMS / TrafficFlowBench-CA).

## Dashboard gallery — one folder, HTML is the base
`docs/dashboards/` is the single browsable folder (open `index.html` or any card):
- **Network dashboards (the base)** — 6 self-contained gui4gmns dashboards: Sioux Falls, Chicago Sketch,
  3 toys, West Jordan. Rebuild with `python renderers/build_dashboards.py` (ARC / Chicago-Regional are
  generate-on-demand, >6 MB single-file). **HTML dashboards are the primary output.**
- **Corridor state-views** — per corridor, the NeXTA-AI-Gen trio (`<view>_<corridor>_<date>.html`):
  *calendar* (whole year by day/year), *network* (map by mean speed), *space-time* (milepost×time heatmap).
- **plot4gmns / MOE figures are *additional*** static images (in `p4g_native_gallery/`, `moe_gallery/`).

**AI-generation, surfaced to users:** the gallery says these pages are AI-generated from a GMNS network +
a link speed/`link_performance` table, and that users can ask for the same views on **more data — e.g. the
ITS I-95 corridors, or other years** of a corridor (the calendar already spans a year, so multi-year is one
more run). Pipeline: `04_nexta_ai_gen/make_html_viz.py <corridor> <date>` (or `--state <ai_output.csv>`).

## What ships (public release contents)
- **Core**: `ai-gen/gui4gmns.py` (pure-Python generator, pip-installable) + `pyproject.toml`
- **Viewers**: `nexta_x.html`, `web-gl/`, `desktop-qt/`
- **Renderers**: `moe_static.py` (bandwidth + space-time contours), `bottleneck_pems.py` (PeMS/RITIS), `city_montage.py`, `gmns_figures.py` (native plot4gmns), `build_gallery.py`
- **Adapters**: ITS I-95 hub, semi-dynamic trajectory synthesis
- **Exporters (GUI-X)**: kepler.gl / deck.gl / QGIS / Google Earth KML
- **Datasets**: public samples (Sioux Falls, Chicago Sketch, toys, West Jordan) + coverage matrix
- **Dashboard gallery**: `docs/dashboards/` (one folder, `index.html`) + `docs/gallery.html` (full index) built by
  `renderers/build_dashboards.py` + `renderers/build_gallery.py`
- **Docs**: Users Guide, PACKAGE, gallery, DATASETS_COVERAGE, ROADMAP, all reviews

## Upload steps (when you say go)
```bash
# 1) GitHub
cd gui4gmns/github_release
python validate_no_private_data.py            # must say clean
git push -u origin main                        # -> github.com/asu-trans-ai-lab/gui4gmns

# 2) PyPI (from github_dev; needs a PyPI API token)
python -m build
python -m twine check dist/*                   # PASSED
python -m twine upload dist/*                   # enter token; or use TestPyPI first:
#   python -m twine upload --repository testpypi dist/*
```

## Known limitations (state them in the README, don't hide)
- No automated tests yet (B1). · Static corridor figures are *space* profiles unless the dataset carries
  time-dependent link data. · PyPI wheel = the generator core; the renderer/exporter CLIs ship in the
  repo (bundling them into the package is roadmap C1). · Some DTALite period-column schemas need a small
  adapter for volumes. · Movement figures show connectivity, not survey-accurate turn arcs.

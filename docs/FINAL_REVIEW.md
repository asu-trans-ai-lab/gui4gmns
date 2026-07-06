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
| **Gallery** | ✅ GO | `docs/gallery.html` — 22 figures, 9 datasets, all load |
| **Real networks** | ✅ GO | ARC 145k links (~5 s), Tucson I-10, Chicago, ITS I-95 hub, global 15-city montage |
| **Reviews attached** | ✅ GO | Fable-5, TRB-viz (AED30), stakeholder (7-audience), viz-landscape |
| **License / provenance** | ✅ GO | MIT; sample data attributed (TransportationNetworks, OSM, Esri); ARC = converted research copy w/ disclaimer |
| **Tests / CI** | ⚠️ NOT YET | roadmap B1 — no automated tests; verification is manual. Recommend before a v1.0 tag. |
| **Size** | ⚠️ WATCH | a few tracked figures/templates > 5 MB (size gate warns); trim before heavy public traffic |

**Verdict: GO for an initial public v0.1.0** (clearly labeled pre-1.0). The one real gap is automated
tests/CI (B1) — fine for a research/preview release, needed before calling it 1.0.

## What ships (public release contents)
- **Core**: `ai-gen/gui4gmns.py` (pure-Python generator, pip-installable) + `pyproject.toml`
- **Viewers**: `nexta_x.html`, `web-gl/`, `desktop-qt/`
- **Renderers**: `moe_static.py` (bandwidth + space-time contours), `bottleneck_pems.py` (PeMS/RITIS), `city_montage.py`, `gmns_figures.py` (native plot4gmns), `build_gallery.py`
- **Adapters**: ITS I-95 hub, semi-dynamic trajectory synthesis
- **Exporters (GUI-X)**: kepler.gl / deck.gl / QGIS / Google Earth KML
- **Datasets**: public samples (Sioux Falls, Chicago Sketch, toys, West Jordan) + coverage matrix
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

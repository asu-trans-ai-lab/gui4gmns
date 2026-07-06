# Multi-stakeholder review of gui4gmns

A structured critique of the package from the seven audiences who'd actually use or vet it. Each entry:
what they value, what they'd flag, and what they need next. (Fable-5 synthesis of how each community
reviews such tools — not attributed to individuals. Circulate the gallery + `PACKAGE.md` for real sign-off.)

## 1. Industry / traffic-engineering consultant (Kittelson/HDR/WSP/AECOM-type)
- **Values:** report-ready static PNGs (no screen-copy), reproducible `generate(folder)`, zero-install client deliverable, the MOE gallery matching NeXTA they already trust.
- **Flags:** needs one-click **PDF/PPTX export** of a figure set; client-facing **branding/title block**; a QA sign-off artifact (the SCI panel helps, but they want it on the *static* figure too).
- **Needs:** batch figure export + provenance/title block (roadmap E10); a "deliverable pack" (map + corridor + space-time + summary) as one PDF.

## 2. Agency / MPO transportation planner
- **Values:** GMNS as the lingua franca; corridor + scenario views; a public-shareable offline HTML; demand OD + bottleneck reading.
- **Flags:** wants **before/after scenario comparison** (build vs no-build) side-by-side; public accessibility; network **editing** (correctly deferred to legacy NeXTA).
- **Needs:** two-scenario dashboard (roadmap: extends the catalog); embeddable public page; ADA/508 basics.

## 3. USDOT / BTS / FHWA GIS review
- **Values:** open standard (GMNS), open-source (MIT), reproducibility, the ITS-DataHub fusion (I-95 hub), national consistency.
- **Flags:** **CRS / projection metadata** must be explicit (we have `crs.txt` per dataset — surface it in outputs); **FGDC/ISO 19115 metadata** for shared layers; **Section 508 accessibility** (alt text, contrast, keyboard) for any public dashboard; data-provenance stamp.
- **Needs:** metadata sidecar on exports (GeoJSON already carries CRS; add a metadata block); 508 pass on the dashboard; provenance stamp (E10). The GUI-X exporters (QGIS/kepler/KML) align well with federal GIS workflows.

## 4. State DOT / MPO analyst (ADOT, VDOT, MAG, ARC, NVTA)
- **Values:** *their* real networks run (ARC 145k, NVTA I-395, Tucson I-10); TMC/probe + QVDF integration; congestion/space-time; offline for the field.
- **Flags:** needs their **native schema** ingested (DTALite period columns — partly done for Tucson); **signal/movement** detail; calibration transparency (INRIX-vs-QVDF contour delivers this); **bottleneck ranking** (RITIS-style).
- **Needs:** schema adapters per agency; movement/turn layer; corridor auto-ranking (E11). The AZ subarea tool (D5) is on their ask list.

## 5. Academic researcher
- **Values:** open + scriptable + reproducible; the space-time (Edie/Treiterer) framework; **semi-dynamic trajectory synthesis** (Eulerian→Lagrangian); the STS coherence idea; benchmark networks (the global city store).
- **Flags:** needs **citation/DOI**, methods write-up for the synthesis + QVDF, **unit tests** (roadmap B1), API stability, and clear separation of validated vs heuristic (BPR-derived speed is a model, not data — labeled, good).
- **Needs:** a methods note + CITATION.cff; tests/CI (B1); the catalog engine (B2) to make experiments declarative.

## 6. Student
- **Values:** zero-install, teaching cases (toy bottleneck/merge/signal, four-step), a real Users Guide, learn GMNS + MOE + space-time hands-on.
- **Flags:** wants **guided exercises** (open dashboard X, find the bottleneck, read the contour); a gentle onramp; the physics checks (SCI) as a learning aid ("why did this fail?").
- **Needs:** a short tutorial/assignment set on the toy + Chicago datasets; the SCI panel as a teaching lens.

## 7. University instructor
- **Values:** the whole thing as courseware — CEE-372-style; reproducible; free; the global city store for cross-city comparison assignments; the "dataset-first catalog" as a teaching structure.
- **Flags:** wants slide-ready figures (montage delivers), a syllabus fit, grading-friendly reproducibility.
- **Needs:** a teaching module (datasets + guide + exercises) — the global montage + toy cases + Users Guide are 80% there.

## Common threads (do these and you satisfy most audiences)
1. **Provenance + metadata + PDF/PPTX export** (consultants, USDOT GIS, State DOT) → roadmap **E10**.
2. **Scenario A/B comparison** (planners, State DOT, researchers) → new **E14**.
3. **Tests/CI + citation** (researchers, students) → **B1** + `CITATION.cff`.
4. **508 / accessibility** (USDOT, public agencies) → **E7-accessibility**.
5. **Agency schema adapters + bottleneck ranking + movements** (State DOT) → **D5/E11** + movement layer.

## Coverage evidence for reviewers
- **Global data store** (`renderers/city_montage.py`, `docs/moe_gallery/global_city_coverage.png`): 15
  TransportationNetworks benchmark cities (Anaheim → Seattle, 76 → 34k links) rendered in ~5 s — proof
  gui4gmns reads the whole GMNS store, not one hand-picked network.
- **Flagship + partial coverage:** `docs/DATASETS_COVERAGE.md`.
- **MOE gallery + reviews:** `docs/moe_gallery/`, `TRB_VIZ_REVIEW.md`, `VIZ_LANDSCAPE_REVIEW.md`, `REVIEW_FABLE5.md`.

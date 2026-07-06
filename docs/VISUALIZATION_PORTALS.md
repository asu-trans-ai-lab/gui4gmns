# Visualization portals — one GMNS folder, many ways to explore it

**The idea, in one line:** GMNS is to transportation what **DICOM is to medical imaging** — a shared,
open exchange format. In medicine you never look at a raw DICOM file; you open it in a *portal* (an offline
desktop viewer, or an online one like OHIF). Transportation data deserves the same. **gui4gmns is the
bridge: point it at any GMNS run folder and it opens that data in a whole family of visualization portals —
some fully offline, some rich online platforms — without you rewriting the data each time.**

You edit the network in the legacy NEXTA GUI (or any GMNS editor). Everything below is for *seeing* it.

![One GMNS folder to many visualization portals](portals_hub.svg)

**▶ Live demo** (nothing to install): open the deck.gl view of Chicago Sketch at
**https://asu-trans-ai-lab.github.io/gui4gmns/portal_demo/**, or browse every dashboard and figure at
**https://asu-trans-ai-lab.github.io/gui4gmns/gallery.html**.

> **It's automatic.** Every dashboard the generator makes now also writes a `portals/` folder beside it
> (`kepler/ deckgl/ qgis/ kml/`). Run `python ai-gen/gui4gmns.py <folder>` once and you have the offline
> dashboard *and* every outbound portal export — no extra step (add `--no-portals` to skip).

## The portals

| Portal | Online / offline | Best for | How you get there from a GMNS folder |
|---|---|---|---|
| **gui4gmns dashboard** (the base) | **Offline** (self-contained `.html`) | network + MOE + animation + basemap, share by file, no install | `python ai-gen/gui4gmns.py <folder>` |
| **web-lite** `nexta_x.html` | **Offline** (drag-drop, any browser) | quick QC of GMNS files, zero install | open `nexta_x.html`, drop in your `node.csv`/`link.csv` |
| **web-gl** `web-gl/nexta_xgl.html` | **Offline** | **GPU 3D** animation at regional scale, live-follow a running sim | open the page, load your run |
| **desktop-qt** `desktop-qt/nexta_qt.py` | **Offline** | desktop app: open folders, Run engine, basemaps, snapshots | `python desktop-qt/nexta_qt.py` |
| **Kepler.gl** | **Online** (kepler.gl/demo) | **3D + trajectories + OD arcs**, no-code styling, big data | `python exporters/gmns_to_viz.py <folder> --target kepler` |
| **deck.gl** | **Online** (CDN) | **TripsLayer trajectories**, custom WebGL layers, embed in a site | `... --target deckgl` |
| **Google Earth** | **Online or offline** (Earth web / Pro desktop) | **3D extruded volume bars + a time-stamped fly-through** on the globe | `... --target kml` |
| **QGIS** | **Offline** (desktop GIS) | analysis-grade GIS, joins, print layouts | `... --target qgis` |
| **Static figures** (plot4gmns / MOE) | **Offline** (PNG) | report/paper images, no screen-grabbing | auto-written to `<folder>/figures/`, or `renderers/` |

One command writes all four export portals at once:
```bash
python exporters/gmns_to_viz.py datasets/02_chicago_sketch --target all -o out/chicago_viz
# -> out/chicago_viz/{kepler,deckgl,qgis,kml}/  each with a README telling you exactly what to open
```

## Online *and* offline — the point

- **No internet at all?** The gui4gmns dashboard, web-lite, web-gl, desktop-qt, QGIS, Google Earth Pro, and
  the static figures all work fully offline — the dashboard even embeds its own basemap tiles. Email it,
  drop it on a shared drive, open it on a plane.
- **Have internet?** The *same* GMNS folder also flows outward into the rich online portals — **Kepler.gl**
  and **deck.gl** for 3D and trajectory exploration, **Google Earth** for the globe. You are never locked in:
  the data is a standard format, and each export is a doorway to a different portal.

## 3D and trajectories, specifically (the two things people ask for)

- **3D:** Google Earth (volume-extruded link bars), web-gl (GPU tilt/animation), Kepler.gl (3D hexbin /
  extruded), deck.gl (any custom 3D layer). The offline dashboard also has an oblique 3D tilt.
- **Trajectories (moving vehicles):** the gui4gmns dashboard animation (green moving / red queued), Kepler.gl
  **Trip layer** (4th coordinate = timestamp), deck.gl **TripsLayer** (fading comet trails), web-gl GPU trails,
  and a Google Earth time-stamped tour. Feed them a `trajectory.csv`, or let the generator synthesize one
  from link performance (`adapters/semidynamic_trajectories.py`).

## For students — try your own dataset (this is meant to be modified)

Everything here is a small, readable file you're encouraged to change:

1. **Swap the dataset.** Any GMNS folder with `node.csv` + `link.csv` works — yours, a
   [TransportationNetworks](https://github.com/bstabler/TransportationNetworks) city, an osm2gmns export:
   ```bash
   python ai-gen/gui4gmns.py path/to/your_gmns_folder      # -> your_gmns_folder/dashboard.html
   python exporters/gmns_to_viz.py path/to/your_gmns_folder --target all
   ```
2. **Modify the HTML.** The offline dashboards and viewers are single files with inline JS — open one, find
   the `DATA = {...}` block and the render functions, change colors/thresholds/labels, reload. No build step.
3. **Bring your own MOE.** Add a `link_performance.csv` (speed/volume/queue) and the dashboard colors by
   observed data; add a `trajectory.csv` and the animation and Trip/Trips portals light up.
4. **Compare portals.** Run `--target all` on one network and open it in Kepler, deck.gl, Google Earth, and
   QGIS side by side — same data, four lenses. Good semester project: add a fifth portal exporter.

## Where the flagship fits

**ITS I-95 (VA)** is the reference for the *whole* pipeline — one corridor fusing GMNS network + speeds +
sensors + probe trajectories + OD, exported outward to every portal above. Its **data is restricted** (INRIX
/ VDOT / probe — see [DATASETS_COVERAGE](DATASETS_COVERAGE.md)) so it runs **locally only**; the **outbound
exports are identical for any public GMNS folder**, so Chicago Sketch or your own network demonstrates the
same portal connections end to end.

See also: [gallery](gallery.html) · [DATASETS_COVERAGE](DATASETS_COVERAGE.md) · `exporters/README.md` ·
`ai-gen/VIZ_SCHEMA.md` (build your own portal, AI-guided).

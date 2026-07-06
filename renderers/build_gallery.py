#!/usr/bin/env python3
"""Build docs/gallery.html — a self-contained index of the pre-generated figures + demo dashboards.

Scans the committed figure folders and datasets, emits one browsable gallery page (relative image
links). Run after regenerating figures. Usage: python build_gallery.py [-o docs/gallery.html]
"""
import os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DOCS = os.path.join(ROOT, "docs")

# The interactive HTML dashboards are the BASE product; plot4gmns static figures are ADDITIONAL.
SECTIONS = [
    ("Additional: plot4gmns static figures", "p4g_native_gallery",
     "Supplementary static images — the plot4gmns catalog reimplemented natively (no pandas/Shapely/"
     "keplergl): network nodes/links/zones/POI, by-attribute, distributions, demand matrix + OD, lanes, movements."),
    ("Additional: MOE & analytics figures (report-ready)", "moe_gallery",
     "Traffic-Speed bandwidth, space-time speed/density contours, corridor profiles, PeMS/RITIS bottleneck "
     "ranking, global city-store coverage. Intuitive green(fast)->red(slow)."),
]

def imgs(folder):
    d = os.path.join(DOCS, folder)
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, "*.png")))

def dashboards():
    d = os.path.join(DOCS, "dashboards")
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, "*.html")))

def datasets():
    dd = os.path.join(ROOT, "datasets")
    out = []
    for name in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
        p = os.path.join(dd, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "link.csv")):
            out.append(name)
    return out

PRETTY = {
    "01_sioux_falls": "Sioux Falls (classic test network)",
    "02_chicago_sketch": "Chicago Sketch (regional demand)",
    "05_toy_bottleneck": "Toy — bottleneck", "05_toy_merge": "Toy — merge", "05_toy_signal": "Toy — signal",
    "07_west_jordan": "West Jordan, UT (real corridor)",
}

def main():
    a = sys.argv[1:]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(DOCS, "gallery.html")

    # BASE section: the interactive HTML dashboards, gathered into one folder, directly clickable.
    dbs = dashboards()
    db_cards = "".join(
        f'<figure class="db"><a href="dashboards/{n}" target="_blank">'
        f'<div class="dbthumb">&#128506;<span>open dashboard</span></div></a>'
        f'<figcaption>{PRETTY.get(n[:-5], n[:-5].replace("_"," "))}</figcaption></figure>' for n in dbs)
    base = (f'<section><h2>Interactive dashboards &mdash; the base <span class="tag">HTML</span></h2>'
            f'<p class="desc">Self-contained offline dashboards (data + basemap embedded), all in one folder '
            f'(<code>docs/dashboards/</code>) so you can browse them by clicking. This is gui4gmns\'s primary '
            f'output. Rebuild any time with <code>python renderers/build_dashboards.py</code>; large networks '
            f'(ARC, Chicago Regional) are generate-on-demand.</p>'
            f'<div class="grid">{db_cards}</div></section>') if dbs else ""

    # ADDITIONAL sections: plot4gmns + MOE static figures.
    cards = ""
    for title, folder, desc in SECTIONS:
        names = imgs(folder)
        if not names: continue
        thumbs = "".join(
            f'<figure><a href="{folder}/{n}" target="_blank"><img src="{folder}/{n}" loading="lazy"></a>'
            f'<figcaption>{n.replace(".png","").replace("_"," ")}</figcaption></figure>' for n in names)
        cards += f'<section><h2>{title} <span class="tag alt">static</span></h2><p class="desc">{desc}</p><div class="grid">{thumbs}</div></section>'
    ds = datasets()
    ds_rows = "".join(f'<li><b>{n}</b> — <code>python ai-gen/gui4gmns.py datasets/{n}</code> '
                      f'-&gt; <code>datasets/{n}/dashboard.html</code> + <code>figures/</code></li>' for n in ds)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>gui4gmns gallery</title>
<style>
 body{{font:14px/1.5 system-ui,Segoe UI,Arial;margin:0;color:#222;background:#fafafa}}
 header{{background:#1d232b;color:#e6edf3;padding:18px 26px}}
 header h1{{margin:0;font-size:20px}} header h1 span{{color:#58a6ff}}
 header p{{margin:4px 0 0;color:#9aa7bd;font-size:13px}}
 main{{max-width:1200px;margin:0 auto;padding:20px 26px}}
 section{{margin:26px 0}} h2{{border-bottom:2px solid #eee;padding-bottom:6px}}
 .tag{{font-size:11px;font-weight:600;color:#fff;background:#2563eb;border-radius:10px;padding:2px 9px;vertical-align:middle}}
 .tag.alt{{background:#8a8f98}}
 .desc{{color:#555;margin:-4px 0 12px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}}
 figure{{margin:0;background:#fff;border:1px solid #e5e5e5;border-radius:8px;overflow:hidden}}
 figure img{{width:100%;display:block;background:#fff}}
 figure.db a{{text-decoration:none}}
 .dbthumb{{height:140px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;
   font-size:44px;color:#2563eb;background:linear-gradient(135deg,#eef3ff,#dfe8ff);border-bottom:1px solid #d6e0f5}}
 .dbthumb span{{font-size:12px;color:#2563eb;font-weight:600}}
 figcaption{{padding:6px 8px;font-size:11.5px;color:#444;border-top:1px solid #eee}}
 ul{{line-height:1.9}} code{{background:#eef;padding:1px 5px;border-radius:3px;font-size:12px}}
</style></head><body>
<header><h1><span>gui4gmns</span> gallery</h1>
<p>HTML dashboards are the base (interactive, one folder); plot4gmns &amp; MOE figures are additional static images.</p></header>
<main>{base}{cards}
<section><h2>Generate for any dataset ({len(ds)} demos)</h2>
<p class="desc">Every dataset produces a self-contained dashboard (base) + a static figure set (additional):</p>
<ul>{ds_rows}</ul></section>
<section><h2>Docs</h2><ul>
<li><a href="PACKAGE.md">PACKAGE.md</a> — package overview &amp; review checklist</li>
<li><a href="DATASETS_COVERAGE.md">DATASETS_COVERAGE.md</a> — flagship + partial-coverage matrix</li>
<li><a href="TRB_VIZ_REVIEW.md">TRB viz review</a> · <a href="STAKEHOLDER_REVIEW.md">stakeholder review</a> · <a href="ROADMAP.md">roadmap</a></li>
</ul></section></main></body></html>"""
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(dbs)} dashboards, {sum(len(imgs(f)) for _, f, _ in SECTIONS)} figures, {len(ds)} datasets)")

if __name__ == "__main__":
    main()

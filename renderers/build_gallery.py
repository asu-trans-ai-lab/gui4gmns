#!/usr/bin/env python3
"""Build docs/gallery.html — a self-contained index of the pre-generated figures + demo dashboards.

Scans the committed figure folders and datasets, emits one browsable gallery page (relative image
links). Run after regenerating figures. Usage: python build_gallery.py [-o docs/gallery.html]
"""
import os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DOCS = os.path.join(ROOT, "docs")

SECTIONS = [
    ("MOE gallery — static, report-ready (matplotlib)", "moe_gallery",
     "Traffic-Speed bandwidth, space-time speed/density contours, corridor profiles, bottleneck ranking, "
     "global city-store coverage. Colors: intuitive green(fast)->red(slow) by default."),
    ("plot4gmns native figures", "p4g_native_gallery",
     "The plot4gmns figure catalog reimplemented natively (no pandas/Shapely/keplergl): network nodes/"
     "links/zones/POI, by-attribute, distributions, demand matrix + OD desire lines, lanes, movements."),
]

def imgs(folder):
    d = os.path.join(DOCS, folder)
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, "*.png")))

def datasets():
    dd = os.path.join(ROOT, "datasets")
    out = []
    for name in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
        p = os.path.join(dd, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "link.csv")):
            out.append(name)
    return out

def main():
    a = sys.argv[1:]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(DOCS, "gallery.html")
    cards = ""
    for title, folder, desc in SECTIONS:
        names = imgs(folder)
        if not names: continue
        thumbs = "".join(
            f'<figure><a href="{folder}/{n}" target="_blank"><img src="{folder}/{n}" loading="lazy"></a>'
            f'<figcaption>{n.replace(".png","").replace("_"," ")}</figcaption></figure>' for n in names)
        cards += f'<section><h2>{title}</h2><p class="desc">{desc}</p><div class="grid">{thumbs}</div></section>'
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
 .desc{{color:#555;margin:-4px 0 12px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}}
 figure{{margin:0;background:#fff;border:1px solid #e5e5e5;border-radius:8px;overflow:hidden}}
 figure img{{width:100%;display:block;background:#fff}}
 figcaption{{padding:6px 8px;font-size:11.5px;color:#444;border-top:1px solid #eee}}
 ul{{line-height:1.9}} code{{background:#eef;padding:1px 5px;border-radius:3px;font-size:12px}}
</style></head><body>
<header><h1><span>gui4gmns</span> gallery — pre-generated figures &amp; dashboards</h1>
<p>Static figures are committed; interactive dashboards are generated per dataset (below).</p></header>
<main>{cards}
<section><h2>Interactive dashboards ({len(ds)} demo datasets)</h2>
<p class="desc">Each generates a self-contained offline dashboard + a static figure set:</p>
<ul>{ds_rows}</ul></section>
<section><h2>Docs</h2><ul>
<li><a href="PACKAGE.md">PACKAGE.md</a> — package overview &amp; review checklist</li>
<li><a href="DATASETS_COVERAGE.md">DATASETS_COVERAGE.md</a> — flagship + partial-coverage matrix</li>
<li><a href="TRB_VIZ_REVIEW.md">TRB viz review</a> · <a href="STAKEHOLDER_REVIEW.md">stakeholder review</a> · <a href="ROADMAP.md">roadmap</a></li>
</ul></section></main></body></html>"""
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({sum(len(imgs(f)) for _, f, _ in SECTIONS)} figures, {len(ds)} datasets)")

if __name__ == "__main__":
    main()

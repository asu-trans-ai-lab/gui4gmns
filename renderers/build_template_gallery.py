#!/usr/bin/env python3
"""Build docs/templates/index.html — a catalog-driven gallery of the public dashboard TEMPLATES.

Dataset-first, not dashboard-first: each card is driven by the dataset catalog (category, capabilities,
required files, QA contract) and links to the live template. Restricted templates (i17/CBI, NVTA) are
excluded by construction (they live outside docs/templates/). Run: python build_template_gallery.py
"""
import os, glob, json
import html as H

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
GAL = os.path.join(ROOT, "docs", "templates")

CAT = json.load(open(os.path.join(ROOT, "templates", "catalog", "dataset_catalog.json"), encoding="utf-8"))
BY_TMPL = {os.path.basename(d.get("template_file", "")): d for d in CAT["datasets"]}

# category -> (label, color). First-level tabs of the intelligent GUI.
CATS = {
    "regional_inventory":       ("Regional / signal inventory", "#2f9e5e"),
    "signal_intersection_ops":  ("Signal / intersection ops", "#2563eb"),
    "corridor_simulation":      ("Corridor simulation", "#b8562a"),
    "multimodal_digital_twin":  ("Multimodal digital twin", "#7c3aed"),
    "odme_calibration":         ("ODME calibration", "#0891b2"),
    "highway_sensor_timeseries":("Highway sensor / ITS data hub", "#dc2626"),
    "rail_freight_network":     ("Rail / freight", "#4b5563"),
    "teaching_problem":         ("Teaching", "#ca8a04"),
}
# templates that have no catalog entry -> (display, category)
EXTRA = {
    "ASU_intersection_cv_dashboard.html": ("ASU intersection — CV trajectory / turning movement", "signal_intersection_ops"),
    "ASU_intersection_dashboard.html":    ("ASU intersection — signal ops", "signal_intersection_ops"),
    "gmns_dashboard_03_corridor_simulation.html": ("Corridor simulation (queue / capacity / delay)", "corridor_simulation"),
    "gtfs_digital_twin_dashboard.html":   ("GTFS rail/transit digital twin", "multimodal_digital_twin"),
}

def chips(items, cls):
    return "".join(f'<span class="{cls}">{H.escape(str(i))}</span>' for i in (items or []))

def card(fn, href):
    d = BY_TMPL.get(os.path.basename(fn))
    cat = (d or {}).get("category") or EXTRA.get(fn, ("", "regional_inventory"))[1]
    label, color = CATS.get(cat, (cat, "#6b7280"))
    title = (d or {}).get("display_name") or EXTRA.get(fn, (fn.replace("_", " ").replace(".html", ""), ""))[0]
    caps = chips((d or {}).get("capabilities", [])[:6], "cap")
    req = chips((d or {}).get("required_files", []), "req")
    qa = chips((d or {}).get("qa_contract", [])[:6], "qa")
    body = ""
    if req: body += f'<div class="row"><b>needs</b> {req}</div>'
    if caps: body += f'<div class="row"><b>shows</b> {caps}</div>'
    if qa: body += f'<div class="row"><b>QA gate</b> {qa}</div>'
    return (cat, f'<figure><a href="{href}" target="_blank"><div class="thumb" style="--c:{color}">'
            f'<span>open template</span></div></a><figcaption><span class="tag" style="background:{color}">{label}</span>'
            f'<b>{H.escape(title)}</b>{body}</figcaption></figure>')

def main():
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(GAL, "*.html"))
                   if os.path.basename(p) != "index.html")
    cards = [card(fn, fn) for fn in files]
    # I-95 flagship: the live data hub (not a static template file here)
    cards.append(card("adapters/its_datahub.py", "../portal_demo/i95/datahub.html"))
    groups = {}
    for cat, htmlc in cards:
        groups.setdefault(cat, []).append(htmlc)
    order = list(CATS.keys())
    secs = ""
    for cat in sorted(groups, key=lambda c: order.index(c) if c in order else 99):
        label = CATS.get(cat, (cat, ""))[0]
        secs += f'<section><h2>{label}</h2><div class="grid">{"".join(groups[cat])}</div></section>'
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>gui4gmns — dashboard template gallery</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
 body{{font:14px/1.55 system-ui,Segoe UI,Arial;margin:0;color:#1d232b;background:#fafafa}}
 header{{background:#1d232b;color:#e6edf3;padding:18px 26px}} header h1{{margin:0;font-size:21px}} header h1 span{{color:#58a6ff}}
 header p{{margin:5px 0 0;color:#9aa7bd;font-size:13px;max-width:900px}}
 main{{max-width:1200px;margin:0 auto;padding:18px 26px}} section{{margin:22px 0}}
 h2{{font-size:16px;border-bottom:2px solid #eee;padding-bottom:6px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
 figure{{margin:0;background:#fff;border:1px solid #e5e5e5;border-radius:9px;overflow:hidden}}
 figure a{{text-decoration:none}}
 .thumb{{height:78px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--c) 12%,#fff);border-bottom:1px solid #eee}}
 .thumb span{{color:var(--c);font-weight:700;font-size:13px}}
 figcaption{{padding:10px 12px}} figcaption b{{display:block;font-size:13.5px;margin:5px 0 3px;color:#1d232b}}
 .tag{{font-size:10.5px;font-weight:600;color:#fff;border-radius:9px;padding:2px 8px}}
 .row{{font-size:11.5px;color:#555;margin:4px 0}} .row b{{color:#333}}
 .cap,.req,.qa{{display:inline-block;font-size:10.5px;border-radius:4px;padding:1px 6px;margin:2px 3px 0 0}}
 .cap{{background:#eef3ff;color:#1b4bb3}} .req{{background:#eef7f0;color:#1c6b3f;font-family:monospace}} .qa{{background:#fef3e8;color:#8a4b13}}
 code{{background:#eef;padding:1px 5px;border-radius:3px}}
</style></head><body>
<header><h1><span>gui4gmns</span> dashboard template gallery</h1>
<p>Dataset-first, dashboard-second. Each template is driven by a <b>dataset catalog</b> entry — category,
what it needs, what it shows, and the <b>QA gate</b> it must pass. See
<a href="../GMNS_TO_DASHBOARD_SKILL.md" style="color:#58a6ff">GMNS_TO_DASHBOARD_SKILL.md</a> for how to convert
any GMNS folder (package + LLM) into one of these.</p></header>
<main>{secs}</main></body></html>"""
    open(os.path.join(GAL, "index.html"), "w", encoding="utf-8").write(page)
    json.dump(CAT, open(os.path.join(GAL, "catalog.json"), "w", encoding="utf-8"), indent=1)
    print(f"wrote docs/templates/index.html ({len(cards)} templates, {len(groups)} categories)")

if __name__ == "__main__":
    main()

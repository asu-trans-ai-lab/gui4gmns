#!/usr/bin/env python3
"""Build all demo dashboards into ONE browsable folder (docs/dashboards/).

The interactive HTML dashboard is gui4gmns's BASE output; plot4gmns static figures are additional.
This generates a SINGLE-FILE (self-contained, no sidecar layers) dashboard per public dataset into one
folder, named by dataset, so you can browse them by opening the folder or docs/gallery.html.

Usage: python build_dashboards.py [-o docs/dashboards] [--max-mb 6]   (skips datasets whose single-file
       dashboard would exceed --max-mb, e.g. ARC 145k links; those stay generate-on-demand.)
"""
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

def load_generator():
    fp = os.path.join(ROOT, "ai-gen", "gui4gmns.py")
    spec = importlib.util.spec_from_file_location("gui4gmns", fp)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def main():
    a = sys.argv[1:]
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(ROOT, "docs", "dashboards")
    max_mb = float(a[a.index("--max-mb") + 1]) if "--max-mb" in a else 6.0
    os.makedirs(out, exist_ok=True)
    gen = load_generator()
    dd = os.path.join(ROOT, "datasets")
    made, skipped = [], []
    for name in sorted(os.listdir(dd)):
        p = os.path.join(dd, name)
        if not (os.path.isdir(p) and os.path.exists(os.path.join(p, "link.csv"))): continue
        if "PRIVATE" in name.upper(): continue                     # never bundle private data
        target = os.path.join(out, name + ".html")
        try:
            gen.generate(p, out=target, split=False, figures=False)  # single-file, self-contained
            mb = os.path.getsize(target) / 1e6
            if mb > max_mb:
                os.remove(target); skipped.append((name, mb)); print(f"  skip {name} ({mb:.1f} MB > {max_mb})")
            else:
                made.append((name, mb)); print(f"  ok   {name}.html ({mb:.1f} MB)")
        except Exception as e:
            print(f"  --   {name}: {type(e).__name__}: {str(e)[:50]}")
    print(f"\n{len(made)} dashboards -> {out}/  ({sum(m for _, m in made):.1f} MB total)")
    if skipped:
        print("generate-on-demand (too big to bundle): " + ", ".join(f"{n} {m:.0f}MB" for n, m in skipped))

if __name__ == "__main__":
    main()

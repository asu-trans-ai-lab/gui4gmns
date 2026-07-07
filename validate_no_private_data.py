#!/usr/bin/env python3
"""Pre-commit privacy gate for gui4gmns. Fails if any git-tracked file looks like agency data.
Run:  python validate_no_private_data.py    (exit 0 = clean, 1 = private data staged)"""
import os, subprocess, sys, re

BLOCK_NAME = re.compile(r"(private|nvta|vdot|inrix|cbi|tmc|p4p|ritis|screenline)", re.I)
BLOCK_PATH = ["06_nvta", "data_private", "dashboard_layers"]
# High-signal markers of EMBEDDED restricted data / private-path coupling — screens CONTENT, not just the
# filename (i17_dashboard.html slipped the name check but embeds I-17 CBI data). Deliberately specific so
# UI labels ("INRIX observed"), design credits ("PeMS/RITIS"), supported schema columns ("speed_inrix"),
# and base64 tile noise do NOT trip it.
CONTENT_BLOCK = re.compile(r"(CBI Dashboard|I-17 CBI|06_nvta|nvta_am_PRIVATE|08_Phoenix_MAG|MAG regional|MAG model)", re.I)
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".pptx", ".xlsx",
              ".zip", ".whl", ".gz", ".tar", ".woff", ".woff2", ".ttf")
SIZE_WARN_MB = 5.0   # roadmap B4 size gate: flag any tracked file larger than this

def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    except Exception as e:
        print("not a git repo yet (nothing tracked):", e); return []
    return [l for l in out.splitlines() if l.strip()]

SELF_OK = {"validate_no_private_data.py", ".gitignore"}   # both legitimately name the private paths they screen/exclude
# Owner-cleared public despite matching a block token (fully exempt from name + content screening). The
# "_tmc" viewers/playbook match the BLOCK_NAME token "tmc" only because TMC = Traffic Management Center (the
# domain term), NOT the private TMC probe feed — they are built solely from vetted public sources: Caltrans
# PeMS (i405n), the cleared USDOT JPO CodeHub ITS I-95 sample (i95), and a synthetic test network (chicago).
ALLOW = ("datasets/08_public_ITS_VA_1-95_sample/",
         "docs/3D_TMC_PLAYBOOK.md",
         "docs/portal_demo/i95_tmc/",
         "docs/portal_demo/chicago_tmc/",
         "docs/portal_demo/i405n_tmc/")
def _allowed(f): return any(f.startswith(p) for p in ALLOW)

def content_hits(files):
    """Files whose CONTENT embeds restricted data / private-path coupling (not just a private filename)."""
    out = []
    for f in files:
        if f in SELF_OK or _allowed(f) or f.lower().endswith(BINARY_EXT) or not os.path.exists(f):
            continue
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                if CONTENT_BLOCK.search(fh.read()):
                    out.append(f)
        except OSError:
            pass
    return out

def main():
    files = tracked()
    bad = [f for f in files
           if f not in SELF_OK and not _allowed(f) and (BLOCK_NAME.search(f) or any(b in f for b in BLOCK_PATH))]
    for f in content_hits(files):
        if f not in bad:
            bad.append(f)
    big = [(f, os.path.getsize(f) / 1e6) for f in files
           if os.path.exists(f) and os.path.getsize(f) > SIZE_WARN_MB * 1e6]
    print(f"tracked files: {len(files)}")
    if big:
        print(f"\n(size gate) {len(big)} tracked file(s) > {SIZE_WARN_MB:.0f} MB — keep raw/large data out of the repo:")
        for f, mb in sorted(big, key=lambda x: -x[1]): print(f"    {mb:6.1f} MB  {f}")
    if bad:
        print(f"\n!! {len(bad)} PRIVATE-looking file(s) tracked — DO NOT COMMIT/PUSH:")
        for f in bad: print("   ", f)
        sys.exit(1)
    print("clean: no private-looking files tracked.")
    sys.exit(0)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pre-commit privacy gate for gui4gmns. Fails if any git-tracked file looks like agency data.
Run:  python validate_no_private_data.py    (exit 0 = clean, 1 = private data staged)"""
import subprocess, sys, re

BLOCK_NAME = re.compile(r"(private|nvta|vdot|inrix|cbi|tmc|p4p|ritis|screenline)", re.I)
BLOCK_PATH = ["06_nvta", "data_private", "dashboard_layers"]

def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    except Exception as e:
        print("not a git repo yet (nothing tracked):", e); return []
    return [l for l in out.splitlines() if l.strip()]

def main():
    files = tracked()
    bad = [f for f in files if BLOCK_NAME.search(f) or any(b in f for b in BLOCK_PATH)]
    print(f"tracked files: {len(files)}")
    if bad:
        print(f"\n!! {len(bad)} PRIVATE-looking file(s) tracked — DO NOT COMMIT/PUSH:")
        for f in bad: print("   ", f)
        sys.exit(1)
    print("clean: no private-looking files tracked.")
    sys.exit(0)

if __name__ == "__main__":
    main()

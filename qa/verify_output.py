#!/usr/bin/env python3
"""verify_output.py — machine-invariant harness for a generated gui4gmns dashboard (qa/TEST_PLAN.md
method M-A). Point it at a GMNS folder that has already been generated (dashboard.html + dashboard_layers/
+ portals/ [+ figures/]); it re-reads the source CSVs, parses the generated output, and prints PASS /
FAIL / NA + a reason for every machine-checkable correctness dimension (D1, D2, D3, D7, D8).

It answers the developer lens ("did it produce the artifacts?") AND the machine-checkable half of the
user lens ("does the picture match the data, is nothing claimed empty, are the claims honest?"). The
subjective half (legend aesthetics, geographic/temporal plausibility) is left to human review (M-E).

Usage:  python qa/verify_output.py <gmns_folder> [--min-coverage 0.03]
Exit 0 if no FAIL, 1 otherwise.
"""
import csv, json, os, re, sys

def fnum(v):
    try: return float(v)
    except: return 0.0

def rd(folder, name):
    p = os.path.join(folder, name)
    if not os.path.exists(p): return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def load_layer(folder, key):
    """Return the parsed NX.<key> object from dashboard_layers/<file>.js, or None if absent/empty."""
    fmap = {"network": "network", "moe": "moe", "td": "td", "trajs": "trajectories",
            "corridor": "corridor", "demand": "demand", "run": "run"}
    p = os.path.join(folder, "dashboard_layers", fmap[key] + ".js")
    if not os.path.exists(p): return None
    js = open(p, encoding="utf-8").read()
    tok = f"NX.{key}="
    if tok not in js: return None
    s = js[js.index(tok) + len(tok):]
    s = s[:s.rindex("}") + 1] if "}" in s else s
    try: return json.loads(s)
    except Exception: return None

class Report:
    def __init__(self): self.rows = []
    def add(self, dim, name, status, msg):
        self.rows.append((dim, name, status, msg))
    def render(self):
        print()
        for dim, name, status, msg in self.rows:
            print(f"  [{dim:>6}] {name:<26} {status:<4}  {msg}")
        npass = sum(1 for r in self.rows if r[2] == "PASS")
        nfail = sum(1 for r in self.rows if r[2] == "FAIL")
        nna = sum(1 for r in self.rows if r[2] == "NA")
        nwarn = sum(1 for r in self.rows if r[2] == "WARN")
        print(f"\n  {npass} pass, {nfail} fail, {nwarn} warn, {nna} n/a")
        return nfail

EXTERNAL_OK = re.compile(r"openstreetmap|creativecommons|w3\.org|schema\.org|example\.com", re.I)

def verify(folder, min_cov=0.03):
    R = Report()
    print(f"gui4gmns output verification — {folder}")
    nodes_csv = rd(folder, "node.csv"); links_csv = rd(folder, "link.csv")
    if not nodes_csv or not links_csv:
        print("  ERROR: node.csv / link.csv not found — is this a GMNS folder?"); return 1
    net = load_layer(folder, "network")
    if net is None:
        R.add("D2", "dashboard generated", "FAIL", "no dashboard_layers/network.js — run the generator first")
        return R.render() or 1

    # D1 topology fidelity: drawn counts == source counts (minus links with no resolvable geometry)
    nn, nl = len(net.get("nodes", [])), len(net.get("links", []))
    cn, cl = len(nodes_csv), len(links_csv)
    if nn == cn and nl == cl:
        R.add("D1", "topology fidelity", "PASS", f"{nn} nodes / {nl} links == node.csv/link.csv")
    elif nl <= cl and nn <= cn:
        R.add("D1", "topology fidelity", "WARN", f"drawn {nn}/{nl} vs csv {cn}/{cl} (some skipped — check WARN in gen log)")
    else:
        R.add("D1", "topology fidelity", "FAIL", f"drawn {nn}/{nl} exceeds csv {cn}/{cl}")

    # D1/D4 MOE value fidelity: sampled link volumes in the moe layer match link_performance
    perf = rd(folder, "link_performance.csv")
    moe = load_layer(folder, "moe")
    if not perf:
        R.add("D1/D4", "MOE value fidelity", "NA", "no link_performance.csv (network-only)")
    elif not moe:
        R.add("D2", "MOE layer present", "FAIL", "link_performance.csv present but moe layer empty/missing")
    else:
        vc = "cum_departure" if "cum_departure" in perf[0] else "volume"
        checked = ok = 0
        for r in perf[:2000]:
            lid = str(int(fnum(r.get("link_id") or 0)))
            if lid in moe:
                checked += 1
                if abs(fnum(moe[lid][0]) - round(fnum(r.get(vc)), 1)) <= 1.0: ok += 1
                if checked >= 5: break
        R.add("D1/D4", "MOE value fidelity", "PASS" if ok == checked and checked else "FAIL",
              f"{ok}/{checked} sampled links match link_performance ({vc})")

    # D2 layer completeness: every input that should light a layer does. NOTE: td.js/demand.js are
    # ALWAYS written with a non-empty wrapper dict (e.g. td={"bins":[],"td":{}}, demand's "dist"
    # histograms come from link attributes regardless of demand.csv) — checking top-level truthiness
    # would call an empty layer "present". Check the specific sub-key that carries the actual content.
    def present(name): return os.path.exists(os.path.join(folder, name))
    td = load_layer(folder, "td"); trajs = load_layer(folder, "trajs")
    corridor = load_layer(folder, "corridor"); demand = load_layer(folder, "demand")
    td_real = bool((td or {}).get("td"))
    demand_real = bool((demand or {}).get("demand"))
    miss = []
    if present("link_performance_15min.csv") and not td_real: miss.append("td (has 15min)")
    if (present("agent_trajectory.csv") or (present("path_flow.csv") and present("link_performance_15min.csv"))) and not (trajs and len(trajs)):
        miss.append("trajs (has trajectory/path source)")
    if present("corridor_speed.csv") and not (corridor and len(corridor)): miss.append("corridor (has corridor_speed)")
    if present("demand.csv") and not demand_real: miss.append("demand (has demand.csv)")
    have = [k for k, v in [("network", net), ("moe", moe), ("td", td_real), ("trajs", trajs), ("demand", demand_real)] if v]
    if miss:
        R.add("D2", "layer completeness", "FAIL", "expected but empty: " + ", ".join(miss))
    else:
        na = "" if present("corridor_speed.csv") else "; corridor n/a (no corridor_speed.csv)"
        R.add("D2", "layer completeness", "PASS", "present: " + ",".join(have) + na)

    # D2/D3 animation: representative & network-covering (catches F-008 clustering + F-009 sparsity)
    if not trajs:
        R.add("D2/D3", "animation coverage", "NA", "no vehicle trajectories for this dataset")
    else:
        tl = set()
        for ev in trajs.values():
            for e in ev: tl.add(e[1])
        cov = len(tl) / max(1, nl)
        tj = rd(folder, "agent_trajectory.csv")
        spread_ok = True; span_txt = ""
        if tj:
            allids = sorted({int(fnum(r["agent_id"])) for r in tj})
            kept = sorted(int(a) for a in trajs)
            full = (allids[-1] - allids[0]) or 1
            span = (kept[-1] - kept[0]) / full
            spread_ok = span >= 0.5   # a lowest-id-cluster bug (F-008) would span ~0.07
            span_txt = f", id span {span*100:.0f}% of range"
        status = "PASS" if (cov >= min_cov and spread_ok) else "FAIL"
        R.add("D2/D3", "animation coverage", status,
              f"{len(trajs)} agents, {len(tl)}/{nl} links ({cov*100:.0f}%){span_txt}"
              + ("" if spread_ok else " — SAMPLE CLUSTERED, not representative"))

    # D8 offline honesty: no external requests in the dashboard or any layer
    ext = set()
    scan = [os.path.join(folder, "dashboard.html")]
    ld = os.path.join(folder, "dashboard_layers")
    if os.path.isdir(ld): scan += [os.path.join(ld, f) for f in os.listdir(ld) if f.endswith(".js")]
    for p in scan:
        if not os.path.exists(p): continue
        for m in re.findall(r"https?://[^\s\"'<>)]+", open(p, encoding="utf-8", errors="ignore").read()):
            if not EXTERNAL_OK.search(m): ext.add(m[:60])
    if not os.path.exists(os.path.join(folder, "dashboard.html")):
        R.add("D8", "offline honesty", "WARN", "dashboard.html not found (only layers checked)")
    elif ext:
        R.add("D8", "offline honesty", "FAIL", f"{len(ext)} external ref(s), e.g. {sorted(ext)[0]}")
    else:
        R.add("D8", "offline honesty", "PASS", f"no external requests across {len(scan)} file(s)")

    # D2 portal completeness: all four written and non-empty
    pd = os.path.join(folder, "portals")
    if not os.path.isdir(pd):
        R.add("D2", "portals completeness", "FAIL", "no portals/ folder (auto-export missing)")
    else:
        empty = [k for k in ("kepler", "deckgl", "qgis", "kml")
                 if not (os.path.isdir(os.path.join(pd, k)) and os.listdir(os.path.join(pd, k)))]
        R.add("D2", "portals completeness", "FAIL" if empty else "PASS",
              ("missing/empty: " + ",".join(empty)) if empty else "kepler,deckgl,qgis,kml all populated")

    # D7 figure honesty: figures exist, none zero-byte (silent-failure guard from F-010)
    fd = os.path.join(folder, "figures")
    if not os.path.isdir(fd):
        R.add("D7", "figure honesty", "NA", "no figures/ (matplotlib not installed?)")
    else:
        pngs = [f for f in os.listdir(fd) if f.endswith(".png")]
        zero = [f for f in pngs if os.path.getsize(os.path.join(fd, f)) == 0]
        if not pngs:
            R.add("D7", "figure honesty", "FAIL", "figures/ exists but no PNG written")
        elif zero:
            R.add("D7", "figure honesty", "FAIL", f"{len(zero)} zero-byte figure(s): {zero[0]}")
        else:
            R.add("D7", "figure honesty", "PASS", f"{len(pngs)} figures, none empty")

    # M-D golden reference: if the folder ships EXPECTED.json (a fixture), assert exact hand-computed
    # values — this is what a tiny fixture buys over a big showcase: "== 2.0", not "looks about right".
    exp_p = os.path.join(folder, "EXPECTED.json")
    if os.path.exists(exp_p):
        verify_golden(json.load(open(exp_p, encoding="utf-8")), net, moe, load_layer(folder, "corridor"), trajs, R,
                       os.path.join(folder, "figures"))

    return R.render()

def _pos_at(events, t):
    """Replicate the dashboard's linear interpolation: (link_id, fraction) of an agent at clock t."""
    ev = sorted(events)
    if not ev or t < ev[0][0] or t > ev[-1][0]: return (None, None)
    i = 0
    while i + 1 < len(ev) and ev[i + 1][0] <= t: i += 1
    lid = ev[i][1]
    if i + 1 < len(ev) and ev[i + 1][0] > ev[i][0]:
        return (lid, (t - ev[i][0]) / (ev[i + 1][0] - ev[i][0]))
    return (lid, 0.0)

def verify_golden(exp, net, moe, corridor, trajs, R, figures_dir=None):
    def near(a, b, tol=1e-6): return abs(a - b) <= tol

    if "nodes" in exp and "links" in exp:
        ok = len(net.get("nodes", [])) == exp["nodes"] and len(net.get("links", [])) == exp["links"]
        R.add("M-D", "golden topology", "PASS" if ok else "FAIL",
              f"{len(net.get('nodes',[]))}/{len(net.get('links',[]))} vs expected {exp['nodes']}/{exp['links']}")

    if exp.get("reprojected_nodes"):
        by_id = {str(n[0]): (n[1], n[2]) for n in net.get("nodes", [])}
        bad = []
        for nid, (elon, elat) in exp["reprojected_nodes"].items():
            got = by_id.get(nid)
            if not got or not (near(got[0], elon, 1e-4) and near(got[1], elat, 1e-4)):
                bad.append(f"node {nid}: got {got}, want [{elon},{elat}]")
        R.add("M-D", "golden CRS reprojection", "FAIL" if bad else "PASS",
              (bad[0]) if bad else f"{len(exp['reprojected_nodes'])} node coords match exactly (D9 geographic)")

    if exp.get("required_figures"):
        missing = []
        for fn in exp["required_figures"]:
            p = os.path.join(figures_dir or "", fn)
            if not os.path.exists(p) or os.path.getsize(p) == 0: missing.append(fn)
        R.add("M-D", "golden required figures", "FAIL" if missing else "PASS",
              ("missing/empty: " + ",".join(missing)) if missing else f"{len(exp['required_figures'])} required figures present")

    if exp.get("moe_volume"):
        if not moe:
            R.add("M-D", "golden MOE volume", "FAIL", "moe layer missing")
        else:
            bad = [k for k, v in exp["moe_volume"].items() if k not in moe or not near(fnum(moe[k][0]), v, 0.5)]
            R.add("M-D", "golden MOE volume", "FAIL" if bad else "PASS",
                  (f"mismatch at link {bad[0]}") if bad else f"{len(exp['moe_volume'])} link volumes exact")

    if exp.get("corridor"):
        cv = (corridor or {})
        bad = []
        for name, want in exp["corridor"].items():
            got = (cv.get(name) or {}).get("val") or {}
            for k in ("n", "rmse", "r2", "bias"):
                if k in want and not near(fnum(got.get(k, -999)), want[k], 0.01): bad.append(f"{name}.{k}")
        R.add("M-D", "golden corridor stats", "FAIL" if bad else "PASS",
              ("mismatch: " + ",".join(bad)) if bad else "RMSE/R2/bias/n all exact")

    if exp.get("traj_frames"):
        bad = []
        for fr in exp["traj_frames"]:
            ev = (trajs or {}).get(str(fr["agent"])) or (trajs or {}).get(fr["agent"])
            if not ev: bad.append(f"a{fr['agent']}(no trajectory)"); continue
            lid, frac = _pos_at(ev, fr["t"])
            if lid != fr["link"] or frac is None or not near(frac, fr["frac"], 0.01):
                bad.append(f"a{fr['agent']}@t{fr['t']}->L{lid}@{frac}")
        R.add("M-D", "golden traj frames", "FAIL" if bad else "PASS",
              ("mismatch: " + bad[0]) if bad else f"{len(exp['traj_frames'])} frame positions exact")

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    folder = a[0]
    mc = float(a[a.index("--min-coverage") + 1]) if "--min-coverage" in a else 0.03
    nfail = verify(folder, mc)
    sys.exit(1 if nfail else 0)

if __name__ == "__main__":
    main()

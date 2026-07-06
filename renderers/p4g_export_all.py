#!/usr/bin/env python3
"""Export ALL plot4gmns figures for a demo GMNS network — using the real plot4gmns engine.

Adopts plot4gmns (github_dev/plot4gmns-main) into gui4gmns: rather than re-deriving its views, we call
its actual `pg.show_*` functions and save every figure. keplergl (only used by its interactive map) is
stubbed so the matplotlib figure set imports without that heavy dependency.

Usage: python p4g_export_all.py [demo_dir] [-o out_dir]
   default demo_dir = plot4gmns-main/datasets/Berlin (ships node/link/poi/zone/demand -> full set)
"""
import os, sys, types
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
P4G = os.path.join(HERE, "..", "plot4gmns-main")

def stub_keplergl():
    m = types.ModuleType("keplergl")
    class KeplerGl:                      # minimal stub (interactive map path unused here)
        def __init__(self, *a, **k): pass
    m.KeplerGl = KeplerGl
    sys.modules["keplergl"] = m

def main():
    a = sys.argv[1:]
    demo = next((x for x in a if not x.startswith("-")), os.path.join(P4G, "datasets", "Berlin"))
    out = a[a.index("-o") + 1] if "-o" in a else os.path.join(HERE, "..", "docs", "p4g_gallery")
    os.makedirs(out, exist_ok=True)
    stub_keplergl()
    if os.path.isdir(P4G): sys.path.insert(0, P4G)   # vendored copy; else use pip-installed plot4gmns
    try:
        import plot4gmns as pg
    except ImportError:
        sys.exit("plot4gmns not found — `pip install plot4gmns` or place it at ../plot4gmns-main")
    mnet = pg.generate_multi_network_from_csv(demo)
    print(f"plot4gmns loaded {os.path.basename(demo)}")

    # the full capability set (plot4gmns tutorial), name -> call
    calls = [
        ("gmns_nodes",              lambda: pg.show_gmns_nodes(mnet)),
        ("gmns_links",              lambda: pg.show_gmns_links(mnet)),
        ("gmns_poi",                lambda: pg.show_gmns_poi(mnet)),
        ("gmns_zones",              lambda: pg.show_gmns_zones(mnet)),
        ("gmns_geometries",         lambda: pg.show_gmns_geometries(mnet)),
        ("by_mode_auto",            lambda: pg.show_network_by_modes(mnet=mnet, modes=['auto'])),
        ("by_mode_bike",            lambda: pg.show_network_by_modes(mnet=mnet, modes=['bike'])),
        ("by_node_type_signal",     lambda: pg.show_network_by_node_types(mnet=mnet, ctrl_type=['signal'])),
        ("by_link_type",            lambda: pg.show_network_by_link_types(mnet=mnet, link_types=['secondary', 'footway'])),
        ("by_link_length",          lambda: pg.show_network_by_link_length(mnet=mnet, min_length=10, max_length=50)),
        ("by_link_free_speed",      lambda: pg.show_network_by_link_free_speed(mnet=mnet, min_free_speed=10, max_free_speed=40)),
        ("by_link_lanes",           lambda: pg.show_network_by_link_lanes(mnet=mnet, min_lanes=2, max_lanes=4)),
        ("link_lane_distribution",  lambda: pg.show_network_by_link_lane_distribution(mnet=mnet)),
        ("link_capacity_distribution", lambda: pg.show_network_by_link_capacity_distribution(mnet=mnet)),
        ("link_free_speed_distribution", lambda: pg.show_network_by_link_free_speed_distribution(mnet=mnet)),
        ("by_poi_type",             lambda: pg.show_network_by_poi_types(mnet=mnet, poi_type=['apartments', 'industrial'])),
        ("poi_attraction_distribution", lambda: pg.show_network_by_poi_attraction_distribution(mnet=mnet)),
        ("poi_production_distribution", lambda: pg.show_network_by_poi_production_distribution(mnet=mnet)),
        ("demand_matrix_heatmap",   lambda: pg.show_network_demand_matrix_heatmap(mnet)),
    ]
    # optional (need extra files; skip cleanly if absent)
    for nm, fn in [("gmns_lanes", lambda: pg.show_gmns_lanes(mnet)),
                   ("gmns_movements", lambda: pg.show_gmns_movements(mnet)),
                   ("by_demand_OD", lambda: pg.show_network_by_demand_OD(mnet=mnet, load_network=True))]:
        calls.append((nm, fn))

    ok = 0
    for nm, fn in calls:
        try:
            r = fn()
            fig = r if hasattr(r, "savefig") else plt.gcf()
            p = os.path.join(out, f"p4g_{nm}.png")
            fig.savefig(p, dpi=120, bbox_inches="tight")
            plt.close("all"); ok += 1
            print(f"  ok  p4g_{nm}.png")
        except Exception as e:
            plt.close("all"); print(f"  --  {nm}: {type(e).__name__}: {str(e)[:60]}")
    print(f"\nexported {ok}/{len(calls)} plot4gmns figures -> {out}/")

if __name__ == "__main__":
    main()

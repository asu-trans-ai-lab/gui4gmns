// DLSim production runner — the Phase-5 "queryable run package" (plan §5 / spec §7-9).
//   dlsim_run <scenario_dir> [--odme N]
// Reads the encoding files, runs the STE engine (or the closed ODME loop with --odme N iterations),
// and writes a machine+human-readable run package into <scenario_dir>/out/:
//   link_performance.csv     per-link CA/CD/max queue (+15-min bins when minute stats are on)
//   run_summary.json         totals, VMT/VHT, CPU, threads, determinism checksum, conservation
//   odme_summary.json        (with --odme) RMSE history, theta stats, gate counts
//   privacy_manifest.json    export levels (default max level 2: link-time performance)
//   run_log.md               human-readable narrative
// DTALite integration note: this binary is the engine behind `simulation_engine = DLSim_STE`.
#include <chrono>
#include <cstdio>
#include <algorithm>
#include <fstream>
#include <string>

#include "../core/Scheduler.h"
#include "../io/Reader.h"
#include "../odme/ODMELoop.h"

using namespace ste;

static std::string hhmm(int base_min, int tick, int tick_sec) {
    if (tick < 0) return "n/a";
    int m = base_min + tick * tick_sec / 60;
    char b[16]; std::snprintf(b, sizeof b, "%02d:%02d", m / 60, m % 60); return b;
}

int main(int argc, char** argv) {
    if (argc < 2) { std::printf("usage: %s <scenario_dir> [--odme N]\n", argv[0]); return 2; }
    std::string dir = argv[1];
    int odme_iters = 0, traj_n = 0;
    double odme_bound = 0.10, odme_eta = -1.0;
    for (int i = 2; i < argc; ++i) {
        if (std::string(argv[i]) == "--odme" && i + 1 < argc) odme_iters = std::atoi(argv[i + 1]);
        if (std::string(argv[i]) == "--traj" && i + 1 < argc) traj_n = std::atoi(argv[i + 1]);
        if (std::string(argv[i]) == "--bound" && i + 1 < argc) odme_bound = std::atof(argv[i + 1]);
        if (std::string(argv[i]) == "--eta" && i + 1 < argc) odme_eta = std::atof(argv[i + 1]);
    }
    std::string outdir = dir + "/out";
    (void)system(("mkdir -p \"" + outdir + "\" 2>nul").c_str());

    auto t0 = std::chrono::steady_clock::now();
    ODMEOutcome odme;
    if (odme_iters > 0) { ODMELoop loop; loop.bound = odme_bound;
        if (odme_eta > 0) loop.eta = odme_eta; odme = loop.run(dir, odme_iters); }

    Scheduler S; ScenarioLoader L;
    if (traj_n > 0) S.traj_max = traj_n;   // explicit privacy-level-0 opt-in
    if (odme_iters > 0) { L.theta_override = odme.theta; L.phi_override = odme.phi; }
    if (!L.load(dir, S)) return 2;
    auto t1 = std::chrono::steady_clock::now();
    S.init(); S.run();
    auto t2 = std::chrono::steady_clock::now();
    auto ms = [](auto a, auto b) {
        return std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count();
    };

    // metrics
    long long total = (long long)S.agents.size();
    double vmt = 0;
    for (auto& k : S.links) vmt += (double)k.cum_departure * k.length_mi;
    double vht = 0;
    for (auto& a : S.agents)
        if (a.completion_tick >= 0) vht += (a.completion_tick - a.dep_tick) * S.tick_sec / 3600.0;
    unsigned long long cks = 0;
    for (auto& k : S.links) cks = cks * 1315423911ull + (unsigned long long)k.cum_departure;
    bool conserved = (S.completed == total);
    S.finalize_flags();

    // ---- link_performance.csv ----
    {
        std::ofstream f(outdir + "/link_performance.csv");
        f << "link_id,from_node_id,to_node_id,cum_arrival,cum_departure,max_queue_exb,max_occupancy\n";
        for (auto& k : S.links)
            f << k.id << "," << k.from_node << "," << k.to_node << "," << k.cum_arrival << ","
              << k.cum_departure << "," << k.max_exb << "," << k.max_occupancy << "\n";
    }
    // ---- run_summary.json ----
    {
        std::ofstream f(outdir + "/run_summary.json");
        f << "{\n"
          << "  \"engine\": \"DLSim_STE\",\n  \"scenario\": \"" << dir << "\",\n"
          << "  \"threads\": " << S.threads() << ",\n"
          << "  \"agents\": " << total << ",\n  \"completed\": " << S.completed << ",\n"
          << "  \"conserved\": " << (conserved ? "true" : "false") << ",\n"
          << "  \"last_completion\": \"" << hhmm(L.base_min, S.last_completion_tick, S.tick_sec) << "\",\n"
          << "  \"vmt_veh_mi\": " << (long long)vmt << ",\n  \"vht_veh_hr\": " << (long long)vht << ",\n"
          << "  \"cpu_ms\": { \"load_route\": " << ms(t0, t1) << ", \"simulate\": " << ms(t1, t2) << " },\n"
          << "  \"determinism_checksum\": \"" << cks << "\",\n"
          << "  \"odme_enabled\": " << (odme_iters > 0 ? "true" : "false") << ",\n"
          << "  \"gridlock\": {\n"
          << "    \"oversaturated\": " << (S.oversaturated ? "true" : "false") << ",\n"
          << "    \"peak_blocked_share\": " << S.blocked_share_peak << ",\n"
          << "    \"deadlock_cycles_detected\": " << S.cycles_detected << ",\n"
          << "    \"storage_bypass_moves\": " << S.relax_moves << ",\n"
          << "    \"origin_metered_min\": " << S.metered_ticks / S.ticks_per_min << ",\n"
          << "    \"first_warning\": \"" << hhmm(L.base_min, S.first_warning_tick, S.tick_sec) << "\",\n"
          << "    \"events\": " << S.grid_events.size() << "\n  }\n}\n";
    }
    // ---- congestion_duration.csv (A1: PAQ/QVDF KPI — P = t3-t0, D, mu = D/P per episode) ----
    {
        std::ofstream f(outdir + "/congestion_duration.csv");
        f << "link_id,episode,onset,clear,P_min,D_veh,mu_vph,DC_ratio,max_queue,censored\n";
        int n_cong_links = 0; double max_P = 0; int worst_link = -1;
        for (auto& k : S.links) {
            if (k.cong_episodes.empty()) continue;
            ++n_cong_links; int ep = 0;
            for (auto& e : k.cong_episodes) {
                double P_hr = (e.clear_tick - e.onset_tick) * S.tick_sec / 3600.0;
                double mu = P_hr > 0 ? e.D / P_hr : 0;
                double cap_total = k.cap_per_lane_hr * k.lanes;
                f << k.id << "," << ++ep << "," << hhmm(L.base_min, e.onset_tick, S.tick_sec) << ","
                  << hhmm(L.base_min, e.clear_tick, S.tick_sec) << "," << (int)(P_hr * 60 + 0.5) << ","
                  << e.D << "," << (long long)mu << ","
                  << (cap_total > 0 ? mu / cap_total : 0) << "," << e.max_queue << ","
                  << (e.clear_tick >= S.horizon_ticks ? 1 : 0) << "\n";
                if (P_hr * 60 > max_P) { max_P = P_hr * 60; worst_link = k.id; }
            }
        }
        std::ofstream js(outdir + "/congestion_summary.json");
        js << "{ \"congested_links\": " << n_cong_links << ", \"max_duration_min\": " << (int)max_P
           << ", \"worst_link\": " << worst_link << " }\n";
    }
    // ---- gridlock_events.csv (early-warning log) ----
    if (!S.grid_events.empty()) {
        std::ofstream f(outdir + "/gridlock_events.csv");
        f << "time,type,link_id,value\n";
        for (auto& e : S.grid_events)
            f << hhmm(L.base_min, e.tick, S.tick_sec) << "," << e.type << "," << e.link_id << ","
              << e.value << "\n";
    }
    // ---- odme_summary.json ----
    if (odme_iters > 0) {
        std::ofstream f(outdir + "/odme_summary.json");
        f << "{\n  \"iterations\": " << odme_iters << ",\n  \"rmse_history\": [";
        for (size_t i = 0; i < odme.history.size(); ++i)
            f << (i ? ", " : "") << odme.history[i].rmse;
        f << "],\n  \"observable_od\": " << odme.n_observable
          << ",\n  \"frozen_od_no_sensor\": " << odme.n_frozen
          << ",\n  \"theta_bound\": 0.10,\n  \"bounds_ok\": " << (odme.bounds_ok ? "true" : "false")
          << ",\n  \"phi\": [";
        for (size_t b = 0; b < odme.phi.size(); ++b) f << (b ? ", " : "") << odme.phi[b];
        f << "]\n}\n";
        // per-OD adjustment (only observable ODs appear; frozen ODs are theta = 1 by the gate)
        std::ofstream ft(outdir + "/od_theta.csv");
        ft << "o_zone_id,d_zone_id,theta\n";
        for (auto& [od, th] : odme.theta) ft << od.first << "," << od.second << "," << th << "\n";
    }
    // ---- link_performance_15min.csv (time-dependent MOE for the gui4gmns animation) ----
    if (S.minute_stats) {
        std::ofstream f(outdir + "/link_performance_15min.csv");
        f << "link_id,time_bin_start,inflow_veh,queue_exb\n";
        int mins = S.horizon_ticks / S.ticks_per_min;
        for (size_t i = 0; i < S.links.size(); ++i)
            for (int m0 = 0; m0 + 15 <= mins; m0 += 15) {
                int inflow = 0;
                for (int m = m0; m < m0 + 15; ++m) inflow += S.inflow_per_min[i][m];
                if (inflow == 0 && S.exb_per_min[i][m0] == 0) continue;   // sparse
                f << S.links[i].id << "," << hhmm(L.base_min, m0 * S.ticks_per_min, S.tick_sec) << ","
                  << inflow << "," << S.exb_per_min[i][m0] << "\n";
            }
    }
    // ---- path_flow.csv (top-200 OD rows by volume; the NEXTA path layer) ----
    {
        std::vector<size_t> order(L.od_rows.size());
        for (size_t i = 0; i < order.size(); ++i) order[i] = i;
        std::sort(order.begin(), order.end(), [&](size_t a, size_t b) {
            return std::get<2>(L.od_rows[a]) > std::get<2>(L.od_rows[b]);
        });
        std::ofstream f(outdir + "/path_flow.csv");
        f << "o_zone_id,d_zone_id,base_volume,route_share,link_ids\n";
        for (size_t k = 0; k < order.size() && k < 200; ++k) {
            size_t i = order[k];
            for (auto& [path, share] : L.od_row_paths[i]) {
                f << std::get<0>(L.od_rows[i]) << "," << std::get<1>(L.od_rows[i]) << ","
                  << std::get<2>(L.od_rows[i]) << "," << share << ",\"";
                for (size_t j = 0; j < path.size(); ++j) f << (j ? ";" : "") << S.links[path[j]].id;
                f << "\"\n";
            }
        }
    }

    // ---- agent_trajectory.csv (only with --traj N: explicit level-0 opt-in) ----
    if (traj_n > 0) {
        std::ofstream f(outdir + "/agent_trajectory.csv");
        f << "agent_id,link_id,time_min,buffer,traffic_state\n";
        static const char* TS[] = {"free_flow", "queued", "discharging", "blocked", "completed"};
        for (auto& e : S.demo_log)
            f << e.agent << "," << S.links[e.link].id << ","
              << (L.base_min + e.tick * S.tick_sec / 60.0) << ","
              << (e.buffer == BufferType::ENB ? "ENB" : "EXB") << "," << TS[(int)e.tstate] << "\n";
    }

    // ---- privacy_manifest.json ----
    {
        std::ofstream f(outdir + "/privacy_manifest.json");
        f << "{\n  \"export_max_level\": 2,\n  \"levels\": {\n"
          << "    \"0_raw_trajectory\": \"internal only - NOT exported\",\n"
          << "    \"2_link_time_performance\": \"out/link_performance.csv\",\n"
          << "    \"3_summary\": \"out/run_summary.json\"\n  },\n"
          << "  \"note\": \"raw agent trajectories are not exported unless explicitly requested\"\n}\n";
    }
    // ---- run_log.md ----
    {
        std::ofstream f(outdir + "/run_log.md");
        f << "# DLSim run log\n\n| item | value |\n|---|---|\n"
          << "| scenario | " << dir << " |\n| threads | " << S.threads() << " |\n"
          << "| agents | " << total << " |\n| completed | " << S.completed
          << (conserved ? " (conserved)" : " (NOT conserved)") << " |\n"
          << "| last completion | " << hhmm(L.base_min, S.last_completion_tick, S.tick_sec) << " |\n"
          << "| VMT / VHT | " << (long long)vmt << " veh-mi / " << (long long)vht << " veh-hr |\n"
          << "| CPU | route " << ms(t0, t1) << " ms, simulate " << ms(t1, t2) << " ms |\n"
          << "| checksum | " << cks << " |\n";
        if (odme_iters > 0)
            f << "| ODME | " << odme_iters << " iters, RMSE " << odme.history.front().rmse << " -> "
              << odme.history.back().rmse << ", observable " << odme.n_observable << ", frozen "
              << odme.n_frozen << " |\n";
    }
    std::printf("dlsim_run: %s -> %s  (agents=%lld completed=%lld conserved=%s, VMT=%.0f, "
                "sim %lld ms, %d threads)\n",
                dir.c_str(), outdir.c_str(), total, S.completed, conserved ? "yes" : "NO", vmt,
                (long long)ms(t1, t2), S.threads());
    return conserved ? 0 : 1;
}

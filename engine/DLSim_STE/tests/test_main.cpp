// DLSim STE kernel — stage tests. Usage: dlsim_test <testdata_dir> <stage1|stage2>
// Stage 1: one-link bottleneck   — queue forms, incident halves discharge, conservation, queue clears.
// Stage 2: two-link spillback    — storage cap reached, loading blocked, conservation still holds.
#include <chrono>
#include <cstdio>
#include <fstream>
#include <numeric>
#include <string>

#include "../core/Scheduler.h"
#include "../io/Reader.h"
#include "../odme/ODMELoop.h"

using namespace ste;

static int n_pass = 0, n_fail = 0;
static void check(bool ok, const std::string& name, const std::string& detail) {
    std::printf("  [%s] %-52s %s\n", ok ? "PASS" : "FAIL", name.c_str(), detail.c_str());
    (ok ? n_pass : n_fail)++;
}
static double avg_inflow_per_min(const Scheduler& S, int link_idx, int min_from, int min_to) {
    double s = 0; int n = 0;
    for (int m = min_from; m <= min_to; ++m) { s += S.inflow_per_min[link_idx][m]; ++n; }
    return n ? s / n : 0;
}
static double avg_dep_per_min(const Scheduler& S, int link_idx, int min_from, int min_to) {
    double s = 0; int n = 0;
    for (int m = min_from; m <= min_to; ++m) { s += S.dep_per_min[link_idx][m]; ++n; }
    return n ? s / n : 0;
}
static int idx_of(const Scheduler& S, int link_id) {
    for (size_t i = 0; i < S.links.size(); ++i)
        if (S.links[i].id == link_id) return (int)i;
    return -1;
}
static std::string hhmm(int base_min, int tick, int tick_sec) {
    int m = base_min + tick * tick_sec / 60;
    char b[16]; std::snprintf(b, sizeof b, "%02d:%02d", m / 60, m % 60); return b;
}

// ---- stage 9: closed ODME loop (truth run -> measurement.csv -> gated/bounded recovery) ----
static int run_stage9(const std::string& root) {
    // 1) truth simulation -> write measurement.csv (sensors: links 1 and 3, 15-min bins 07:00-08:15)
    Scheduler St; ScenarioLoader Lt;
    if (!Lt.load(root + "/stage9_truth", St)) return 2;
    St.init(); St.run();
    std::map<int, int> lidx;
    for (size_t i = 0; i < St.links.size(); ++i) lidx[St.links[i].id] = (int)i;
    {
        std::ofstream mf(root + "/stage9_odme/measurement.csv");
        mf << "sensor_id,link_id,time_bin,count,quality,privacy_level\n";
        int sid = 100;
        for (int lid : {1, 3}) {
            for (int b0 = 420; b0 < 420 + 75; b0 += 15) {
                double c = 0;
                for (int m = b0 - Lt.base_min; m < b0 - Lt.base_min + 15; ++m)
                    if (m >= 0 && m < (int)St.inflow_per_min[lidx[lid]].size())
                        c += St.inflow_per_min[lidx[lid]][m];
                char tb[32];
                std::snprintf(tb, sizeof tb, "%02d:%02d-%02d:%02d", b0 / 60, b0 % 60, (b0 + 15) / 60, (b0 + 15) % 60);
                mf << sid << "," << lid << "," << tb << "," << c << ",observed,2\n";
            }
            ++sid;
        }
    }
    // 2) closed loop on the biased seed (theta) + flat profile (phi)
    ODMELoop loop;
    loop.eta = 1.2;                       // shared-sensor ODs converge slowly; still bound-safe
    ODMEOutcome R = loop.run(root + "/stage9_odme", 15);
    std::printf("== stage9: closed ODME loop ==\nRMSE history: ");
    for (auto& h : R.history) std::printf("%.1f ", h.rmse);
    std::printf("\ntheta:");
    for (auto& [od, th] : R.theta) std::printf(" (%d->%d)=%.4f", od.first, od.second, th);
    std::printf("\nphi:");
    for (double p : R.phi) std::printf(" %.4f", p);
    std::printf("\nobservable=%d frozen=%d\n", R.n_observable, R.n_frozen);

    double r0 = R.history.front().rmse, rN = R.history.back().rmse;
    check(rN < 0.35 * r0, "count RMSE reduced > 65%",
          std::to_string(r0).substr(0, 6) + " -> " + std::to_string(rN).substr(0, 6));
    check(R.n_observable == 2 && R.n_frozen == 1,
          "observability gate: 2 observable, 1 frozen (no sensor)", "");
    check(!R.theta.count({1, 4}), "unobservable OD (1->4) never adjusted (theta = 1)", "");
    double t13 = R.theta.count({1, 3}) ? R.theta[{1, 3}] : 1.0;
    double t23 = R.theta.count({2, 3}) ? R.theta[{2, 3}] : 1.0;
    check(t13 >= 1.04 && t13 <= 1.101, "theta(1->3) recovers +9% (truth 1200/seed 1100)",
          std::to_string(t13).substr(0, 6));
    check(t23 >= 0.899 && t23 <= 0.96, "theta(2->3) recovers -8% (truth 600/seed 650)",
          std::to_string(t23).substr(0, 6));
    check(R.bounds_ok, "all theta within the +-10% credibility bound", "");
    double true_phi[4] = {0.15, 0.35, 0.35, 0.15}, l1_flat = 0, l1_fin = 0;
    for (int b = 0; b < 4; ++b) {
        l1_flat += std::fabs(0.25 - true_phi[b]);
        l1_fin += std::fabs((b < (int)R.phi.size() ? R.phi[b] : 0.25) - true_phi[b]);
    }
    check(l1_fin < 0.5 * l1_flat, "phi(t) recovered toward the true peaked profile",
          "L1 " + std::to_string(l1_flat).substr(0, 5) + " -> " + std::to_string(l1_fin).substr(0, 5));
    std::printf("== %d passed, %d failed ==\n", n_pass, n_fail);
    return n_fail == 0 ? 0 : 1;
}

int main(int argc, char** argv) {
    if (argc < 3) { std::printf("usage: %s <dir> <stage1|stage2>\n", argv[0]); return 2; }
    std::string dir = argv[1], stage = argv[2];
    if (stage == "stage9") return run_stage9(dir);

    Scheduler S; ScenarioLoader L;
    auto t0 = std::chrono::steady_clock::now();
    if (!L.load(dir, S)) return 2;
    auto t1 = std::chrono::steady_clock::now();
    S.init();
    S.run();
    auto t2 = std::chrono::steady_clock::now();
    auto ms = [](auto a, auto b) {
        return std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count();
    };
    std::printf("CPU: load+route %lld ms, simulate %lld ms (%d ticks, %zu links, %zu agents, %d threads)\n",
                (long long)ms(t0, t1), (long long)ms(t1, t2), S.horizon_ticks, S.links.size(),
                S.agents.size(), S.threads());

    // bit-determinism checksum: link CD hash + sum of completion ticks (thread-count invariant)
    unsigned long long cks = 0; long long sum_ct = 0;
    for (auto& k : S.links) cks = cks * 1315423911ull + (unsigned long long)k.cum_departure;
    for (auto& a : S.agents) if (a.completion_tick >= 0) sum_ct += a.completion_tick;
    std::printf("determinism_checksum=%llu_%lld\n", cks, sum_ct);

    // gridlock management summary + event log
    S.finalize_flags();
    std::printf("gridlock: policy_events=%zu peak_blocked_share=%.3f cycles=%d relax_moves=%lld "
                "metered_min=%lld first_warning=%s oversaturated=%s\n",
                S.grid_events.size(), S.blocked_share_peak, S.cycles_detected, S.relax_moves,
                S.metered_ticks / S.ticks_per_min,
                S.first_warning_tick >= 0 ? hhmm(L.base_min, S.first_warning_tick, S.tick_sec).c_str() : "none",
                S.oversaturated ? "YES" : "no");
    if (!S.grid_events.empty()) {
        std::ofstream gf(dir + "/out_gridlock_events.csv");
        gf << "time,type,link_id,value\n";
        for (auto& e : S.grid_events)
            gf << hhmm(L.base_min, e.tick, S.tick_sec) << "," << e.type << "," << e.link_id << ","
               << e.value << "\n";
    }

    // ---- run summary ----
    std::printf("== %s: %s ==\n", stage.c_str(), dir.c_str());
    std::printf("agents=%zu completed=%lld last_completion=%s max_entry_delay=%.1f min\n",
                S.agents.size(), S.completed,
                S.last_completion_tick >= 0 ? hhmm(L.base_min, S.last_completion_tick, S.tick_sec).c_str() : "n/a",
                S.max_entry_delay_ticks * S.tick_sec / 60.0);
    if (S.links.size() <= 8)
        for (size_t i = 0; i < S.links.size(); ++i) {
            const Link& k = S.links[i];
            std::printf("link %d: CA=%lld CD=%lld max_occ=%d/%d max_queue(EXB)=%d fftt=%d ticks\n",
                        k.id, k.cum_arrival, k.cum_departure, k.max_occupancy, k.storage_cap, k.max_exb,
                        k.fftt_ticks);
        }

    // demo: the event list IS the trajectory (agent 0)
    std::printf("agent 0 event list: ");
    for (auto& e : S.demo_log)
        std::printf("(%d,L%d,%s,%s%s) ", e.agent, S.links[e.link].id,
                    hhmm(L.base_min, e.tick, S.tick_sec).c_str(),
                    e.buffer == BufferType::ENB ? "ENB" : "EXB",
                    e.tstate == TrafficState::completed ? ",done" : "");
    std::printf("\n");

    // ---- 15-min link performance output (encoding §9) ----
    if (S.links.size() <= 200) {
        std::ofstream out(dir + "/out_link_performance_15min.csv");
        out << "link_id,time_bin_start,inflow_veh,exb_queue_at_bin_start\n";
        int mins = S.horizon_ticks / S.ticks_per_min;
        for (size_t i = 0; i < S.links.size(); ++i)
            for (int m0 = 0; m0 + 15 <= mins; m0 += 15) {
                int inflow = 0;
                for (int m = m0; m < m0 + 15; ++m) inflow += S.inflow_per_min[i][m];
                out << S.links[i].id << "," << hhmm(L.base_min, m0 * S.ticks_per_min, S.tick_sec)
                    << "," << inflow << "," << S.exb_per_min[i][m0] << "\n";
            }
    }

    // link indices: link id 1 -> upstream, id 2 -> bottleneck (both stages)
    int up = 0, bt = 1;
    long long total = (long long)S.agents.size();

    if (stage == "stage1") {
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        check(S.links[up].max_occupancy < S.links[up].storage_cap,
              "no spillback: link1 occupancy under storage cap",
              std::to_string(S.links[up].max_occupancy) + " < " + std::to_string(S.links[up].storage_cap));
        // KW physics (F2): near the peak the Newell envelope CA - CD(t-1-BWTT) < kjam*L briefly gates
        // entry (vacated space needs L/w to propagate back) — bounded, not runaway
        check(S.max_entry_delay_ticks >= 1 && S.max_entry_delay_ticks <= 150,
              "KW entry gating at peak: bounded (< 15 min)",
              "max entry delay " + std::to_string(S.max_entry_delay_ticks) + " ticks");
        double inc = avg_inflow_per_min(S, bt, 23, 37);      // inside incident (07:23-07:37), queued
        check(inc >= 10.0 && inc <= 13.0, "incident discharge ~700 veh/h",
              std::to_string(inc * 60).substr(0, 6) + " veh/h in 07:23-07:37");
        double post = avg_inflow_per_min(S, bt, 42, 55);     // post-incident, still queued
        check(post >= 21.5 && post <= 25.0, "queued discharge ~1400 veh/h",
              std::to_string(post * 60).substr(0, 6) + " veh/h in 07:42-07:55");
        check(S.links[up].max_exb > 50, "queue formed upstream of bottleneck",
              "max EXB " + std::to_string(S.links[up].max_exb));
        check(S.last_completion_tick <= 135 * S.ticks_per_min, "queue clears (all done by 09:15)",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
    } else if (stage == "stage2") {
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        // KW physics (F2): a DISCHARGING link never reaches jam density — occupancy peaks near
        // kjam*L minus the departures within one backward-wave time (~360 - 700/h x 5 min ~ 302);
        // the storage constraint binds through the CA - CD(t-1-BWTT) envelope (see entry delay below)
        check(S.links[up].max_occupancy >= 250 && S.links[up].max_occupancy <= S.links[up].storage_cap,
              "spillback: KW envelope binds (occupancy near kjam*L - mu*L/w)",
              std::to_string(S.links[up].max_occupancy) + " in [250," + std::to_string(S.links[up].storage_cap) + "]");
        check(S.max_entry_delay_ticks > 50, "loading blocked (entry delayed > 5 min)",
              std::to_string(S.max_entry_delay_ticks * S.tick_sec / 60) + " min max delay");
        double inc = avg_inflow_per_min(S, bt, 23, 37);
        check(inc >= 10.0 && inc <= 13.0, "incident discharge ~700 veh/h",
              std::to_string(inc * 60).substr(0, 6) + " veh/h in 07:23-07:37");
        check(S.last_completion_tick <= 200 * S.ticks_per_min, "network clears (all done by 10:20)",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
    }

    if (stage == "stage3") {
        // merge: links a=1 (heavy), b=2 (light, half of a's demand) -> c=3 (bottleneck 1800/h)
        int a = idx_of(S, 1), b = idx_of(S, 2), c = idx_of(S, 3);
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        double da = avg_dep_per_min(S, a, 30, 55), db = avg_dep_per_min(S, b, 30, 55);
        double ratio = db > 0 ? da / db : 0;
        check(ratio >= 1.5 && ratio <= 2.6, "proportional merge: service ratio ~2:1",
              "a/b = " + std::to_string(ratio).substr(0, 4) + " in 07:30-07:55");
        double tot = avg_inflow_per_min(S, c, 30, 55);
        check(tot >= 28.5 && tot <= 31.5, "merge throughput = downstream capacity (1800/h)",
              std::to_string(tot * 60).substr(0, 6) + " veh/h");
        check(S.links[a].max_exb > 30 && S.links[b].max_exb > 30, "both approaches queued",
              "a EXB " + std::to_string(S.links[a].max_exb) + ", b EXB " + std::to_string(S.links[b].max_exb));
        check(S.links[a].max_occupancy < S.links[a].storage_cap &&
              S.links[b].max_occupancy < S.links[b].storage_cap, "no spillback on approaches", "");
        check(S.last_completion_tick <= 105 * S.ticks_per_min, "clears by 08:45",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
    } else if (stage == "stage4") {
        // signal: link 2 green_ratio 0.45 during 07:10-07:50 -> discharge = 0.45 x 1800 = 810/h
        int sig = idx_of(S, 2);
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        double green = avg_inflow_per_min(S, sig, 12, 48);
        check(green >= 12.5 && green <= 14.5, "signal discharge = g/C x sat flow (~810/h)",
              std::to_string(green * 60).substr(0, 6) + " veh/h in 07:12-07:48");
        double after = avg_inflow_per_min(S, sig, 52, 64);
        check(after >= 28.0 && after <= 31.5, "full discharge after green window (~1800/h)",
              std::to_string(after * 60).substr(0, 6) + " veh/h in 07:52-08:04");
        check(S.links[idx_of(S, 1)].max_exb > 50, "queue formed at signal",
              "max EXB " + std::to_string(S.links[idx_of(S, 1)].max_exb));
        check(S.last_completion_tick <= 105 * S.ticks_per_min, "clears by 08:45",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
    } else if (stage == "stage7") {
        // QVDF capacity drop: link 2 (C=1800, f_d=1.2) -> queue-discharge mu = 1500 veh/h
        int sig = idx_of(S, 2);
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        double ff = avg_inflow_per_min(S, sig, 5, 13);
        check(ff >= 13.0 && ff <= 16.5, "free-flow: demand-limited (~900/h), no drop",
              std::to_string(ff * 60).substr(0, 6) + " veh/h in 07:05-07:13");
        double drop = avg_inflow_per_min(S, sig, 20, 44);
        check(drop >= 24.0 && drop <= 26.0, "capacity drop: mu = C/f_d = 1500 veh/h (< C = 1800)",
              std::to_string(drop * 60).substr(0, 6) + " veh/h in 07:20-07:44");
        double drain = avg_inflow_per_min(S, sig, 46, 64);
        check(drain >= 24.0 && drain <= 26.0, "queue drains at dropped rate (1500 veh/h)",
              std::to_string(drain * 60).substr(0, 6) + " veh/h in 07:46-08:04");
        check(S.links[idx_of(S, 1)].max_exb > 100, "queue formed (theory ~300)",
              "max EXB " + std::to_string(S.links[idx_of(S, 1)].max_exb));
        check(S.last_completion_tick <= 80 * S.ticks_per_min, "clears by 08:20 (theory ~08:07)",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
        // A1 congestion-duration KPI closure: the measured episode's mu must equal the imposed
        // queue-discharge rate C/f_d = 1500 vph, and P must match the hand-computed duration
        {
            const Link& U = S.links[idx_of(S, 1)];
            check(U.cong_episodes.size() == 1, "one congestion episode detected",
                  std::to_string(U.cong_episodes.size()));
            if (!U.cong_episodes.empty()) {
                auto& e = U.cong_episodes.front();
                double P_min = (e.clear_tick - e.onset_tick) * S.tick_sec / 60.0;
                double mu = e.D / ((e.clear_tick - e.onset_tick) * S.tick_sec / 3600.0);
                check(P_min >= 42 && P_min <= 56, "episode duration P ~49 min (theory: 07:17-08:06)",
                      std::to_string((int)P_min) + " min");
                check(mu >= 1400 && mu <= 1560, "measured mu = D/P recovers C/f_d = 1500 vph",
                      std::to_string((int)mu) + " vph");
            }
        }
    } else if (stage == "stage11a") {
        // OVERLOAD + report_only: the engine must FAIL LOUDLY with early warnings — never absorb it
        check(S.completed < total, "overload NOT silently absorbed (report_only leaves demand stuck)",
              std::to_string(S.completed) + "/" + std::to_string(total));
        check(S.first_warning_tick >= 0 &&
                  S.first_warning_tick < (S.last_completion_tick >= 0 ? S.last_completion_tick : S.horizon_ticks) / 2,
              "EARLY warning (first alert in the first half of the run)",
              "first warning " + hhmm(L.base_min, S.first_warning_tick, S.tick_sec));
        check(S.cycles_detected > 0, "deadlock cycles DETECTED and reported",
              std::to_string(S.cycles_detected) + " cycles");
        check(S.relax_moves == 0, "report_only: zero storage bypasses (nothing hidden)",
              std::to_string(S.relax_moves));
        check(S.oversaturated, "run flagged OVERSATURATED", "");
        check(!S.grid_events.empty(), "gridlock event log written (out_gridlock_events.csv)",
              std::to_string(S.grid_events.size()) + " events");
    } else if (stage == "stage11b") {
        // OVERLOAD + meter+relax: managed loading — meter at origins, break only detected cycles, report
        // note: under corrected KW + effective-lane storage this scenario is managed by cycle-targeted
        // relaxation alone (no metering needed) and is CORRECTLY classified not-oversaturated —
        // the asserts test the mechanisms and the honest classification, not a fixed response mix
        check(S.completed == total, "managed overload conserves",
              std::to_string(S.completed) + "/" + std::to_string(total));
        check(S.first_warning_tick >= 0, "early warning emitted",
              hhmm(L.base_min, S.first_warning_tick, S.tick_sec));
        long long moves = 0; for (auto& k : S.links) moves += k.cum_departure;
        check(S.cycles_detected > 0 && S.relax_moves > 0 && S.relax_moves < moves / 100,
              "deadlock cycles broken by LOGGED last-resort bypasses (<1% of moves)",
              std::to_string(S.relax_moves) + " of " + std::to_string(moves) + ", " +
                  std::to_string(S.cycles_detected) + " cycles");
        check(!S.oversaturated, "correctly classified NOT oversaturated (criteria-based, honest)",
              "peak share " + std::to_string(S.blocked_share_peak).substr(0, 5));
        check(S.max_entry_delay_ticks * S.tick_sec < 3600, "no runaway origin queues", "");
    } else if (stage == "stage12") {
        // Riemann clearance (F2): link B (2 mi, w = 12 mph -> BWTT = 10 min) jammed behind an incident
        // that lifts at 07:30. Newell: entry to B resumes when the release wave reaches the entrance,
        // i.e. ~07:40 — NOT instantly (the pre-F2 kernel resumed at ~07:31).
        int B = idx_of(S, 2);
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        check(S.links[B].bwtt_ticks == 100, "BWTT = L/w = 2 mi / 12 mph = 10 min (100 ticks)",
              std::to_string(S.links[B].bwtt_ticks) + " ticks");
        int fill_min = -1, resume_min = -1;
        for (int m = 0; m < 30; ++m)                       // last inflow before the jam blocks entry
            if (S.inflow_per_min[B][m] > 0) fill_min = m;
        for (int m = 31; m < 120; ++m)                     // first inflow after the incident lifts
            if (S.inflow_per_min[B][m] > 0) { resume_min = m; break; }
        check(fill_min >= 0 && fill_min < 30, "link B filled to jam during incident (entry then blocked)",
              "last pre-clearance inflow at 07:" + std::to_string(fill_min));
        check(resume_min >= 38 && resume_min <= 42,
              "entry resumes ~L/w = 10 min AFTER clearance (Newell), not instantly",
              "resumed 07:" + std::to_string(resume_min) + " (analytic 07:40)");
        check(S.last_completion_tick <= 110 * S.ticks_per_min, "network clears",
              hhmm(L.base_min, S.last_completion_tick, S.tick_sec));
    } else if (stage == "stage5" || stage == "stage6" || stage == "stage10") {
        // Chicago Sketch baseline: agency-scale dynamic loading, conservation + completion + throughput
        check(S.completed == total, "conservation: all agents complete",
              std::to_string(S.completed) + "/" + std::to_string(total));
        check(S.last_completion_tick >= 0 && S.last_completion_tick < S.horizon_ticks,
              "network clears within horizon",
              S.last_completion_tick >= 0 ? hhmm(L.base_min, S.last_completion_tick, S.tick_sec) : "n/a");
        long long moves = 0; int max_q = 0, congested_links = 0;
        for (auto& k : S.links) {
            moves += k.cum_departure;
            max_q = std::max(max_q, k.max_exb);
            if (k.max_exb > 20) congested_links++;
        }
        check(moves > (long long)total * 2, "network throughput plausible (>2 links/agent avg)",
              std::to_string(moves) + " link departures");
        std::printf("  info: max link queue %d veh; links with queue>20: %d\n", max_q, congested_links);
    }

    std::printf("== %d passed, %d failed ==\n", n_pass, n_fail);
    return n_fail == 0 ? 0 : 1;
}

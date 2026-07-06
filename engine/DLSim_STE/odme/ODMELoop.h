// DLSim STE kernel — closed ODME loop (plan Phase 3), the kernel twin of dynamic-odme-lab / TAPLite:
//   simulate -> compare 15-min sensor counts -> OBSERVABILITY GATE -> bounded theta update (+-10%)
//   -> phi(t) recovery -> regenerate departures -> re-simulate.
// Firm rules (carried from the NVTA work):
//   R1  an OD whose paths cross NO sensor is never adjusted (theta = 1, frozen)
//   R2  hard credibility bound: theta in [1-bound, 1+bound]
//   R3  unreachable residuals stay in the report; they are never forced into the OD matrix
#pragma once
#include <cmath>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "../core/Scheduler.h"
#include "../io/Reader.h"

namespace ste {

struct ODMEIterStats { double rmse = 0; double total_sim = 0, total_obs = 0; };

struct ODMEOutcome {
    std::vector<ODMEIterStats> history;
    std::map<std::pair<int, int>, double> theta;   // final OD adjustment (gated + bounded)
    std::vector<double> phi;                       // final departure-bin ratios
    int n_observable = 0, n_frozen = 0;
    bool bounds_ok = true;
};

class ODMELoop {
public:
    double bound = 0.10;      // R2: hard +-10%
    double eta = 0.9;         // theta step
    double alpha = 0.9;       // phi step

    ODMEOutcome run(const std::string& dir, int iterations) {
        ODMEOutcome R;
        // measurement.csv: link_id,time_bin,count  (15-min bins, wall clock)
        Csv ms; ms.load(dir + "/measurement.csv");
        std::map<int, std::map<int, double>> obs;             // link_id -> bin_start_min -> count
        for (auto& r : ms.rows) {
            std::string tb = ms.get(r, "time_bin");
            obs[(int)ms.num(r, "link_id")][hhmm_to_min(tb.substr(0, tb.find('-')))] = ms.num(r, "count");
        }
        std::set<int> sensor_ids;
        for (auto& [lid, m] : obs) sensor_ids.insert(lid);

        std::map<std::pair<int, int>, double> theta;
        std::vector<double> phi;                              // empty on first pass = seed profile

        for (int it = 0; it <= iterations; ++it) {
            Scheduler S; ScenarioLoader L;
            L.theta_override = theta; L.phi_override = phi;
            if (!L.load(dir, S)) return R;
            S.init(); S.run();

            // simulated 15-min counts on sensor links
            std::map<int, int> lidx;                          // link id -> idx
            for (size_t i = 0; i < S.links.size(); ++i) lidx[S.links[i].id] = (int)i;
            auto sim_count = [&](int link_id, int bin_start_min) {
                int li = lidx.count(link_id) ? lidx[link_id] : -1;
                if (li < 0) return 0.0;
                int m0 = bin_start_min - L.base_min; double s = 0;
                for (int m = std::max(0, m0); m < m0 + 15 && m < (int)S.inflow_per_min[li].size(); ++m)
                    s += S.inflow_per_min[li][m];
                return s;
            };
            ODMEIterStats st; int n = 0; double sse = 0;
            for (auto& [lid, mm] : obs)
                for (auto& [b0, c_obs] : mm) {
                    double c_sim = sim_count(lid, b0);
                    sse += (c_sim - c_obs) * (c_sim - c_obs); ++n;
                    st.total_sim += c_sim; st.total_obs += c_obs;
                }
            st.rmse = n ? std::sqrt(sse / n) : 0;
            R.history.push_back(st);
            if (it == iterations) { R.theta = theta; R.phi = phi.empty() ? L.bins_ratio : phi; break; }

            // ---- R1 observability gate + R2 bounded theta update ----
            R.n_observable = R.n_frozen = 0;
            for (size_t i = 0; i < L.od_rows.size(); ++i) {
                auto [oz, dz, vol] = L.od_rows[i];
                double num = 0, den = 0;
                for (int li : L.od_row_links[i]) {
                    int lid = S.links[li].id;
                    auto io = obs.find(lid);
                    if (io == obs.end()) continue;            // not a sensor link
                    for (auto& [b0, c_obs] : io->second) { num += c_obs - sim_count(lid, b0); den += c_obs; }
                }
                if (den <= 0) { R.n_frozen++; continue; }     // R1: no sensor crossed -> frozen (theta 1)
                R.n_observable++;
                double& th = theta[{oz, dz}];
                if (th == 0.0) th = 1.0;
                th = std::min(1.0 + bound, std::max(1.0 - bound, th * (1.0 + eta * num / den)));
            }

            // ---- phi(t) recovery: match the observed time-of-day shape at the sensors ----
            if (phi.empty()) phi = L.bins_ratio;
            std::vector<double> s_obs(phi.size(), 0), s_sim(phi.size(), 0);
            for (size_t b = 0; b < phi.size(); ++b) {
                int b0 = L.bins_start_min[b];
                for (auto& [lid, mm] : obs) {
                    auto ib = mm.find(b0);
                    if (ib == mm.end()) continue;
                    s_obs[b] += ib->second; s_sim[b] += sim_count(lid, b0);
                }
            }
            double t_obs = 0, t_sim = 0;
            for (size_t b = 0; b < phi.size(); ++b) { t_obs += s_obs[b]; t_sim += s_sim[b]; }
            if (t_obs > 0 && t_sim > 0) {
                double norm = 0;
                for (size_t b = 0; b < phi.size(); ++b) {
                    double r_obs = s_obs[b] / t_obs, r_sim = std::max(1e-6, s_sim[b] / t_sim);
                    phi[b] *= std::pow(r_obs / r_sim, alpha);
                    norm += phi[b];
                }
                for (auto& p : phi) p /= norm;
            }
        }
        for (auto& [od, th] : R.theta)
            if (th < 1.0 - bound - 1e-9 || th > 1.0 + bound + 1e-9) R.bounds_ok = false;
        return R;
    }
};

}  // namespace ste

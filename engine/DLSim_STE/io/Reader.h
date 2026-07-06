// DLSim STE kernel — encoding reader: builds a Scheduler purely from the spec's files
// (node.csv, link.csv, demand_auto.csv, departure_time_profile.csv, control_event.csv, run_config.json).
// Phase-0 acceptance in action: the scenario is fully described by encodings, no C++ edits.
#pragma once
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "../core/Scheduler.h"

namespace ste {

// ---------- tiny CSV ----------
struct Csv {
    std::vector<std::string> header;
    std::vector<std::vector<std::string>> rows;
    std::unordered_map<std::string, int> idx;
    bool load(const std::string& path) {
        std::ifstream f(path);
        if (!f.is_open()) return false;
        std::string line; bool first = true;
        while (std::getline(f, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
            if (line.empty()) continue;
            std::vector<std::string> cells; std::stringstream ss(line); std::string c;
            while (std::getline(ss, c, ',')) cells.push_back(c);
            if (first) { header = cells; for (size_t i = 0; i < cells.size(); ++i) idx[cells[i]] = (int)i; first = false; }
            else rows.push_back(cells);
        }
        return true;
    }
    std::string get(const std::vector<std::string>& row, const std::string& col) const {
        auto it = idx.find(col);
        if (it == idx.end() || it->second >= (int)row.size()) return "";
        return row[it->second];
    }
    double num(const std::vector<std::string>& row, const std::string& col, double d = 0) const {
        std::string s = get(row, col); return s.empty() ? d : std::atof(s.c_str());
    }
};

// ---------- helpers ----------
inline int hhmm_to_min(const std::string& s) {              // "07:20" -> 440
    int h = 0, m = 0; if (std::sscanf(s.c_str(), "%d:%d", &h, &m) >= 1) return h * 60 + m;
    return 0;
}
inline std::string jstr(const std::string& js, const std::string& key, const std::string& d) {
    auto p = js.find("\"" + key + "\""); if (p == std::string::npos) return d;
    p = js.find(':', p); auto q1 = js.find('"', p); auto q2 = js.find('"', q1 + 1);
    if (q1 == std::string::npos || q2 == std::string::npos) return d;
    return js.substr(q1 + 1, q2 - q1 - 1);
}
inline double jnum(const std::string& js, const std::string& key, double d) {
    auto p = js.find("\"" + key + "\""); if (p == std::string::npos) return d;
    p = js.find(':', p); return std::atof(js.c_str() + p + 1);
}

// ---------- scenario loader ----------
class ScenarioLoader {
public:
    int base_min = 420;   // simulation t=0 wall-clock minute (default 07:00)

    // ---- ODME-loop hooks (encoding spec §2) ----
    std::map<std::pair<int, int>, double> theta_override;  // (oz,dz) -> multiplicative OD adjustment
    std::vector<double> phi_override;                      // replaces departure-bin ratios if size matches
    // exposed after load(): per demand row (oz, dz, seed volume) + union of path link idxs (coverage)
    std::vector<std::tuple<int, int, double>> od_rows;
    std::vector<std::vector<int>> od_row_links;
    std::vector<std::vector<std::pair<std::vector<int>, double>>> od_row_paths;   // per-row (path, share)
    std::vector<double> bins_ratio;                        // departure-bin ratios actually used
    std::vector<int> bins_start_min;                       // bin start minutes (wall clock)

    bool load(const std::string& dir, Scheduler& S) {
        // run_config.json
        std::ifstream cf(dir + "/run_config.json");
        std::string js((std::istreambuf_iterator<char>(cf)), std::istreambuf_iterator<char>());
        S.tick_sec = (int)jnum(js, "sim_tick_sec", 6);
        S.ticks_per_min = 60 / S.tick_sec;
        base_min = hhmm_to_min(jstr(js, "base_time", "07:00"));
        S.horizon_ticks = (int)jnum(js, "horizon_min", 180) * S.ticks_per_min;
        std::string gp = jstr(js, "gridlock_policy", "meter+relax");
        S.gridlock_policy = gp == "report_only" ? Scheduler::GridlockPolicy::report_only
                            : gp == "meter"     ? Scheduler::GridlockPolicy::meter
                            : gp == "relax"     ? Scheduler::GridlockPolicy::relax
                                                : Scheduler::GridlockPolicy::meter_relax;
        S.meter_on_share = jnum(js, "meter_on_share", S.meter_on_share);
        S.meter_off_share = jnum(js, "meter_off_share", S.meter_off_share);

        // node.csv: node -> zone; centroid set (for connector detection)
        Csv nodes; if (!nodes.load(dir + "/node.csv")) { err("node.csv"); return false; }
        std::map<int, int> zone_to_node;
        std::set<int> centroid_nodes;
        for (auto& r : nodes.rows) {
            int nid = (int)nodes.num(r, "node_id");
            std::string z = nodes.get(r, "zone_id");
            if (!z.empty()) { zone_to_node[std::atoi(z.c_str())] = nid; centroid_nodes.insert(nid); }
        }

        // link.csv — GMNS unit handling: prefer vdf_length_mi / vdf_free_speed_mph when > 0;
        // else assume miles/mph for small values, meters/kmh for large (real-world exports).
        Csv lk; if (!lk.load(dir + "/link.csv")) { err("link.csv"); return false; }
        std::map<int, int> link_id_to_idx;
        int n_unit_fallback = 0;
        for (auto& r : lk.rows) {
            Link L;
            L.id = (int)lk.num(r, "link_id");
            L.from_node = (int)lk.num(r, "from_node_id");
            L.to_node = (int)lk.num(r, "to_node_id");
            L.lanes = std::max(1.0, lk.num(r, "lanes", 1));
            L.cap_per_lane_hr = lk.num(r, "capacity", 1800);
            double vlen = lk.num(r, "vdf_length_mi", 0), rlen = lk.num(r, "length", 1);
            L.length_mi = vlen > 1e-6 ? vlen : (rlen < 50 ? rlen : (++n_unit_fallback, rlen / 1609.34));
            double vspd = lk.num(r, "vdf_free_speed_mph", 0), rspd = lk.num(r, "free_speed", 60);
            L.free_speed_mph = vspd > 1e-6 ? vspd : (rspd <= 90 ? rspd : rspd / 1.60934);
            L.kjam = lk.num(r, "kjam", 180);
            L.dmodel = lk.get(r, "discharge_model") == "qvdf" ? 1 : 0;
            L.qvdf_fd = lk.num(r, "qvdf_fd", 1.0);
            // centroid connector = touches a centroid AND is (near-)zero length; physical links that
            // happen to end at a centroid in toy networks keep their real storage constraint
            L.connector = (centroid_nodes.count(L.from_node) || centroid_nodes.count(L.to_node)) &&
                          L.length_mi < 0.25;
            link_id_to_idx[L.id] = (int)S.links.size();
            S.links.push_back(L);
        }
        if (n_unit_fallback)
            std::cerr << "[units] " << n_unit_fallback << " links: length meters->miles fallback\n";

        // adjacency for routing (FFTT-weighted Dijkstra)
        std::unordered_map<int, std::vector<std::pair<int, int>>> adj;  // node -> (link_idx, to_node)
        for (size_t i = 0; i < S.links.size(); ++i)
            adj[S.links[i].from_node].push_back({(int)i, S.links[i].to_node});

        // departure profile (phi)
        Csv ph; if (!ph.load(dir + "/departure_time_profile.csv")) { err("departure_time_profile.csv"); return false; }
        struct Bin { int start_min, end_min; double ratio; };
        std::vector<Bin> bins;
        for (auto& r : ph.rows) {
            std::string tb = ph.get(r, "time_bin");
            auto dash = tb.find('-');
            bins.push_back({hhmm_to_min(tb.substr(0, dash)), hhmm_to_min(tb.substr(dash + 1)),
                            ph.num(r, "ratio")});
        }
        if (phi_override.size() == bins.size())            // ODME-recovered phi replaces the seed profile
            for (size_t i = 0; i < bins.size(); ++i) bins[i].ratio = phi_override[i];
        bins_ratio.clear(); bins_start_min.clear();
        for (auto& b : bins) { bins_ratio.push_back(b.ratio); bins_start_min.push_back(b.start_min); }

        // demand + agent generation (cumulative rounding preserves totals)
        Csv dm; if (!dm.load(dir + "/demand_auto.csv")) { err("demand_auto.csv"); return false; }
        double dscale = jnum(js, "demand_scale", 1.0);
        std::string rmethod = jstr(js, "routing_method", "sp");
        int rit = (int)jnum(js, "routing_iterations", 8);

        struct DRow { int oz, dz; double vol; };
        std::vector<DRow> drows;
        for (auto& r : dm.rows) {
            int oz = (int)dm.num(r, "o_zone_id"), dz = (int)dm.num(r, "d_zone_id");
            double vol = dm.num(r, "volume") * dscale;
            if (vol <= 0 || oz == dz) continue;                        // intrazonal: never enters network
            drows.push_back({oz, dz, vol});
        }

        // ---- path set per OD row: (link path, route share) ----
        // priority: explicit path_flow.csv (DTALite assignment hook) > MSA diversification > shortest path
        std::vector<std::vector<std::pair<std::vector<int>, double>>> rowpaths(drows.size());
        Csv pf; bool have_pf = pf.load(dir + "/path_flow.csv");
        if (have_pf) {
            std::map<std::pair<int, int>, std::vector<std::pair<std::vector<int>, double>>> pfmap;
            for (auto& r : pf.rows) {
                int oz = (int)pf.num(r, "o_zone_id"), dz = (int)pf.num(r, "d_zone_id");
                double share = pf.num(r, "route_share", 1.0);
                std::vector<int> path; std::stringstream ss(pf.get(r, "link_ids")); std::string tok;
                bool ok = true;
                while (std::getline(ss, tok, ';'))
                    if (!tok.empty()) {
                        auto it = link_id_to_idx.find(std::atoi(tok.c_str()));
                        if (it == link_id_to_idx.end()) { ok = false; break; }
                        path.push_back(it->second);
                    }
                if (ok && !path.empty()) pfmap[{oz, dz}].push_back({path, share});
            }
            std::cerr << "[routing] path_flow.csv: " << pf.rows.size() << " path rows, "
                      << pfmap.size() << " OD pairs\n";
            for (size_t i = 0; i < drows.size(); ++i) {
                auto it = pfmap.find({drows[i].oz, drows[i].dz});
                if (it != pfmap.end()) rowpaths[i] = it->second;
                else {
                    std::vector<int> p = route(adj, zone_to_node[drows[i].oz], zone_to_node[drows[i].dz], S);
                    if (!p.empty()) rowpaths[i].push_back({p, 1.0});
                }
            }
        } else if (rmethod == "msa") {
            msa_paths(drows.size(), [&](size_t i) { return std::make_tuple(drows[i].oz, drows[i].dz, drows[i].vol); },
                      adj, zone_to_node, S, rowpaths, rit);
        } else {
            for (size_t i = 0; i < drows.size(); ++i) {
                std::vector<int> p = route(adj, zone_to_node[drows[i].oz], zone_to_node[drows[i].dz], S);
                if (!p.empty()) rowpaths[i].push_back({p, 1.0});
            }
        }

        // ---- expose OD rows + path coverage (for the ODME observability gate + path export) ----
        od_rows.clear(); od_row_links.clear();
        for (size_t i = 0; i < drows.size(); ++i) {
            od_rows.push_back({drows[i].oz, drows[i].dz, drows[i].vol});
            std::set<int> uni;
            for (auto& pw : rowpaths[i]) uni.insert(pw.first.begin(), pw.first.end());
            od_row_links.emplace_back(uni.begin(), uni.end());
        }
        od_row_paths = rowpaths;

        // ---- agent generation (cumulative rounding per path preserves totals) ----
        int aid = 0, n_skipped = 0; double vol_skipped = 0;
        for (size_t i = 0; i < drows.size(); ++i) {
            if (rowpaths[i].empty()) { ++n_skipped; vol_skipped += drows[i].vol; continue; }
            double th = 1.0;
            auto it_th = theta_override.find({drows[i].oz, drows[i].dz});
            if (it_th != theta_override.end()) th = it_th->second;
            double sum_share = 0;
            for (auto& pw : rowpaths[i]) sum_share += pw.second;
            for (auto& [path, w] : rowpaths[i]) {
                double pvol = drows[i].vol * th * w / sum_share;
                double cum = 0; long long placed = 0;
                for (auto& b : bins) {
                    cum += b.ratio;
                    long long target = (long long)(pvol * cum + 0.5);
                    int n = (int)(target - placed); placed = target;
                    for (int k = 0; k < n; ++k) {
                        Agent a; a.id = aid++;
                        a.path_links = path;
                        double dep_min = (b.start_min - base_min) +
                                         (k + 0.5) * (b.end_min - b.start_min) / (double)n;
                        a.dep_tick = (int)(dep_min * S.ticks_per_min + 0.5);
                        S.agents.push_back(a);
                    }
                }
            }
        }

        if (n_skipped)
            std::cerr << "[demand] skipped " << n_skipped << " unroutable OD rows ("
                      << vol_skipped << " veh)\n";

        // control events (phase-1: incident / work_zone capacity_factor)
        Csv ce;
        if (ce.load(dir + "/control_event.csv")) {
            for (auto& r : ce.rows) {
                std::string type = ce.get(r, "type"), param = ce.get(r, "parameter");
                bool cap_style = (type == "incident" || type == "work_zone") && param == "capacity_factor";
                bool signal_style = (type == "signal") && param == "green_ratio";
                if (cap_style || signal_style) {
                    // signal (meso approximation): effective capacity = saturation flow x green_ratio
                    ControlEvent c;
                    c.type = type == "incident" ? ControlState::incident
                             : type == "signal" ? ControlState::signal : ControlState::work_zone;
                    c.link_idx = link_id_to_idx[(int)ce.num(r, "location_id")];
                    c.start_tick = (hhmm_to_min(ce.get(r, "start_time")) - base_min) * S.ticks_per_min;
                    c.end_tick = (hhmm_to_min(ce.get(r, "end_time")) - base_min) * S.ticks_per_min;
                    c.cap_factor = ce.num(r, "value", 1.0);
                    S.controls.push_back(c);
                } else if (!type.empty()) {
                    std::cerr << "[phase-1] control type '" << type << "' parsed but not yet simulated\n";
                }
            }
        }
        return true;
    }

private:
    static void err(const std::string& f) { std::cerr << "missing " << f << "\n"; }

    // ---- MSA path diversification ----------------------------------------------------------
    // Method of Successive Averages with step 1/k over K all-or-nothing assignments; the final
    // link volumes equal the average of the K AON volumes, so each iteration's chosen path
    // carries route share 1/K. BPR(0.15,4) costs from the MSA-averaged volumes.
    std::unordered_map<int, std::pair<int, int>> dijkstra_prev(
        std::unordered_map<int, std::vector<std::pair<int, int>>>& adj, int src,
        const std::vector<double>& cost) {
        std::unordered_map<int, std::pair<int, int>> prev;
        std::unordered_map<int, double> dist;
        using QE = std::pair<double, int>;
        std::priority_queue<QE, std::vector<QE>, std::greater<QE>> pq;
        dist[src] = 0; pq.push({0, src});
        while (!pq.empty()) {
            auto [d, u] = pq.top(); pq.pop();
            auto it = dist.find(u);
            if (it != dist.end() && d > it->second + 1e-12) continue;
            for (auto& [li, v] : adj[u]) {
                auto iv = dist.find(v);
                if (iv == dist.end() || d + cost[li] < iv->second - 1e-12) {
                    dist[v] = d + cost[li]; prev[v] = {u, li}; pq.push({d + cost[li], v});
                }
            }
        }
        return prev;
    }
    static std::vector<int> extract_path(std::unordered_map<int, std::pair<int, int>>& prev,
                                         int src, int dst) {
        std::vector<int> path;
        if (src == dst || !prev.count(dst)) return path;
        for (int v = dst; v != src; v = prev[v].first) path.push_back(prev[v].second);
        std::reverse(path.begin(), path.end());
        return path;
    }

    template <typename GetRow>
    void msa_paths(size_t nrows, GetRow get,
                   std::unordered_map<int, std::vector<std::pair<int, int>>>& adj,
                   std::map<int, int>& zone_to_node, Scheduler& S,
                   std::vector<std::vector<std::pair<std::vector<int>, double>>>& rowpaths, int K) {
        size_t L = S.links.size();
        std::vector<double> v(L, 0.0);
        std::map<int, std::vector<size_t>> by_origin;
        for (size_t i = 0; i < nrows; ++i) by_origin[std::get<0>(get(i))].push_back(i);
        for (int it = 1; it <= K; ++it) {
            std::vector<double> cost(L);
            for (size_t li = 0; li < L; ++li) {
                double cap = S.links[li].cap_per_lane_hr * S.links[li].lanes;
                double t0 = S.links[li].length_mi / S.links[li].free_speed_mph;
                double x = cap > 0 ? v[li] / cap : 0;
                cost[li] = t0 * (1.0 + 0.15 * x * x * x * x);
            }
            // parallel over origins (each demand row belongs to exactly one origin -> rowpaths writes are
            // disjoint). AON volumes accumulate per-thread and merge in FIXED thread order so the
            // floating-point sum is identical regardless of thread count (determinism gate).
            std::vector<std::pair<int, std::vector<size_t>>> origs(by_origin.begin(), by_origin.end());
            int nthr = 1;
#ifdef _OPENMP
            nthr = omp_get_max_threads();
#endif
            // integer milli-vehicle accumulation: addition is associative -> the merged sum is identical
            // for ANY thread count / order (bit-deterministic routing volumes)
            std::vector<std::vector<long long>> v_thr(nthr, std::vector<long long>(L, 0));
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
            for (int oi = 0; oi < (int)origs.size(); ++oi) {
                int tid = 0;
#ifdef _OPENMP
                tid = omp_get_thread_num();
#endif
                auto prev = dijkstra_prev(adj, zone_to_node[origs[oi].first], cost);
                for (size_t i : origs[oi].second) {
                    auto [o, dz, vol] = get(i);
                    std::vector<int> path = extract_path(prev, zone_to_node[o], zone_to_node[dz]);
                    if (path.empty()) continue;
                    long long mv = (long long)(vol * 1000.0 + 0.5);
                    for (int li : path) v_thr[tid][li] += mv;
                    bool found = false;
                    for (auto& pw : rowpaths[i])
                        if (pw.first == path) { pw.second += 1.0 / K; found = true; break; }
                    if (!found) rowpaths[i].push_back({path, 1.0 / K});
                }
            }
            double w = 1.0 / it;
            for (size_t li = 0; li < L; ++li) {
                long long s = 0;
                for (int tI = 0; tI < nthr; ++tI) s += v_thr[tI][li];
                v[li] = (1 - w) * v[li] + w * (s / 1000.0);
            }
        }
        size_t multi = 0;
        for (size_t i = 0; i < nrows; ++i)
            if (rowpaths[i].size() > 1) multi++;
        std::cerr << "[routing] MSA-" << K << ": " << multi << "/" << nrows
                  << " OD rows diversified onto multiple paths\n";
    }

    // per-origin cache: one full Dijkstra per origin, reused across all destinations
    int cached_src_ = -0x7fffffff;
    std::unordered_map<int, std::pair<int, int>> cached_prev_;   // node -> (prev node, link_idx)

    std::vector<int> route(std::unordered_map<int, std::vector<std::pair<int, int>>>& adj,
                           int src, int dst, Scheduler& S) {
        if (src != cached_src_) {
            cached_src_ = src; cached_prev_.clear();
            std::unordered_map<int, double> dist;
            using QE = std::pair<double, int>;
            std::priority_queue<QE, std::vector<QE>, std::greater<QE>> pq;
            dist[src] = 0; pq.push({0, src});
            while (!pq.empty()) {
                auto [d, u] = pq.top(); pq.pop();
                auto it = dist.find(u);
                if (it != dist.end() && d > it->second + 1e-12) continue;
                for (auto& [li, v] : adj[u]) {
                    double w = S.links[li].length_mi / S.links[li].free_speed_mph;
                    auto iv = dist.find(v);
                    if (iv == dist.end() || d + w < iv->second - 1e-12) {
                        dist[v] = d + w; cached_prev_[v] = {u, li}; pq.push({d + w, v});
                    }
                }
            }
        }
        std::vector<int> path;
        if (src == dst) return path;
        if (!cached_prev_.count(dst)) return path;
        for (int v = dst; v != src; v = cached_prev_[v].first) path.push_back(cached_prev_[v].second);
        std::reverse(path.begin(), path.end());
        return path;
    }
};

}  // namespace ste

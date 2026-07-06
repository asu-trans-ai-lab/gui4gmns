// DLSim STE kernel — Scheduler: the paper's five-task synchronous pipeline per tick.
//   Task 1: load newly departed agents to first-link ENB (origin queue if storage full)
//   Task 2: per-link capacity update (control-modified; fractional-carry, no bursts)
//   Task 3: node capacity allocation (demand-proportional merge; QVDF capacity drop)
//   Task 4: node transfer  EXB(l) -> ENB(next)   (consumes out-cap(l), in-cap(next), storage(next))
//   Task 5: link transfer  ENB -> EXB when ready (arrival + FFTT)   [Newell KW forward move]
//
// Parallel design (paper §3, synchronous space-parallel LPs):
//   Tasks 2/3/5 are parallel over LINKS (each iteration writes only its own link).
//   Task 4 is parallel over NODES: node n owns the EXBs of its incoming links and the ENBs/avail_in
//   of its outgoing links, so per-node processing is race-free by construction. Merge allocations are
//   stored on the downstream link (single writer in Task 3, single reader-node in Task 4).
//   No RNG; identical arithmetic per LP regardless of thread count => bit-deterministic results.
#pragma once
#include <algorithm>
#include <deque>
#include <map>
#include <unordered_map>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

#include "Agent.h"
#include "Event.h"
#include "Link.h"

namespace ste {

struct ControlEvent {
    ControlState type = ControlState::none;
    int link_idx = -1;
    int start_tick = 0, end_tick = 0;
    double cap_factor = 1.0;
};

class Scheduler {
public:
    int tick_sec = 6;
    int horizon_ticks = 0;
    int ticks_per_min = 10;

    // ---- gridlock management (detection -> early warning -> metering -> logged last-resort relax) ----
    // "Local gridlock propagates everywhere": overload must be surfaced, not silently absorbed.
    enum class GridlockPolicy { report_only, meter, relax, meter_relax };
    GridlockPolicy gridlock_policy = GridlockPolicy::meter_relax;
    int monitor_every = 10;            // ticks between monitor passes (1 min)
    int warn_block_ticks = 50;         // per-link early warning after 5 min continuous storage blocking
    double warn_share = 0.02;          // network early warning when >=2% of physical links are blocked
    double meter_on_share = 0.03;      // origin metering ON at >=3% blocked (hysteresis)
    double meter_off_share = 0.015;    // ... OFF at <=1.5%
    struct GridEvent { int tick; const char* type; int link_id; double value; };
    std::vector<GridEvent> grid_events;
    long long relax_moves = 0;         // storage-bypassing moves (deadlock-cycle breaking, logged)
    long long metered_ticks = 0;       // ticks with origin metering active
    long long vehicles_held = 0;       // agent-ticks held at origins by metering
    int cycles_detected = 0, first_warning_tick = -1;
    double blocked_share_peak = 0;
    bool metering = false, oversaturated = false;

    std::vector<Link> links;
    std::vector<Agent> agents;               // will be sorted by dep_tick (stable by id)
    std::vector<ControlEvent> controls;

    // node partition
    std::vector<std::vector<int>> node_incoming;   // node seq -> incoming link idxs (sorted)

    // stats
    std::vector<std::vector<int>> inflow_per_min;   // [link][minute] entries into ENB
    std::vector<std::vector<int>> exb_per_min;      // [link][minute] EXB size at minute start
    std::vector<std::vector<int>> dep_per_min;      // [link][minute] departures from link (task 4)
    long long completed = 0;
    int last_completion_tick = -1;
    int max_entry_delay_ticks = 0;

    // trajectory logging: event lists for agents with id < traj_max (trajectory IS the event list).
    // Default 1 (agent 0 demo). Raising it is an explicit privacy-level-0 opt-in (see privacy manifest).
    int demo_agent_id = 0;
    int traj_max = 1;
    std::vector<Event> demo_log;

    void init() {
        // node partition: map node ids -> seq, incoming link lists
        std::map<int, int> nseq;
        for (auto& L : links) {
            if (!nseq.count(L.from_node)) nseq[L.from_node] = (int)nseq.size();
            if (!nseq.count(L.to_node)) nseq[L.to_node] = (int)nseq.size();
        }
        node_incoming.assign(nseq.size(), {});
        for (size_t li = 0; li < links.size(); ++li) {
            links[li].from_nseq = nseq[links[li].from_node];
            links[li].to_nseq = nseq[links[li].to_node];
            node_incoming[links[li].to_nseq].push_back((int)li);
        }
        for (auto& v : node_incoming) std::sort(v.begin(), v.end());

        for (auto& L : links) {
            L.fftt_ticks = std::max(1, (int)(L.length_mi / L.free_speed_mph * 3600.0 / tick_sec + 0.5));
            L.storage_cap = L.connector ? 500000000
                                        : std::max(1, (int)(L.kjam * L.length_mi * L.lanes + 0.5));
            L.per_tick_cap = L.cap_per_lane_hr * L.lanes * tick_sec / 3600.0;
            // effective lanes for STORAGE and WAVE: some GMNS exports code lanes=1 with TOTAL capacity
            // (e.g. Chicago Sketch, capacity up to 49,500). Infer physical lanes at ~1800 veh/h/lane so
            // kjam*L*lanes reflects real storage; flow capacity itself is unchanged.
            double cap_total = L.cap_per_lane_hr * L.lanes;
            double eff_lanes = std::max(L.lanes, cap_total / 1800.0);
            L.storage_cap = L.connector ? 500000000
                                        : std::max(1, (int)(L.kjam * L.length_mi * eff_lanes + 0.5));
            // backward wave speed from the triangular FD (per effective lane): w = c/(kjam - c/vf)
            double c_lane = cap_total / eff_lanes;
            double kc = c_lane / std::max(1.0, L.free_speed_mph);
            L.w_mph = (L.kjam - kc) > 1e-6 ? c_lane / (L.kjam - kc) : 12.0;
            L.w_mph = std::min(20.0, std::max(8.0, L.w_mph));
            L.bwtt_ticks = L.connector ? 0
                                       : (int)(L.length_mi / L.w_mph * 3600.0 / tick_sec + 0.5);
            L.cd_hist.assign(L.bwtt_ticks + 2, 0);
            L.cd_lagged = 0;
            // triangular-FD subtlety: at capacity flow the Newell envelope is EXACTLY tight
            // (occ + mu*L/w = kjam*L), so integer rounding causes chronic false blocking.
            // One tick of flow as slack absorbs discretization without changing wave dynamics.
            L.kw_slack = (int)(L.per_tick_cap) + 2;
        }
        std::stable_sort(agents.begin(), agents.end(),
                         [](const Agent& a, const Agent& b) { return a.dep_tick < b.dep_tick; });
        // per-minute stats are O(links x minutes): keep for analysis-scale nets, skip at regional scale
        minute_stats = links.size() <= 10000;
        int mins = minute_stats ? horizon_ticks / ticks_per_min + 2 : 1;
        inflow_per_min.assign(links.size(), std::vector<int>(mins, 0));
        exb_per_min.assign(links.size(), std::vector<int>(mins, 0));
        dep_per_min.assign(links.size(), std::vector<int>(mins, 0));
    }
    bool minute_stats = true;

    void run() {
        build_id_index();
        size_t next_agent = 0;
        std::map<int, std::deque<int>> origin_queue;   // first-link idx -> agent ids (FIFO, deterministic)
        const int nlinks = (int)links.size();
        const int nnodes = (int)node_incoming.size();

        for (int t = 0; t < horizon_ticks; ++t) {
            int minute = t / ticks_per_min;

            // ---- control factors (serial: tiny) ----
            for (auto& L : links) L.cap_factor = 1.0;
            for (const auto& c : controls)
                if (c.link_idx >= 0 && t >= c.start_tick && t < c.end_tick)
                    links[c.link_idx].cap_factor = std::min(links[c.link_idx].cap_factor, c.cap_factor);

            // ---- Task 2: capacity replenishment + lagged CD for KW admission (parallel over links) ----
#pragma omp parallel for schedule(static)
            for (int li = 0; li < nlinks; ++li) {
                Link& L = links[li];
                L.repl_in = L.per_tick_cap * L.cap_factor;
                L.avail_in = L.frac_in + L.repl_in;
                L.avail_out = L.frac_out + L.per_tick_cap * L.cap_factor;
                // CD(t - 1 - BWTT): the DTALite kinemative_wave lagged count (0 before the wave arrives)
                int lag_t = t - 1 - L.bwtt_ticks;
                L.cd_lagged = (L.bwtt_ticks <= 0) ? L.cum_departure
                              : (lag_t < 0 ? 0 : L.cd_hist[lag_t % (L.bwtt_ticks + 2)]);
            }

            // ---- Task 1: loading (serial; origins are cheap and FIFO-deterministic) ----
            while (next_agent < agents.size() && agents[next_agent].dep_tick <= t) {
                const Agent& a = agents[next_agent];
                origin_queue[a.path_links.front()].push_back(a.id);
                ++next_agent;
            }
            if (metering) {   // origin metering: hold demand at origins while the network is critical
                ++metered_ticks;
                for (auto& [li, q] : origin_queue) vehicles_held += (long long)q.size();
            } else
            for (auto& [li, q] : origin_queue) {
                Link& L = links[li];
                while (!q.empty() && L.cum_arrival - L.cd_lagged < L.storage_cap + L.kw_slack) {  // KW envelope
                    int aid = q.front(); q.pop_front();
                    Agent& a = agents_by_id(aid);
                    a.entry_tick = t;
                    max_entry_delay_ticks = std::max(max_entry_delay_ticks, t - a.dep_tick);
                    L.enb.push_back({aid, t + L.fftt_ticks});
                    ++L.cum_arrival;
                    if (minute_stats) inflow_per_min[li][minute]++;
                    log_demo(aid, li, t, BufferType::ENB, TrafficState::free_flow);
                }
            }

            // ---- Task 3: allocation + QVDF drop (parallel over DOWNSTREAM links; single writer) ----
#pragma omp parallel for schedule(static)
            for (int di = 0; di < nlinks; ++di) {
                Link& D = links[di];
                D.alloc_from.clear();
                double request_total = 0;
                for (int u : node_incoming[D.from_nseq]) {
                    auto it = links[u].exb_next_count.find(di);
                    if (it != links[u].exb_next_count.end() && it->second > 0)
                        request_total += it->second;
                }
                if (request_total <= 0) continue;
                // QVDF capacity drop: persistent queue waiting to enter -> discharge mu = C / f_d
                if (D.dmodel == 1 && D.qvdf_fd > 1.0 && request_total >= std::max(2.0, D.per_tick_cap))
                    D.avail_in -= D.repl_in * (1.0 - 1.0 / D.qvdf_fd);
                for (int u : node_incoming[D.from_nseq]) {
                    auto it = links[u].exb_next_count.find(di);
                    if (it == links[u].exb_next_count.end() || it->second <= 0) continue;
                    double n = it->second;
                    double share = (request_total <= D.avail_in) ? n : D.avail_in * n / request_total;
                    double carry = 0;
                    auto ic = D.carry_from.find(u);
                    if (ic != D.carry_from.end()) carry = ic->second;
                    D.alloc_from[u] = share + carry;
                }
            }

            // ---- Task 4: node transfer (parallel over NODES; node owns its in-EXBs / out-ENBs) ----
            bool allow_relax = (gridlock_policy == GridlockPolicy::relax ||
                                gridlock_policy == GridlockPolicy::meter_relax);
            long long comp_add = 0, relax_add = 0;
#pragma omp parallel for schedule(dynamic, 64) reduction(+ : comp_add, relax_add)
            for (int ni = 0; ni < nnodes; ++ni) {
                for (int li : node_incoming[ni]) {
                    Link& U = links[li];
                    // relaxation ONLY for members of a DETECTED deadlock cycle (logged last resort)
                    bool relax = allow_relax && U.in_cycle;
                    bool storage_blocked_now = false;
                    U.blocked_by = -1;
                    while (!U.exb.empty()) {
                        int aid = U.exb.front();
                        Agent& a = agents_by_id(aid);
                        bool at_dest = (a.path_pos + 1 >= (int)a.path_links.size());
                        if (at_dest) {
                            if (U.avail_out < 1.0) break;
                            U.exb.pop_front(); U.exb_next_count[-1]--;
                            U.avail_out -= 1.0;
                            ++U.cum_departure; if (minute_stats) dep_per_min[li][t / ticks_per_min]++;
                            a.completion_tick = t; ++comp_add;
                            log_demo(aid, li, t, BufferType::EXB, TrafficState::completed);
                        } else {
                            int di = a.path_links[a.path_pos + 1];
                            Link& D = links[di];
                            auto ia = D.alloc_from.find(li);
                            double& alloc = ia != D.alloc_from.end() ? ia->second : dummy_alloc_;
                            if (U.avail_out < 1.0 || D.avail_in < 1.0 || alloc < 1.0)
                                break;  // capacity blocking never relaxes
                            if (D.cum_arrival - D.cd_lagged >= D.storage_cap + D.kw_slack) {  // KW envelope
                                // (CA owned by this node's thread; cd_lagged fixed for the tick)
                                if (!relax) {
                                    storage_blocked_now = true;
                                    U.blocked_by = di;   // functional blocked-by edge (deadlock = cycle)
                                    break;  // FIFO spillback (storage binds; snapshot, deterministic)
                                }
                                ++relax_add;             // storage bypass: counted + reported, never silent
                            }
                            U.exb.pop_front(); U.exb_next_count[di]--;
                            U.avail_out -= 1.0; D.avail_in -= 1.0; alloc -= 1.0;
                            ++U.cum_departure; ++D.cum_arrival;
                            if (minute_stats) dep_per_min[li][t / ticks_per_min]++;
                            a.path_pos += 1;
                            D.enb.push_back({aid, t + D.fftt_ticks});
                            if (minute_stats) inflow_per_min[di][t / ticks_per_min]++;
                            log_demo(aid, di, t, BufferType::ENB, TrafficState::free_flow);
                        }
                    }
                    U.storage_block_ticks = storage_blocked_now ? U.storage_block_ticks + 1 : 0;
                }
            }
            if (comp_add > 0) { completed += comp_add; last_completion_tick = t; }
            relax_moves += relax_add;

            // ---- gridlock monitor (serial, deterministic): detect -> warn early -> meter ----
            if (t % monitor_every == 0) gridlock_monitor(t);

            // ---- Task 5: link transfer (parallel over links) ----
#pragma omp parallel for schedule(static)
            for (int li = 0; li < nlinks; ++li) {
                Link& L = links[li];
                while (!L.enb.empty() && L.enb.front().ready_tick <= t) {
                    int aid = L.enb.front().agent; L.enb.pop_front();
                    Agent& a = agents_by_id(aid);
                    int next = (a.path_pos + 1 < (int)a.path_links.size()) ? a.path_links[a.path_pos + 1] : -1;
                    L.exb.push_back(aid);
                    L.exb_next_count[next]++;
                    log_demo(aid, li, t, BufferType::EXB,
                             L.exb.size() > 1 ? TrafficState::queued : TrafficState::discharging);
                }
            }

            // ---- end of tick: carries + stats (parallel over links) ----
#pragma omp parallel for schedule(static)
            for (int li = 0; li < nlinks; ++li) {
                Link& L = links[li];
                L.frac_in = std::min(L.avail_in, 1.0);
                L.frac_out = std::min(L.avail_out, 1.0);
                // merge fractional carries (< 1 veh per upstream; decay when no one is waiting)
                L.carry_from.clear();
                for (auto& [u, rem] : L.alloc_from) {
                    auto it = links[u].exb_next_count.find(li);
                    if (it != links[u].exb_next_count.end() && it->second > 0)
                        L.carry_from[u] = std::min(rem, 1.0);
                }
                if (L.bwtt_ticks > 0) L.cd_hist[t % (L.bwtt_ticks + 2)] = L.cum_departure;  // KW ring
                // congestion-duration KPI: episode = persistent EXB queue (PAQ: P = t3 - t0, mu = D/P).
                // Hysteresis: onset when the queue exceeds ~2 ticks of capacity (real breakdown, not
                // tick-discretization bunching); clear when it drains below ~half a tick of capacity.
                {
                    int q_hi = std::max(5, (int)(2.0 * L.per_tick_cap));
                    int q_lo = std::max(1, (int)(0.5 * L.per_tick_cap));
                    int q = (int)L.exb.size();
                    if (L.cong_onset_tick < 0 && q >= q_hi) {
                        L.cong_onset_tick = t; L.cong_onset_dep = L.cum_departure; L.cong_max_q = q;
                    } else if (L.cong_onset_tick >= 0) {
                        L.cong_max_q = std::max(L.cong_max_q, q);
                        if (q <= q_lo) {                                  // episode clears
                            if (t - L.cong_onset_tick >= 50)              // record if P >= 5 min
                                L.cong_episodes.push_back({L.cong_onset_tick, t,
                                                           L.cum_departure - L.cong_onset_dep,
                                                           L.cong_max_q});
                            L.cong_onset_tick = -1; L.cong_max_q = 0;
                        }
                    }
                }
                L.max_occupancy = std::max(L.max_occupancy, L.occupancy());
                L.max_exb = std::max(L.max_exb, (int)L.exb.size());
                if (minute_stats && t % ticks_per_min == 0) exb_per_min[li][minute] = (int)L.exb.size();
            }
        }
        close_open_episodes();
    }

    void close_open_episodes() {   // censored episodes still running at the horizon
        for (auto& L : links)
            if (L.cong_onset_tick >= 0 && horizon_ticks - L.cong_onset_tick >= 50)
                L.cong_episodes.push_back({L.cong_onset_tick, horizon_ticks,
                                           L.cum_departure - L.cong_onset_dep, L.cong_max_q});
    }

    Agent& agents_by_id(int aid) { return agents[id_index_[aid]]; }
    void build_id_index() {
        id_index_.assign(agents.size(), 0);
        for (size_t i = 0; i < agents.size(); ++i) id_index_[agents[i].id] = (int)i;
    }
    int threads() const {
#ifdef _OPENMP
        return omp_get_max_threads();
#else
        return 1;
#endif
    }

    // detection: per-link warnings, blocked-share warning, deadlock-cycle detection on the
    // blocked_by functional graph (each blocked link points at exactly one blocker -> cycles are
    // found in O(#blocked) with the standard 3-color walk), metering hysteresis.
    void gridlock_monitor(int t) {
        // KW note: instantaneous storage gating is NORMAL operation (the envelope binds for a few
        // ticks while the release wave travels). Gridlock indicators count only PERSISTENT blocking.
        const int persist = 30;   // >= 3 min continuously blocked
        int blocked = 0, physical = 0;
        for (auto& L : links) {
            if (L.connector) continue;
            ++physical;
            if (L.blocked_by >= 0 && L.storage_block_ticks >= persist) ++blocked;
            if (L.blocked_by >= 0 && L.storage_block_ticks >= warn_block_ticks && !L.warned) {
                L.warned = true;
                grid_events.push_back({t, "blocked_link_warning", L.id, (double)L.storage_block_ticks});
                if (first_warning_tick < 0) first_warning_tick = t;
            }
            if (L.blocked_by < 0) L.warned = false;
        }
        double share = physical ? (double)blocked / physical : 0.0;
        blocked_share_peak = std::max(blocked_share_peak, share);
        if (share >= warn_share && (grid_events.empty() ||
            std::string(grid_events.back().type) != "network_congestion_warning" ||
            t - grid_events.back().tick > 50)) {
            grid_events.push_back({t, "network_congestion_warning", -1, share});
            if (first_warning_tick < 0) first_warning_tick = t;
        }
        // deadlock cycles: 3-color walk on blocked_by
        for (auto& L : links) L.in_cycle = false;
        std::vector<int8_t> color(links.size(), 0);          // 0 white, 1 gray, 2 black
        for (size_t s = 0; s < links.size(); ++s) {
            if (color[s] != 0 || links[s].blocked_by < 0) continue;
            std::vector<int> path; int u = (int)s;
            while (u >= 0 && color[u] == 0 && links[u].blocked_by >= 0) {
                color[u] = 1; path.push_back(u); u = links[u].blocked_by;
            }
            if (u >= 0 && color[u] == 1) {                   // found a new cycle: mark members
                ++cycles_detected;
                grid_events.push_back({t, "deadlock_cycle_detected", links[u].id, 0.0});
                if (first_warning_tick < 0) first_warning_tick = t;
                bool in = false;
                for (int v : path) { if (v == u) in = true; if (in) links[v].in_cycle = true; }
            }
            for (int v : path) color[v] = 2;
        }
        // metering hysteresis
        if (gridlock_policy == GridlockPolicy::meter || gridlock_policy == GridlockPolicy::meter_relax) {
            if (!metering && share >= meter_on_share) {
                metering = true; grid_events.push_back({t, "origin_metering_on", -1, share});
            } else if (metering && share <= meter_off_share) {
                metering = false; grid_events.push_back({t, "origin_metering_off", -1, share});
            }
        }
    }

public:
    void finalize_flags() {
        long long moves = 0;
        for (auto& L : links) moves += L.cum_departure;
        oversaturated = (blocked_share_peak >= 0.05) || (relax_moves > moves / 1000) ||
                        (completed < (long long)agents.size());
    }

private:
    std::vector<int> id_index_;
    double dummy_alloc_ = 0.0;   // for downstream links with no allocation entry (never eligible)
    void log_demo(int aid, int link, int t, BufferType b, TrafficState s) {
        if (aid >= traj_max && aid != demo_agent_id) return;
#ifdef _OPENMP
#pragma omp critical(dlsim_demo)
#endif
        demo_log.push_back({aid, link, t, b, s,
                            links[link].cap_factor < 0.999 ? ControlState::incident : ControlState::none});
    }
};

}  // namespace ste

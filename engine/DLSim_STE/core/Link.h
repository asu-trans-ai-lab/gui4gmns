// DLSim STE kernel — Link with the paper's double-buffer representation:
//   ENB (entrance buffer): agents traversing; ready at arrival_tick + FFTT   (Newell V(t)=A(t-FFTT))
//   EXB (exit buffer):     agents waiting for downstream in-capacity / storage
// Storage constraint (spillback): occupancy = |ENB|+|EXB| <= kjam*length*lanes.
#pragma once
#include <cstdint>
#include <deque>
#include <map>
#include <vector>

namespace ste {

struct EnbEntry { int agent; int ready_tick; };

struct Link {
    // identity / supply encoding (spec §1)
    int id = 0, from_node = 0, to_node = 0;
    double lanes = 1, cap_per_lane_hr = 1800, free_speed_mph = 60, length_mi = 1, kjam = 180;
    bool connector = false;   // centroid connector: no physical storage constraint

    // derived
    int fftt_ticks = 1;            // free-flow travel time in ticks
    int storage_cap = 9999999;     // kjam * length * lanes (veh)
    double per_tick_cap = 1;       // capacity (all lanes) per tick, veh

    // discharge model (encoding spec §4): 0 = newell_kw (constant capacity), 1 = qvdf (capacity drop:
    // while a persistent queue waits to enter, discharge mu = C / f_d < C)
    int dmodel = 0;
    double qvdf_fd = 1.0;                  // f_d > 1 activates the drop

    // per-tick capacity state (fractional-carry discharge; carry < 1 veh, no bursts)
    double avail_in = 0, avail_out = 0;    // this tick's usable capacity
    double repl_in = 0;                    // this tick's in-capacity replenishment (pre-drop)
    double frac_in = 0, frac_out = 0;      // fractional carry to next tick
    double cap_factor = 1.0;               // control-modified factor (incident/work zone)

    // buffers
    std::deque<EnbEntry> enb;
    std::deque<int> exb;
    std::map<int, int> exb_next_count;   // next-link idx (-1 = destination) -> waiting agents in EXB

    // merge allocation, stored on the DOWNSTREAM link (single-writer ownership for parallel Task 3/4:
    // written in Task 3 by this link's iteration, read/decremented in Task 4 by this link's from-node)
    std::map<int, double> alloc_from;    // upstream link idx -> this tick's allocation
    std::map<int, double> carry_from;    // upstream link idx -> fractional carry (< 1 veh)

    // node partition (filled by Scheduler::init)
    int from_nseq = -1, to_nseq = -1;

    // gridlock management: consecutive ticks storage-blocked; who blocks the FIFO head (functional
    // graph -> deadlock = a cycle of blocked_by edges); cycle membership set by the monitor
    int storage_block_ticks = 0;
    int blocked_by = -1;          // downstream link idx whose storage blocks this link's head (per tick)
    bool in_cycle = false;        // member of a detected deadlock cycle (eligible for logged relaxation)
    bool warned = false;          // per-link early-warning emitted (throttle)

    // Newell kinematic-wave storage (F2, DTALite kinemative_wave completed): admission requires
    //   CA(t) - CD(t - 1 - BWTT) < kjam * L * lanes        [V(t) = D(t - L/w) + kjam*L envelope]
    // so space vacated downstream only becomes available at the entrance after the backward wave
    // (speed w) arrives. cd_hist is a per-tick ring of cumulative departures (owner-written).
    int bwtt_ticks = 0;                  // L / w in ticks
    double w_mph = 12.0;                 // backward wave speed (triangular FD: w = c/(kjam - c/vf))
    std::vector<long long> cd_hist;      // ring buffer, size bwtt_ticks + 2
    long long cd_lagged = 0;             // CD(t - 1 - BWTT), refreshed each tick in Task 2
    int kw_slack = 2;                    // discretization slack (~1 tick of flow); see Scheduler::init

    // congestion-duration KPI (PAQ / QVDF: P = t3 - t0, D = departures within P, mu = D/P).
    // Episode = persistent EXB queue; owner-written in the end-of-tick pass (race-free).
    struct CongEpisode { int onset_tick, clear_tick; long long D; int max_queue; };
    std::vector<CongEpisode> cong_episodes;
    int cong_onset_tick = -1;            // -1 = not in an episode
    long long cong_onset_dep = 0;        // cum_departure at onset
    int cong_max_q = 0;

    // cumulative counts (sparse A/D curves come from these in phase 2)
    long long cum_arrival = 0, cum_departure = 0;
    int max_occupancy = 0, max_exb = 0;

    int occupancy() const { return static_cast<int>(enb.size() + exb.size()); }
};

}  // namespace ste

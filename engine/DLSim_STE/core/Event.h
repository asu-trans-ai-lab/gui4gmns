// DLSim STE kernel — Event: the atom of the space-time-event encoding.
// e = (agent, link, tick, buffer, traffic_state, control_state)   [spec §3]
#pragma once
#include <cstdint>

namespace ste {

enum class BufferType : uint8_t { ENB = 0, EXB = 1 };
enum class TrafficState : uint8_t { free_flow, queued, discharging, blocked, completed };
enum class ControlState : uint8_t { none, signal, ramp_metering, lane_control,
                                    incident, work_zone, pricing, guidance };

struct Event {
    int32_t agent;
    int32_t link;          // link seq index (-1 = network boundary)
    int32_t tick;          // integer tick; sub-tick offset per spec D3 (phase-2)
    BufferType buffer;
    TrafficState tstate;
    ControlState cstate;
};

}  // namespace ste

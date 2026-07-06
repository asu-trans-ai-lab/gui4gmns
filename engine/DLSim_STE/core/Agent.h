// DLSim STE kernel — Agent: id + path + schedule. A trajectory IS the agent's event list.
#pragma once
#include <cstdint>
#include <vector>

namespace ste {

struct Agent {
    int32_t id = -1;
    std::vector<int> path_links;   // link seq indices, origin -> destination
    int path_pos = 0;              // current position in path_links
    int dep_tick = 0;              // scheduled departure (from phi(t) profile)
    int entry_tick = -1;           // actual network entry (> dep_tick if loading blocked)
    int completion_tick = -1;      // -1 = not completed
};

}  // namespace ste

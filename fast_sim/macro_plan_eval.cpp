// Evaluate a small vocabulary of inference-legal reactive task graphs from a
// replay checkpoint.  Both seats generate actions from their own farm and the
// shared market on every simulated turn.  Recorded actions are used only to
// reconstruct the checkpoint root; no future action tape enters a branch.
#include "sim.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

using namespace kag;

struct Turn { Action action[2]; };

struct Particle {
    std::string label;
    int value[N_ITEMS + N_CROPS] = {0};
    bool oracle = false;
};

struct MacroPlan {
    const char* name;
    int crop;
    int animal;
    bool liquidate;
    bool fertilize;
    bool expand;
    int target_hires;
};

static constexpr MacroPlan PLANS[] = {
    {"maintain",       -1,         -1,    false, false, false, 1},
    {"liquidate",      -1,         -1,    true,  false, false, 0},
    {"wheat_cycle",    WHEAT,      -1,    false, false, true,  3},
    {"carrot_cycle",   CARROT,     -1,    false, true,  true,  3},
    {"strawberry_cycle", STRAWBERRY, -1,  false, true,  true,  3},
    {"melon_cycle",    MELON,      -1,    false, true,  true,  3},
    {"goose_route",    WHEAT,      GOOSE, false, false, true,  4},
    {"cow_route",      WHEAT,      COW,   false, false, true,  4},
    {"sheep_route",    WHEAT,      SHEEP, false, false, true,  4},
};

static void read_config(std::istream& input, Config& config) {
    const std::streampos position = input.tellg();
    std::string token;
    if (!(input >> token)) return;
    if (token != "CONFIG") {
        input.clear();
        input.seekg(position);
        return;
    }
    input >> config.episode_steps >> config.board_size
          >> config.starting_money >> config.max_orders
          >> config.turns_per_day >> config.shed_capacity
          >> config.weed_chance >> config.shop_unlock_interval
          >> config.shop_sell_interval >> config.center_sell_interval
          >> config.hire_mult;
}

static bool load_trace(
    const std::string& path,
    uint64_t& seed,
    Config& config,
    std::vector<Turn>& turns
) {
    std::ifstream input(path);
    if (!input) return false;
    int count = 0;
    if (!(input >> seed >> count) || count <= 0) return false;
    read_config(input, config);
    turns.resize(count);
    for (int step = 0; step < count; ++step) {
        for (int player = 0; player < 2; ++player) {
            int unit_count = 0, order_count = 0;
            input >> unit_count >> order_count;
            Action& action = turns[step].action[player];
            action.n_units = std::min(unit_count, MAX_UNITS);
            for (int index = 0; index < unit_count; ++index) {
                int op = 0, arg = 0, amount = 0;
                input >> op >> arg >> amount;
                if (index < MAX_UNITS) {
                    action.units[index] = {
                        static_cast<uint8_t>(op),
                        static_cast<uint8_t>(arg),
                        static_cast<int16_t>(amount),
                    };
                }
            }
            action.n_orders = std::min(order_count, 16);
            for (int index = 0; index < order_count; ++index) {
                int op = 0, item = 0, amount = 0;
                input >> op >> item >> amount;
                if (index < 16) {
                    action.orders[index] = {
                        static_cast<uint8_t>(op),
                        static_cast<uint8_t>(item),
                        amount,
                    };
                }
            }
        }
    }
    return static_cast<bool>(input);
}

static bool load_particles(const std::string& path, std::vector<Particle>& rows) {
    std::ifstream input(path);
    if (!input) return false;
    Particle particle;
    while (input >> particle.label) {
        particle.oracle = particle.label == "oracle";
        for (int index = 0; index < N_ITEMS + N_CROPS; ++index) {
            if (!(input >> particle.value[index])) return false;
        }
        rows.push_back(particle);
        particle = Particle{};
    }
    return !rows.empty();
}

static std::vector<uint64_t> parse_seeds(const std::string& values) {
    std::vector<uint64_t> result;
    std::stringstream input(values);
    std::string token;
    while (std::getline(input, token, ',')) {
        if (!token.empty()) result.push_back(std::strtoull(token.c_str(), nullptr, 10));
    }
    return result;
}

static int inventory_total(const Farm& farm, int unit) {
    int total = 0;
    for (int item = 0; item < N_ITEMS; ++item) total += farm.inv[unit][item];
    return total;
}

static int farm_item_total(const Farm& farm, int item) {
    int total = farm.shed[item];
    for (int unit = 0; unit < farm.n_units; ++unit) total += farm.inv[unit][item];
    return total;
}

static int board_animal_count(const Farm& farm, int animal) {
    int count = 0;
    for (int y = 0; y < BOARD; ++y)
        for (int x = 0; x < BOARD; ++x)
            count += farm.tiles[y][x].has_animal && farm.tiles[y][x].what == animal;
    return count;
}

static int empty_structure_count(const Farm& farm, int animal) {
    const TileKind wanted = animal == GOOSE ? T_COOP : T_PASTURE;
    int count = 0;
    for (int y = 0; y < BOARD; ++y)
        for (int x = 0; x < BOARD; ++x) {
            const Tile& tile = farm.tiles[y][x];
            count += tile.kind == wanted && !tile.has_animal;
        }
    return count;
}

static int animal_count(const Farm& farm) {
    int count = 0;
    for (int animal = GOOSE; animal <= SHEEP; ++animal)
        count += board_animal_count(farm, animal);
    return count;
}

static UnitAction move_toward(int x, int y, int tx, int ty) {
    if (x < tx) return {OP_EAST, 0, 1};
    if (x > tx) return {OP_WEST, 0, 1};
    if (y < ty) return {OP_SOUTH, 0, 1};
    if (y > ty) return {OP_NORTH, 0, 1};
    return UnitAction{};
}

static void nearest_shed(int x, int y, int& tx, int& ty) {
    static constexpr int access[4][2] = {{4,4},{5,4},{4,5},{5,5}};
    int best = std::numeric_limits<int>::max();
    tx = 4; ty = 4;
    for (const auto& point : access) {
        const int distance = std::abs(x - point[0]) + std::abs(y - point[1]);
        if (distance < best) { best = distance; tx = point[0]; ty = point[1]; }
    }
}

struct Task {
    int x = 0, y = 0;
    int priority = -1;
    UnitAction action{};
};

static bool better_task(const Task& candidate, const Task& best, int x, int y) {
    if (candidate.priority != best.priority) return candidate.priority > best.priority;
    const int candidate_distance = std::abs(x - candidate.x) + std::abs(y - candidate.y);
    const int best_distance = std::abs(x - best.x) + std::abs(y - best.y);
    if (candidate_distance != best_distance) return candidate_distance < best_distance;
    return candidate.y < best.y || (candidate.y == best.y && candidate.x < best.x);
}

static bool mature_plant(const Tile& tile, int day) {
    return tile.kind == T_PLANT &&
           day - tile.planted_day >= CROPS[tile.what].first_yield_day;
}

static Task choose_field_task(
    const Farm& farm,
    const MacroPlan& plan,
    int unit,
    int day,
    bool claimed[BOARD][BOARD],
    int remaining_seed[N_CROPS]
) {
    const int ux = farm.pos_x[unit], uy = farm.pos_y[unit];
    const bool has_wheat = farm.inv[unit][WHEAT] > 0;
    const bool has_fertilizer = farm.inv[unit][FERTILIZER] > 0;
    Task best;
    for (int y = 0; y < BOARD; ++y) {
        for (int x = 0; x < BOARD; ++x) {
            if (claimed[y][x]) continue;
            const Tile& tile = farm.tiles[y][x];
            Task task; task.x = x; task.y = y;
            if (tile.has_animal) {
                const int bonus = tile.what == plan.animal ? 12 : 0;
                if (!tile.fed_today && has_wheat) {
                    task.priority = 100 + bonus; task.action = {OP_FEED, 0, 1};
                } else if (tile.yield_units > 0) {
                    task.priority = 94 + bonus; task.action = {OP_HARVEST, 0, 1};
                } else if (tile.fertilizer_available) {
                    task.priority = 82 + bonus; task.action = {OP_COLLECT_FERTILIZER, 0, 1};
                } else if (!tile.cared_today) {
                    task.priority = 74 + bonus; task.action = {OP_CARE, 0, 1};
                }
            } else if (tile.kind == T_PLANT) {
                const int bonus = tile.what == plan.crop ? 10 : 0;
                if (tile.yield_units > 0 && mature_plant(tile, day)) {
                    task.priority = (plan.liquidate ? 105 : 92) + bonus;
                    task.action = {OP_HARVEST, 0, 1};
                }
                if (!tile.watered_today && 88 + bonus > task.priority) {
                    task.priority = 88 + bonus; task.action = {OP_WATER, 0, 1};
                }
                if (plan.fertilize && has_fertilizer &&
                    tile.what == plan.crop && tile.fertilized_until_day < day &&
                    84 + bonus > task.priority) {
                    task.priority = 84 + bonus; task.action = {OP_FERTILIZE, FERTILIZER, 1};
                }
            } else if (tile.kind == T_WEED) {
                task.priority = 86; task.action = {OP_DIG, 0, 1};
            } else if ((tile.kind == T_COOP || tile.kind == T_PASTURE) &&
                       !tile.has_animal && plan.animal >= 0 &&
                       farm.inv[unit][plan.animal] > 0 &&
                       tile.kind == (plan.animal == GOOSE ? T_COOP : T_PASTURE)) {
                task.priority = 98; task.action = {OP_PLACE, static_cast<uint8_t>(plan.animal), 1};
            } else if (tile.kind == T_EMPTY && plan.crop >= 0 &&
                       remaining_seed[plan.crop] > 0) {
                task.priority = 52;
                task.action = {OP_PLANT, static_cast<uint8_t>(plan.crop), 1};
            } else if (tile.kind == T_EMPTY && plan.animal >= 0 &&
                       empty_structure_count(farm, plan.animal) == 0 &&
                       farm_item_total(farm, plan.animal) > 0) {
                task.priority = 48;
                task.action = {
                    static_cast<uint8_t>(plan.animal == GOOSE ? OP_BUILD_COOP : OP_BUILD_PASTURE),
                    0, 1
                };
            }
            if (task.priority >= 0 && better_task(task, best, ux, uy)) best = task;
        }
    }
    return best;
}

static Action reactive_action(const Sim& sim, int seat, const MacroPlan& plan) {
    const Farm& farm = sim.st.farms[seat];
    Action action;
    action.clear();
    action.n_units = std::min(farm.n_units, MAX_UNITS);
    bool claimed[BOARD][BOARD] = {{false}};
    int remaining_seed[N_CROPS];
    for (int crop = 0; crop < N_CROPS; ++crop) remaining_seed[crop] = farm.seeds[crop];

    int unfed = 0;
    for (int y = 0; y < BOARD; ++y)
        for (int x = 0; x < BOARD; ++x)
            unfed += farm.tiles[y][x].has_animal && !farm.tiles[y][x].fed_today;

    for (int unit = 0; unit < action.n_units; ++unit) {
        const int x = farm.pos_x[unit], y = farm.pos_y[unit];
        const int carried = inventory_total(farm, unit);
        const bool useful_wheat = farm.inv[unit][WHEAT] > 0 && unfed > 0;
        const bool useful_animal = plan.animal >= 0 && farm.inv[unit][plan.animal] > 0;
        const bool useful_fertilizer = plan.fertilize && farm.inv[unit][FERTILIZER] > 0;

        if (carried > 0 && !useful_wheat && !useful_animal && !useful_fertilizer) {
            if (is_shed_adjacent(x, y, sim.cfg.board_size)) {
                action.units[unit] = {OP_DROP, 0, 1};
            } else {
                int tx = 0, ty = 0; nearest_shed(x, y, tx, ty);
                action.units[unit] = move_toward(x, y, tx, ty);
            }
            continue;
        }

        if (carried == 0 && is_shed_adjacent(x, y, sim.cfg.board_size)) {
            if (unfed > 0 && farm.shed[WHEAT] > 0) {
                action.units[unit] = {
                    OP_PICKUP, WHEAT,
                    static_cast<int16_t>(std::min<int>(8, farm.shed[WHEAT]))
                };
                continue;
            }
            if (plan.animal >= 0 && farm.shed[plan.animal] > 0 &&
                empty_structure_count(farm, plan.animal) > 0) {
                action.units[unit] = {OP_PICKUP, static_cast<uint8_t>(plan.animal), 1};
                continue;
            }
            if (plan.fertilize && farm.shed[FERTILIZER] > 0) {
                action.units[unit] = {OP_PICKUP, FERTILIZER, 1};
                continue;
            }
        }

        if (carried == 0 && unfed > 0 && farm.shed[WHEAT] > 0) {
            int tx = 0, ty = 0; nearest_shed(x, y, tx, ty);
            action.units[unit] = move_toward(x, y, tx, ty);
            continue;
        }

        Task task = choose_field_task(
            farm, plan, unit, sim.st.day, claimed, remaining_seed
        );
        if (task.priority >= 0) {
            claimed[task.y][task.x] = true;
            if (x == task.x && y == task.y) {
                action.units[unit] = task.action;
                if (task.action.op == OP_PLANT && task.action.arg < N_CROPS)
                    remaining_seed[task.action.arg]--;
            } else {
                action.units[unit] = move_toward(x, y, task.x, task.y);
            }
        }
    }

    struct Sale { int item; int value; };
    std::vector<Sale> sales;
    const int wheat_reserve = plan.animal >= 0 ? std::max(4, animal_count(farm) * 2) : 0;
    for (int item = 0; item < N_PRODUCTS; ++item) {
        int quantity = farm.shed[item];
        if (item == WHEAT) quantity = std::max(0, quantity - wheat_reserve);
        if (quantity > 0) sales.push_back({item, quantity * sim.st.market.prices[item]});
    }
    std::sort(sales.begin(), sales.end(), [](const Sale& left, const Sale& right) {
        if (left.value != right.value) return left.value > right.value;
        return left.item < right.item;
    });
    const int sale_limit = plan.liquidate ? 8 : 4;
    for (int index = 0; index < static_cast<int>(sales.size()) && index < sale_limit; ++index) {
        const int item = sales[index].item;
        int quantity = farm.shed[item];
        if (item == WHEAT) quantity = std::max(0, quantity - wheat_reserve);
        action.orders[action.n_orders++] = {M_SELL, static_cast<uint8_t>(item), quantity};
    }

    if (!plan.liquidate) {
        int added_hires = 0;
        while (action.n_orders < 16 &&
               farm.hires_today + added_hires < plan.target_hires &&
               action.n_orders < sim.cfg.max_orders) {
            action.orders[action.n_orders++] = {M_HIRE, 0, 1};
            added_hires++;
        }
        if (plan.expand && farm.n_quadrants < 4 && farm.money > 5000 &&
            action.n_orders < sim.cfg.max_orders)
            action.orders[action.n_orders++] = {M_BUY_LAND, 0, 1};
        if (plan.crop >= 0 && farm.seeds[plan.crop] < 4 &&
            action.n_orders < sim.cfg.max_orders) {
            action.orders[action.n_orders++] = {
                M_BUY_SEED, static_cast<uint8_t>(plan.crop), 4 - farm.seeds[plan.crop]
            };
        }
        if (plan.animal >= 0 &&
            board_animal_count(farm, plan.animal) + farm_item_total(farm, plan.animal) < 2 &&
            action.n_orders < sim.cfg.max_orders)
            action.orders[action.n_orders++] = {M_BUY_ANIMAL, static_cast<uint8_t>(plan.animal), 1};
        const int wheat_need = std::max(0, animal_count(farm) * 3 - farm_item_total(farm, WHEAT));
        if (wheat_need > 0 && action.n_orders < sim.cfg.max_orders)
            action.orders[action.n_orders++] = {M_BUY_PRODUCT, WHEAT, wheat_need};
        if (plan.fertilize && farm_item_total(farm, FERTILIZER) < 2 &&
            action.n_orders < sim.cfg.max_orders)
            action.orders[action.n_orders++] = {M_BUY_PRODUCT, FERTILIZER, 2};
    }
    return action;
}

static double item_unit_value(const State& state, int item) {
    if (item < N_PRODUCTS) return state.market.prices[item];
    return ANIMALS[item - GOOSE].cost * 0.75;
}

static double farm_value(const Sim& sim, int seat) {
    const Farm& farm = sim.st.farms[seat];
    double value = farm.money;
    for (int item = 0; item < N_ITEMS; ++item) {
        int quantity = farm.shed[item];
        for (int unit = 0; unit < farm.n_units; ++unit) quantity += farm.inv[unit][item];
        value += quantity * item_unit_value(sim.st, item) * 0.90;
    }
    for (int crop = 0; crop < N_CROPS; ++crop)
        value += farm.seeds[crop] * CROPS[crop].seed * 0.45;
    for (int y = 0; y < BOARD; ++y) {
        for (int x = 0; x < BOARD; ++x) {
            const Tile& tile = farm.tiles[y][x];
            if (tile.kind == T_PLANT) {
                value += tile.yield_units * sim.st.market.prices[tile.what] * 0.85;
                value += CROPS[tile.what].max_yield * sim.st.market.prices[tile.what] *
                         (CROPS[tile.what].ongoing ? 0.80 : 0.25);
            } else if (tile.has_animal) {
                const AnimalDef& animal = ANIMALS[tile.what - GOOSE];
                value += animal.cost * 0.65;
                value += tile.yield_units * sim.st.market.prices[animal.product] * 0.85;
                value += sim.st.market.prices[animal.product] * 1.5;
            } else if (tile.kind == T_COOP || tile.kind == T_PASTURE) {
                value += 40.0;
            }
        }
    }
    return value;
}

static void apply_particle(Sim& sim, int opponent, const Particle& particle) {
    if (particle.oracle) return;
    Farm& farm = sim.st.farms[opponent];
    farm.shed_total = 0;
    for (int item = 0; item < N_ITEMS; ++item) {
        farm.shed[item] = static_cast<int16_t>(std::max(0, particle.value[item]));
        farm.shed_total += farm.shed[item];
    }
    for (int crop = 0; crop < N_CROPS; ++crop)
        farm.seeds[crop] = static_cast<int16_t>(std::max(0, particle.value[N_ITEMS + crop]));
}

static void emit_rollout(
    const Sim& original,
    const std::vector<Turn>& turns,
    const Particle& particle,
    int prefix,
    int horizon,
    int seat,
    uint64_t future_seed,
    const MacroPlan& plan,
    const MacroPlan& opponent_plan
) {
    Sim branch = original;
    apply_particle(branch, 1 - seat, particle);
    branch.cfg.seed = future_seed;
    const double own_start = farm_value(branch, seat);
    const double opponent_start = farm_value(branch, 1 - seat);
    const int stop = std::min<int>(prefix + horizon, turns.size());
    for (int step = prefix; step < stop; ++step) {
        Action actions[2];
        actions[seat] = reactive_action(branch, seat, plan);
        actions[1 - seat] = reactive_action(branch, 1 - seat, opponent_plan);
        branch.step(actions[0], actions[1]);
    }
    const double own_end = farm_value(branch, seat);
    const double opponent_end = farm_value(branch, 1 - seat);
    const double score = (own_end - own_start) - (opponent_end - opponent_start);
    const double money_delta =
        (branch.st.farms[seat].money - original.st.farms[seat].money) -
        (branch.st.farms[1 - seat].money - original.st.farms[1 - seat].money);
    std::printf(
        "%s\t%llu\t%d\t%s\t%s\t%.6f\t%.6f\t%.6f\t%.6f\n",
        particle.label.c_str(),
        static_cast<unsigned long long>(future_seed),
        horizon,
        plan.name,
        opponent_plan.name,
        score,
        own_end,
        opponent_end,
        money_delta
    );
}

int main(int argc, char** argv) {
    if (argc < 6) {
        std::fprintf(stderr, "usage: macro_plan_eval TRACE PARTICLES PREFIX SEAT FUTURE_SEEDS [HORIZONS]\n");
        return 2;
    }
    uint64_t replay_seed = 0;
    Config config;
    std::vector<Turn> turns;
    std::vector<Particle> particles;
    if (!load_trace(argv[1], replay_seed, config, turns)) {
        std::fprintf(stderr, "invalid trace\n"); return 2;
    }
    if (!load_particles(argv[2], particles)) {
        std::fprintf(stderr, "invalid particles\n"); return 2;
    }
    const int prefix = std::atoi(argv[3]);
    const int seat = std::atoi(argv[4]);
    const std::vector<uint64_t> future_seeds = parse_seeds(argv[5]);
    std::vector<int> horizons = {6, 12, 24};
    if (argc > 6) {
        horizons.clear();
        std::stringstream input(argv[6]);
        std::string token;
        while (std::getline(input, token, ','))
            if (!token.empty()) horizons.push_back(std::atoi(token.c_str()));
    }
    if (prefix < 0 || prefix >= static_cast<int>(turns.size()) ||
        seat < 0 || seat > 1 || future_seeds.empty() || horizons.empty()) {
        std::fprintf(stderr, "invalid arguments\n"); return 2;
    }
    config.seed = replay_seed;
    Sim snapshot(config);
    for (int step = 0; step < prefix; ++step)
        snapshot.step(turns[step].action[0], turns[step].action[1]);

    std::printf("scenario\tfuture_seed\thorizon\tplan\tresponse\tscore\town_value\topponent_value\tmoney_delta\n");
    for (const Particle& particle : particles)
        for (uint64_t future_seed : future_seeds)
            for (int horizon : horizons)
                for (const MacroPlan& plan : PLANS)
                    for (const int response : {0, 1})
                        emit_rollout(
                            snapshot, turns, particle, prefix, horizon, seat,
                            future_seed, plan, PLANS[response]
                        );
    return 0;
}

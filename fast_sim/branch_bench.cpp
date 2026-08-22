// Benchmark midgame snapshot/fork rollouts on an exported competitive trace.
//
// This deliberately measures only simulator copy/transition throughput.  It
// does not include policy candidate generation, belief construction or value
// inference, so the projected 600 ms branch count is an upper bound for search.
#include "sim.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <type_traits>
#include <vector>

using namespace kag;

struct Turn {
    Action action[2];
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
    if (!input) {
        std::fprintf(stderr, "cannot open %s\n", path.c_str());
        return false;
    }
    int count = 0;
    if (!(input >> seed >> count) || count <= 0) {
        std::fprintf(stderr, "invalid trace header in %s\n", path.c_str());
        return false;
    }
    read_config(input, config);
    turns.resize(count);
    for (int step = 0; step < count; ++step) {
        for (int player = 0; player < 2; ++player) {
            int unit_count = 0;
            int order_count = 0;
            input >> unit_count >> order_count;
            Action& action = turns[step].action[player];
            action.n_units = std::min(unit_count, MAX_UNITS);
            for (int index = 0; index < unit_count; ++index) {
                int op = 0;
                int arg = 0;
                int amount = 0;
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
                int op = 0;
                int item = 0;
                int amount = 0;
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
    if (!input) {
        std::fprintf(stderr, "truncated action stream in %s\n", path.c_str());
        return false;
    }
    return true;
}

static Action root_variant(const Action& recorded, int variant) {
    Action result = recorded;
    switch (variant % 4) {
        case 0:
            break;
        case 1:
            result.clear();
            break;
        case 2:
            result.n_orders = 0;
            break;
        case 3:
            for (int unit = 0; unit < result.n_units; ++unit) {
                result.units[unit] = UnitAction{};
            }
            break;
    }
    return result;
}

static bool tile_equal(const Tile& left, const Tile& right) {
    return left.kind == right.kind && left.what == right.what &&
           left.has_animal == right.has_animal &&
           left.watered_today == right.watered_today &&
           left.fed_today == right.fed_today &&
           left.cared_today == right.cared_today &&
           left.fertilizer_available == right.fertilizer_available &&
           left.consecutive_dry == right.consecutive_dry &&
           left.yield_units == right.yield_units &&
           left.pending_care_bonus == right.pending_care_bonus &&
           left.planted_day == right.planted_day &&
           left.max_lifespan_step == right.max_lifespan_step &&
           left.fertilized_until_day == right.fertilized_until_day;
}

static bool farm_equal(const Farm& left, const Farm& right) {
    if (left.money != right.money || left.n_units != right.n_units ||
        left.n_quadrants != right.n_quadrants ||
        left.hires_today != right.hires_today ||
        left.shed_total != right.shed_total ||
        left.sell_revenue != right.sell_revenue ||
        left.total_spend != right.total_spend) {
        return false;
    }
    for (int y = 0; y < BOARD; ++y) {
        for (int x = 0; x < BOARD; ++x) {
            if (!tile_equal(left.tiles[y][x], right.tiles[y][x])) return false;
        }
    }
    for (int unit = 0; unit < MAX_UNITS; ++unit) {
        if (left.pos_x[unit] != right.pos_x[unit] ||
            left.pos_y[unit] != right.pos_y[unit] ||
            left.inv_nkeys[unit] != right.inv_nkeys[unit]) {
            return false;
        }
        for (int item = 0; item < N_ITEMS; ++item) {
            if (left.inv[unit][item] != right.inv[unit][item] ||
                left.inv_keys[unit][item] != right.inv_keys[unit][item]) {
                return false;
            }
        }
    }
    for (int item = 0; item < N_ITEMS; ++item) {
        if (left.shed[item] != right.shed[item] ||
            left.discarded[item] != right.discarded[item] ||
            left.produced[item] != right.produced[item] ||
            left.sold_units[item] != right.sold_units[item]) {
            return false;
        }
        if (item < N_CROPS && left.seeds[item] != right.seeds[item]) {
            return false;
        }
    }
    return true;
}

static bool state_equal(const State& left, const State& right) {
    if (left.n_shops != right.n_shops || left.step != right.step ||
        left.day != right.day || left.hour != right.hour ||
        left.done != right.done) {
        return false;
    }
    for (int player = 0; player < 2; ++player) {
        if (!farm_equal(left.farms[player], right.farms[player])) return false;
    }
    for (int item = 0; item < N_PRODUCTS; ++item) {
        if (left.market.inventory[item] != right.market.inventory[item] ||
            left.market.prices[item] != right.market.prices[item]) {
            return false;
        }
    }
    for (int shop = 0; shop < MAX_SHOP_INSTANCES; ++shop) {
        if (left.shops[shop] != right.shops[shop]) return false;
    }
    return true;
}

static uint64_t result_digest(const State& state) {
    uint64_t money[2] = {0, 0};
    std::memcpy(&money[0], &state.farms[0].money, sizeof(double));
    std::memcpy(&money[1], &state.farms[1].money, sizeof(double));
    uint64_t value = money[0] ^ (money[1] << 1);
    value ^= static_cast<uint64_t>(state.step) << 48;
    value ^= static_cast<uint64_t>(state.n_shops) << 40;
    for (int item = 0; item < N_PRODUCTS; ++item) {
        value = value * 1099511628211ull +
                static_cast<uint64_t>(state.market.inventory[item]);
    }
    return value;
}

static bool run_exact_fork_check(
    const Sim& snapshot,
    const std::vector<Turn>& turns,
    int prefix,
    int horizon
) {
    Sim fork = snapshot;
    Sim linear(snapshot.cfg);
    const int stop = std::min<int>(prefix + horizon, turns.size());
    for (int step = prefix; step < stop; ++step) {
        fork.step(turns[step].action[0], turns[step].action[1]);
    }
    for (int step = 0; step < stop; ++step) {
        linear.step(turns[step].action[0], turns[step].action[1]);
    }
    return state_equal(fork.st, linear.st);
}

static void benchmark_horizon(
    const Sim& snapshot,
    const std::vector<Turn>& turns,
    int prefix,
    int horizon,
    int repetitions,
    int candidate_seat
) {
    const int stop = std::min<int>(prefix + horizon, turns.size());
    const int executed = stop - prefix;
    uint64_t sink = 0;
    const auto started = std::chrono::steady_clock::now();
    for (int repetition = 0; repetition < repetitions; ++repetition) {
        Sim child = snapshot;
        for (int step = prefix; step < stop; ++step) {
            Action actions[2] = {
                turns[step].action[0], turns[step].action[1]
            };
            if (step == prefix) {
                actions[candidate_seat] = root_variant(
                    actions[candidate_seat], repetition
                );
            }
            child.step(actions[0], actions[1]);
        }
        sink ^= result_digest(child.st) + static_cast<uint64_t>(repetition);
    }
    const double seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started
    ).count();
    const double branches_per_second = repetitions / seconds;
    const double transitions_per_second =
        static_cast<double>(repetitions) * executed / seconds;
    std::printf(
        "horizon=%-2d branches=%d seconds=%.6f branches/s=%.0f "
        "transitions/s=%.0f projected_600ms=%.0f sink=%llu\n",
        executed,
        repetitions,
        seconds,
        branches_per_second,
        transitions_per_second,
        branches_per_second * 0.6,
        static_cast<unsigned long long>(sink)
    );
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(
            stderr,
            "usage: branch_bench TRACE [PREFIX=360] [REPETITIONS=100000] "
            "[CANDIDATE_SEAT=0]\n"
        );
        return 2;
    }
    uint64_t seed = 0;
    Config config;
    std::vector<Turn> turns;
    if (!load_trace(argv[1], seed, config, turns)) return 2;
    const int prefix = argc > 2 ? std::atoi(argv[2]) : 360;
    const int repetitions = argc > 3 ? std::atoi(argv[3]) : 100000;
    const int candidate_seat = argc > 4 ? std::atoi(argv[4]) : 0;
    if (prefix < 0 || prefix >= static_cast<int>(turns.size()) ||
        repetitions <= 0 || candidate_seat < 0 || candidate_seat > 1) {
        std::fprintf(stderr, "invalid prefix/repetitions/candidate seat\n");
        return 2;
    }

    static_assert(std::is_trivially_copyable<State>::value, "State must copy");
    static_assert(std::is_trivially_copyable<Sim>::value, "Sim must copy");
    config.seed = seed;
    Sim snapshot(config);
    for (int step = 0; step < prefix; ++step) {
        snapshot.step(turns[step].action[0], turns[step].action[1]);
    }

    std::printf(
        "seed=%llu prefix=%d trace_steps=%zu sizeof_state=%zu "
        "sizeof_sim=%zu trivially_copyable=yes\n",
        static_cast<unsigned long long>(seed),
        prefix,
        turns.size(),
        sizeof(State),
        sizeof(Sim)
    );
    for (const int horizon : {6, 12, 24}) {
        if (!run_exact_fork_check(snapshot, turns, prefix, horizon)) {
            std::fprintf(stderr, "fork replay mismatch at horizon %d\n", horizon);
            return 1;
        }
        benchmark_horizon(
            snapshot,
            turns,
            prefix,
            horizon,
            repetitions,
            candidate_seat
        );
    }
    std::printf("fork_semantic_checks=3/3 pass\n");
    return 0;
}

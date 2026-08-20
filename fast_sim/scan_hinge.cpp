// Rank seeds by final scarcity of the three 1.32.7 hinge-priced products.
// Build against the patched public sim.hpp and feed it one recorded action trace.
#include "sim.hpp"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

using namespace kag;
struct Turn { Action a[2]; };

static void read_config(std::istream& in, Config& cfg) {
    std::streampos pos = in.tellg();
    std::string token;
    if (!(in >> token)) return;
    if (token != "CONFIG") { in.clear(); in.seekg(pos); return; }
    in >> cfg.episode_steps >> cfg.board_size >> cfg.starting_money
       >> cfg.max_orders >> cfg.turns_per_day >> cfg.shed_capacity
       >> cfg.weed_chance >> cfg.shop_unlock_interval
       >> cfg.shop_sell_interval >> cfg.center_sell_interval >> cfg.hire_mult;
}

static void load(const std::string& path, Config& cfg, std::vector<Turn>& turns) {
    std::ifstream in(path);
    uint64_t ignored_seed;
    int count;
    in >> ignored_seed >> count;
    read_config(in, cfg);
    turns.resize(count);
    for (int step = 0; step < count; ++step) {
        for (int player = 0; player < 2; ++player) {
            int unit_count, order_count;
            in >> unit_count >> order_count;
            Action& action = turns[step].a[player];
            action.n_units = std::min(unit_count, MAX_UNITS);
            for (int i = 0; i < unit_count; ++i) {
                int op, arg, quantity;
                in >> op >> arg >> quantity;
                if (i < MAX_UNITS) action.units[i] = {
                    static_cast<uint8_t>(op), static_cast<uint8_t>(arg),
                    static_cast<int16_t>(quantity)
                };
            }
            action.n_orders = std::min(order_count, 16);
            for (int i = 0; i < order_count; ++i) {
                int op, item, quantity;
                in >> op >> item >> quantity;
                if (i < 16) action.orders[i] = {
                    static_cast<uint8_t>(op), static_cast<uint8_t>(item), quantity
                };
            }
        }
    }
}

struct Row { int inventory; uint64_t seed; int item; };

int main(int argc, char** argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: scan_hinge TRACE START_SEED COUNT\n");
        return 2;
    }
    Config base;
    std::vector<Turn> turns;
    load(argv[1], base, turns);
    const uint64_t start = std::stoull(argv[2]);
    const int count = std::stoi(argv[3]);
    std::vector<Row> rows;
    rows.reserve(static_cast<size_t>(count) * 3);
    for (int offset = 0; offset < count; ++offset) {
        Config cfg = base;
        cfg.seed = start + static_cast<uint64_t>(offset);
        Sim sim(cfg);
        for (const auto& turn : turns) sim.step(turn.a[0], turn.a[1]);
        for (int item : {CARROT, TOMATO, EGG}) {
            rows.push_back({sim.st.market.inventory[item], cfg.seed, item});
        }
    }
    std::sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) {
        if (a.inventory != b.inventory) return a.inventory < b.inventory;
        if (a.seed != b.seed) return a.seed < b.seed;
        return a.item < b.item;
    });
    const char* names[] = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG"};
    for (size_t i = 0; i < std::min<size_t>(30, rows.size()); ++i) {
        const auto& row = rows[i];
        std::printf("seed=%llu item=%s final_inventory=%d final_price=%d\n",
                    static_cast<unsigned long long>(row.seed), names[row.item],
                    row.inventory, market_price(row.item, row.inventory));
    }
}

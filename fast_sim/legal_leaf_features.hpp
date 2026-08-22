// Exact native counterpart of rl.evaluate_leaf_value.legal_value_features.
// Only the controlled farm's private shed/seeds/inventories are read.  The
// opponent contributes public farm fields only; source seed, identity, replay
// actions and the opponent private payload are not features.
#pragma once

#include "sim.hpp"
#include "frozen_pairwise_rank_e105.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace kag_leaf {

using namespace kag;

struct PointSet {
    int x[BOARD * BOARD] = {0};
    int y[BOARD * BOARD] = {0};
    int count = 0;

    void add(int px, int py) {
        x[count] = px;
        y[count] = py;
        ++count;
    }
};

struct NumberSummary {
    double sum = 0.0;
    int minimum = std::numeric_limits<int>::max();
    int count = 0;

    void add(int value) {
        sum += value;
        minimum = std::min(minimum, value);
        ++count;
    }
    double min_or_zero() const { return count ? minimum : 0.0; }
    double mean_or_zero() const { return count ? sum / count : 0.0; }
};

struct PublicCounts {
    int crop[N_CROPS] = {0};
    int animal[N_ANIMALS] = {0};
    int plants_unwatered = 0;
    int animals_unfed = 0;
    int tile_coop = 0;
    int tile_pasture = 0;
    int tile_plant = 0;
    int tile_weed = 0;
    int tiles_with_yield = 0;
};

inline PublicCounts public_counts(const Farm& farm, int board_size) {
    PublicCounts result;
    for (int y = 0; y < board_size; ++y) {
        for (int x = 0; x < board_size; ++x) {
            const Tile& tile = farm.tiles[y][x];
            switch (tile.kind) {
                case T_PLANT:
                    ++result.tile_plant;
                    if (tile.what < N_CROPS) ++result.crop[tile.what];
                    if (!tile.watered_today) ++result.plants_unwatered;
                    break;
                case T_COOP:
                    ++result.tile_coop;
                    break;
                case T_PASTURE:
                    ++result.tile_pasture;
                    break;
                case T_WEED:
                    ++result.tile_weed;
                    break;
                default:
                    break;
            }
            if (tile.has_animal && tile.what >= GOOSE && tile.what <= SHEEP) {
                ++result.animal[tile.what - GOOSE];
                if (!tile.fed_today) ++result.animals_unfed;
            }
            if (tile.yield_units != 0) ++result.tiles_with_yield;
        }
    }
    return result;
}

inline double public_farm_marked_value(
    const State& state,
    const Farm& farm,
    int board_size
) {
    double value = farm.money;
    for (int y = 0; y < board_size; ++y) {
        for (int x = 0; x < board_size; ++x) {
            const Tile& tile = farm.tiles[y][x];
            if (tile.kind == T_PLANT && tile.what < N_CROPS) {
                const CropDef& crop = CROPS[tile.what];
                const double price = state.market.prices[tile.what];
                value += tile.yield_units * price * 0.85;
                value += crop.max_yield * price * (crop.ongoing ? 0.80 : 0.25);
            } else if (
                tile.has_animal && tile.what >= GOOSE && tile.what <= SHEEP
            ) {
                const AnimalDef& animal = ANIMALS[tile.what - GOOSE];
                const double price = state.market.prices[animal.product];
                value += animal.cost * 0.65;
                value += tile.yield_units * price * 0.85;
                value += price * 1.5;
            } else if (tile.kind == T_COOP || tile.kind == T_PASTURE) {
                value += 40.0;
            }
        }
    }
    return value;
}

inline double own_private_marked_value(const State& state, const Farm& farm) {
    double value = 0.0;
    for (int item = 0; item < N_ITEMS; ++item) {
        int quantity = std::max(0, static_cast<int>(farm.shed[item]));
        for (int unit = 0; unit < farm.n_units; ++unit)
            quantity += std::max(0, static_cast<int>(farm.inv[unit][item]));
        const double unit_value = item < N_PRODUCTS
            ? state.market.prices[item]
            : ANIMALS[item - GOOSE].cost * 0.75;
        value += quantity * unit_value * 0.90;
    }
    for (int crop = 0; crop < N_CROPS; ++crop)
        value += std::max(0, static_cast<int>(farm.seeds[crop]))
               * CROPS[crop].seed * 0.45;
    return value;
}

inline int eta(int x, int y, int tx, int ty) {
    return std::abs(x - tx) + std::abs(y - ty) + 1;
}

inline void target_summary(
    LegalFeatureVector& output,
    std::size_t targets_index,
    std::size_t eta_min_index,
    std::size_t eta_mean_index,
    std::size_t reachable_index,
    const Farm& farm,
    const PointSet& targets,
    int turns_today
) {
    output[targets_index] = targets.count;
    if (targets.count == 0 || farm.n_units == 0) return;
    int minimum = std::numeric_limits<int>::max();
    double sum = 0.0;
    int reachable = 0;
    for (int target = 0; target < targets.count; ++target) {
        int best = std::numeric_limits<int>::max();
        for (int unit = 0; unit < farm.n_units; ++unit) {
            best = std::min(
                best,
                eta(
                    farm.pos_x[unit], farm.pos_y[unit],
                    targets.x[target], targets.y[target]
                )
            );
        }
        minimum = std::min(minimum, best);
        sum += best;
        reachable += best <= turns_today;
    }
    output[eta_min_index] = minimum;
    output[eta_mean_index] = sum / targets.count;
    output[reachable_index] = reachable;
}

inline void fill_public_count_features(
    LegalFeatureVector& output,
    const PublicCounts& counts,
    bool own
) {
    if (own) {
        output[FEAT_OWN_ANIMAL_COW] = counts.animal[COW - GOOSE];
        output[FEAT_OWN_ANIMAL_GOOSE] = counts.animal[GOOSE - GOOSE];
        output[FEAT_OWN_ANIMAL_SHEEP] = counts.animal[SHEEP - GOOSE];
        output[FEAT_OWN_ANIMALS_UNFED] = counts.animals_unfed;
        output[FEAT_OWN_CROP_CARROT] = counts.crop[CARROT];
        output[FEAT_OWN_CROP_MELON] = counts.crop[MELON];
        output[FEAT_OWN_CROP_STRAWBERRY] = counts.crop[STRAWBERRY];
        output[FEAT_OWN_CROP_TOMATO] = counts.crop[TOMATO];
        output[FEAT_OWN_CROP_WHEAT] = counts.crop[WHEAT];
        output[FEAT_OWN_PLANTS_UNWATERED] = counts.plants_unwatered;
        output[FEAT_OWN_TILE_COOP] = counts.tile_coop;
        output[FEAT_OWN_TILE_PASTURE] = counts.tile_pasture;
        output[FEAT_OWN_TILE_PLANT] = counts.tile_plant;
        output[FEAT_OWN_TILE_WEED] = counts.tile_weed;
        output[FEAT_OWN_TILES_WITH_YIELD] = counts.tiles_with_yield;
    } else {
        output[FEAT_OPPONENT_ANIMAL_COW] = counts.animal[COW - GOOSE];
        output[FEAT_OPPONENT_ANIMAL_GOOSE] = counts.animal[GOOSE - GOOSE];
        output[FEAT_OPPONENT_ANIMAL_SHEEP] = counts.animal[SHEEP - GOOSE];
        output[FEAT_OPPONENT_ANIMALS_UNFED] = counts.animals_unfed;
        output[FEAT_OPPONENT_CROP_CARROT] = counts.crop[CARROT];
        output[FEAT_OPPONENT_CROP_MELON] = counts.crop[MELON];
        output[FEAT_OPPONENT_CROP_STRAWBERRY] = counts.crop[STRAWBERRY];
        output[FEAT_OPPONENT_CROP_TOMATO] = counts.crop[TOMATO];
        output[FEAT_OPPONENT_CROP_WHEAT] = counts.crop[WHEAT];
        output[FEAT_OPPONENT_PLANTS_UNWATERED] = counts.plants_unwatered;
        output[FEAT_OPPONENT_TILE_COOP] = counts.tile_coop;
        output[FEAT_OPPONENT_TILE_PASTURE] = counts.tile_pasture;
        output[FEAT_OPPONENT_TILE_PLANT] = counts.tile_plant;
        output[FEAT_OPPONENT_TILE_WEED] = counts.tile_weed;
        output[FEAT_OPPONENT_TILES_WITH_YIELD] = counts.tiles_with_yield;
    }
}

inline LegalFeatureVector legal_leaf_features(const Sim& sim, int seat) {
    LegalFeatureVector output{};
    const Farm& own = sim.st.farms[seat];
    const Farm& opponent = sim.st.farms[1 - seat];
    const int board_size = std::min(BOARD, sim.cfg.board_size);
    const int day = sim.st.day;
    const int hour = sim.st.hour;
    const int step = day * 24 + hour;
    const int turns_today = 24 - hour;

    output[FEAT_DAY] = day;
    output[FEAT_HOUR] = hour;
    output[FEAT_STEP] = step;
    output[FEAT_OWN_MONEY] = own.money;
    output[FEAT_OPPONENT_MONEY] = opponent.money;
    output[FEAT_MONEY_DELTA] = own.money - opponent.money;
    output[FEAT_HANDS] = std::max(0, own.n_units - 1);
    output[FEAT_OPPONENT_HANDS] = std::max(0, opponent.n_units - 1);
    output[FEAT_UNLOCKED] = own.n_quadrants;
    output[FEAT_OPPONENT_UNLOCKED] = opponent.n_quadrants;
    output[FEAT_OWN_HIRES_TODAY] = own.hires_today;
    output[FEAT_OPPONENT_HIRES_TODAY] = opponent.hires_today;

    int carried_total = 0;
    for (int unit = 0; unit < own.n_units; ++unit)
        for (int item = 0; item < N_ITEMS; ++item)
            carried_total += std::max(0, static_cast<int>(own.inv[unit][item]));
    output[FEAT_CARRIED_TOTAL] = carried_total;
    output[FEAT_SHED_TOTAL] = own.shed_total;

    fill_public_count_features(
        output, public_counts(own, board_size), true
    );
    fill_public_count_features(
        output, public_counts(opponent, board_size), false
    );

    static constexpr std::size_t market_features[N_PRODUCTS] = {
        FEAT_MARKET_WHEAT, FEAT_MARKET_CARROT, FEAT_MARKET_TOMATO,
        FEAT_MARKET_STRAWBERRY, FEAT_MARKET_MELON, FEAT_MARKET_EGG,
        FEAT_MARKET_MILK, FEAT_MARKET_WOOL, FEAT_MARKET_FERTILIZER,
    };
    static constexpr std::size_t price_features[N_PRODUCTS] = {
        FEAT_PRICE_WHEAT, FEAT_PRICE_CARROT, FEAT_PRICE_TOMATO,
        FEAT_PRICE_STRAWBERRY, FEAT_PRICE_MELON, FEAT_PRICE_EGG,
        FEAT_PRICE_MILK, FEAT_PRICE_WOOL, FEAT_PRICE_FERTILIZER,
    };
    static constexpr std::size_t shed_features[N_PRODUCTS] = {
        FEAT_SHED_WHEAT, FEAT_SHED_CARROT, FEAT_SHED_TOMATO,
        FEAT_SHED_STRAWBERRY, FEAT_SHED_MELON, FEAT_SHED_EGG,
        FEAT_SHED_MILK, FEAT_SHED_WOOL, FEAT_SHED_FERTILIZER,
    };
    for (int item = 0; item < N_PRODUCTS; ++item) {
        output[market_features[item]] = sim.st.market.inventory[item];
        output[price_features[item]] = sim.st.market.prices[item];
        output[shed_features[item]] = own.shed[item];
    }
    static constexpr std::size_t seed_features[N_CROPS] = {
        FEAT_SEED_WHEAT, FEAT_SEED_CARROT, FEAT_SEED_TOMATO,
        FEAT_SEED_STRAWBERRY, FEAT_SEED_MELON,
    };
    for (int crop = 0; crop < N_CROPS; ++crop)
        output[seed_features[crop]] = own.seeds[crop];

    int shop_counts[N_SHOPS] = {0};
    for (int index = 0; index < sim.st.n_shops; ++index)
        if (sim.st.shops[index] < N_SHOPS) ++shop_counts[sim.st.shops[index]];
    output[FEAT_SHOP_BAKERY] = shop_counts[SHOP_BAKERY];
    output[FEAT_SHOP_BRUNCH_SPOT] = shop_counts[SHOP_BRUNCH_SPOT];
    output[FEAT_SHOP_FARMERS_MARKET] = shop_counts[SHOP_FARMERS_MARKET];
    output[FEAT_SHOP_ICE_CREAM_SHOP] = shop_counts[SHOP_ICE_CREAM_SHOP];
    output[FEAT_SHOP_PET_CAFE] = shop_counts[SHOP_PET_CAFE];
    output[FEAT_SHOP_PIZZA_SHOP] = shop_counts[SHOP_PIZZA_SHOP];
    output[FEAT_SHOP_SMOOTHIE_SHOP] = shop_counts[SHOP_SMOOTHIE_SHOP];
    output[FEAT_SHOP_YARN_STORE] = shop_counts[SHOP_YARN_STORE];

    const double own_public = public_farm_marked_value(
        sim.st, own, board_size
    );
    const double opponent_public = public_farm_marked_value(
        sim.st, opponent, board_size
    );
    const double own_private = own_private_marked_value(sim.st, own);
    output[FEAT_OWN_PRIVATE_MARKED_VALUE] = own_private;
    output[FEAT_OPPONENT_PUBLIC_MARKED_VALUE] = opponent_public;
    output[FEAT_LEGAL_MARKED_MARGIN] =
        own_public + own_private - opponent_public;

    PointSet service_targets;
    PointSet harvest_targets;
    PointSet weed_targets;
    PointSet fertilizer_targets;
    NumberSummary crop_first_etas;
    NumberSummary animal_next_etas;
    NumberSummary decay_turns;
    int ready_units = 0;
    double ready_value = 0.0;
    int critical_plants = 0;
    int critical_animals = 0;
    int pending_care = 0;
    int fertilized_tiles = 0;
    int terminal_stranded = 0;

    for (int y = 0; y < board_size; ++y) {
        for (int x = 0; x < board_size; ++x) {
            const Tile& tile = own.tiles[y][x];
            if (tile.kind == T_WEED) {
                weed_targets.add(x, y);
                continue;
            }
            if (tile.kind == T_PLANT && tile.what < N_CROPS) {
                const CropDef& crop = CROPS[tile.what];
                if (!tile.watered_today) {
                    service_targets.add(x, y);
                    critical_plants += tile.consecutive_dry >= 1;
                }
                fertilized_tiles += tile.fertilized_until_day >= day;
                const int first_day = tile.planted_day + crop.first_yield_day;
                crop_first_etas.add(std::max(0, first_day - day));
                terminal_stranded += first_day >= 30;
                if (
                    tile.yield_units > 0 &&
                    (crop.ongoing || day >= first_day)
                ) {
                    harvest_targets.add(x, y);
                    ready_units += tile.yield_units;
                    ready_value +=
                        tile.yield_units * sim.st.market.prices[tile.what];
                }
                if (tile.max_lifespan_step >= 0)
                    decay_turns.add(std::max(0, tile.max_lifespan_step - step));
                continue;
            }
            if (
                tile.has_animal && tile.what >= GOOSE && tile.what <= SHEEP
            ) {
                const AnimalDef& animal = ANIMALS[tile.what - GOOSE];
                if (!tile.fed_today) {
                    service_targets.add(x, y);
                    critical_animals += tile.consecutive_dry >= 1;
                }
                if (tile.fertilizer_available) fertilizer_targets.add(x, y);
                pending_care += tile.pending_care_bonus;
                if (tile.yield_units > 0) {
                    harvest_targets.add(x, y);
                    ready_units += tile.yield_units;
                    ready_value +=
                        tile.yield_units * sim.st.market.prices[animal.product];
                }
                const int first_day = tile.planted_day + animal.first_yield_day;
                int next_day = std::max(first_day, day + 1);
                const int remainder = (next_day - first_day) % animal.interval;
                if (remainder) next_day += animal.interval - remainder;
                animal_next_etas.add(next_day - day);
                terminal_stranded += next_day >= 30;
            }
        }
    }

    output[FEAT_FORWARD_READY_YIELD_UNITS] = ready_units;
    output[FEAT_FORWARD_READY_YIELD_VALUE] = ready_value;
    output[FEAT_FORWARD_CRITICAL_PLANTS] = critical_plants;
    output[FEAT_FORWARD_CRITICAL_ANIMALS] = critical_animals;
    output[FEAT_FORWARD_PENDING_CARE_BONUS] = pending_care;
    output[FEAT_FORWARD_FERTILIZER_AVAILABLE_TILES] = fertilizer_targets.count;
    output[FEAT_FORWARD_FERTILIZED_TILES] = fertilized_tiles;
    output[FEAT_FORWARD_CROP_FIRST_YIELD_DAYS_MIN] =
        crop_first_etas.min_or_zero();
    output[FEAT_FORWARD_CROP_FIRST_YIELD_DAYS_MEAN] =
        crop_first_etas.mean_or_zero();
    output[FEAT_FORWARD_ANIMAL_NEXT_YIELD_DAYS_MIN] =
        animal_next_etas.min_or_zero();
    output[FEAT_FORWARD_ANIMAL_NEXT_YIELD_DAYS_MEAN] =
        animal_next_etas.mean_or_zero();
    output[FEAT_FORWARD_TERMINAL_STRANDED_OBJECTS] = terminal_stranded;
    output[FEAT_FORWARD_DECAY_TURNS_MIN] = decay_turns.min_or_zero();

    target_summary(
        output, FEAT_FORWARD_SERVICE_TARGETS, FEAT_FORWARD_SERVICE_ETA_MIN,
        FEAT_FORWARD_SERVICE_ETA_MEAN, FEAT_FORWARD_SERVICE_REACHABLE_TODAY,
        own, service_targets, turns_today
    );
    target_summary(
        output, FEAT_FORWARD_HARVEST_TARGETS, FEAT_FORWARD_HARVEST_ETA_MIN,
        FEAT_FORWARD_HARVEST_ETA_MEAN, FEAT_FORWARD_HARVEST_REACHABLE_TODAY,
        own, harvest_targets, turns_today
    );
    target_summary(
        output, FEAT_FORWARD_WEED_TARGETS, FEAT_FORWARD_WEED_ETA_MIN,
        FEAT_FORWARD_WEED_ETA_MEAN, FEAT_FORWARD_WEED_REACHABLE_TODAY,
        own, weed_targets, turns_today
    );
    target_summary(
        output, FEAT_FORWARD_FERTILIZER_TARGETS,
        FEAT_FORWARD_FERTILIZER_ETA_MIN,
        FEAT_FORWARD_FERTILIZER_ETA_MEAN,
        FEAT_FORWARD_FERTILIZER_REACHABLE_TODAY,
        own, fertilizer_targets, turns_today
    );

    static constexpr int shed_access[4][2] = {
        {4, 4}, {5, 4}, {4, 5}, {5, 5}
    };
    NumberSummary carried_etas;
    int carried_units = 0;
    for (int unit = 0; unit < own.n_units; ++unit) {
        int total = 0;
        for (int item = 0; item < N_ITEMS; ++item)
            total += std::max(0, static_cast<int>(own.inv[unit][item]));
        if (total <= 0) continue;
        ++carried_units;
        int best = std::numeric_limits<int>::max();
        for (const auto& point : shed_access)
            best = std::min(
                best,
                eta(own.pos_x[unit], own.pos_y[unit], point[0], point[1])
            );
        carried_etas.add(best);
    }
    output[FEAT_FORWARD_CARRIED_UNITS] = carried_units;
    output[FEAT_FORWARD_CARRIED_TO_SHED_ETA_MIN] =
        carried_etas.min_or_zero();
    // Reachability is a count over carried workers, not a boolean minimum.
    int carried_reachable = 0;
    for (int unit = 0; unit < own.n_units; ++unit) {
        int total = 0;
        for (int item = 0; item < N_ITEMS; ++item)
            total += std::max(0, static_cast<int>(own.inv[unit][item]));
        if (total <= 0) continue;
        int best = std::numeric_limits<int>::max();
        for (const auto& point : shed_access)
            best = std::min(
                best,
                eta(own.pos_x[unit], own.pos_y[unit], point[0], point[1])
            );
        carried_reachable += best <= turns_today;
    }
    output[FEAT_FORWARD_CARRIED_TO_SHED_REACHABLE_TODAY] = carried_reachable;

    return output;
}

}  // namespace kag_leaf

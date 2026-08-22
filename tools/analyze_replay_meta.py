"""Extract comparable economic-strategy features from Kaggriculture replays."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median


PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "SHEEP", "COW")
FIELD_OPERATIONS = (
    "NORTH",
    "SOUTH",
    "EAST",
    "WEST",
    "PASS",
    "PICKUP",
    "DROP",
    "PLANT",
    "WATER",
    "HARVEST",
    "FERTILIZE",
    "BUILD_COOP",
    "BUILD_PASTURE",
    "DIG",
    "PLACE",
    "FEED",
    "COLLECT_FERTILIZER",
    "CARE",
)
MARKET_OPERATIONS = (
    "BUY_SEED",
    "BUY_PRODUCT",
    "BUY_ANIMAL",
    "SELL",
    "HIRE",
    "BUY_LAND",
)
CHECKPOINT_DAYS = (0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 29)


def operation(raw) -> str:
    if isinstance(raw, (list, tuple)) and raw:
        return str(raw[0]).upper()
    return "PASS"


def quantity(raw, index: int = 2) -> int:
    if not isinstance(raw, (list, tuple)) or len(raw) <= index:
        return 1
    try:
        return max(0, int(raw[index]))
    except (TypeError, ValueError):
        return 0


def normalize_name(value: str) -> str:
    return " ".join(str(value).casefold().split())


def tile_counts(farm: dict) -> dict[str, int]:
    counts = Counter()
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", "UNKNOWN")).upper()
            counts[f"kind_{kind}"] += 1
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                counts[f"crop_{str(crop).upper()}"] += 1
            if animal:
                counts[f"animal_{str(animal).upper()}"] += 1
            if kind == "PLANT" and not tile.get("watered_today", False):
                counts["unwatered"] += 1
            if animal and not tile.get("fed_today", False):
                counts["unfed"] += 1
            if int(tile.get("yield_units", 0) or 0) > 0:
                counts["yield_tiles"] += 1
    for crop in CROPS:
        counts.setdefault(f"crop_{crop}", 0)
    for animal in ANIMALS:
        counts.setdefault(f"animal_{animal}", 0)
    for kind in ("PLANT", "PASTURE", "COOP", "WEED"):
        counts.setdefault(f"kind_{kind}", 0)
    return dict(sorted(counts.items()))


def player_names(replay: dict) -> list[str]:
    agents = replay.get("info", {}).get("Agents", []) or []
    names = [str(agent.get("Name", "")) for agent in agents]
    if len(names) < 2:
        names = [str(name) for name in replay.get("info", {}).get("TeamNames", [])]
    return names


def _set_first(first_steps: dict[str, int], key: str, step: int) -> None:
    first_steps.setdefault(key, step)


def analyze_player(replay: dict, seat: int) -> dict:
    steps = replay.get("steps", []) or []
    if not steps or seat >= len(steps[0]):
        raise ValueError(f"replay has no seat {seat}")
    names = player_names(replay)
    rewards = [float(value or 0) for value in replay.get("rewards", [])]
    opponent = 1 - seat
    field_counts = Counter()
    market_counts = Counter()
    market_quantities = Counter()
    seed_buys = Counter()
    animal_buys = Counter()
    product_buys = Counter()
    sales = Counter()
    placements = Counter()
    first_steps: dict[str, int] = {}
    hires_by_day = Counter()
    daily_field: dict[int, Counter] = {}
    daily_market: dict[int, Counter] = {}
    daily_buys: dict[int, Counter] = {}
    daily_sales: dict[int, Counter] = {}
    daily_snapshots = []
    land_steps = []
    money_checkpoints = {}
    peak_hands = 0
    peak_tiles = Counter()
    estimated_sale_mark_value = 0

    for index in range(max(0, len(steps) - 1)):
        pre = steps[index][seat].get("observation", {}) or {}
        day = int(pre.get("day", index // 24) or 0)
        hour = int(pre.get("hour", index % 24) or 0)
        step = day * 24 + hour
        farms = pre.get("farms", []) or []
        farm = farms[seat] if seat < len(farms) else {}
        peak_hands = max(peak_hands, len(farm.get("hands", []) or []))
        for key, value in tile_counts(farm).items():
            peak_tiles[key] = max(peak_tiles[key], value)
        if day in CHECKPOINT_DAYS and hour == 0:
            money_checkpoints.setdefault(str(day), float(farm.get("money", 0) or 0))
        if hour == 0:
            daily_snapshots.append(
                {
                    "day": day,
                    "money": float(farm.get("money", 0) or 0),
                    "hands": len(farm.get("hands", []) or []),
                    "quadrants": len(farm.get("unlocked_quadrants", []) or []),
                    "tiles": tile_counts(farm),
                }
            )

        action = steps[index + 1][seat].get("action", {}) or {}
        units = [action.get("farmer"), *(action.get("hands", []) or [])]
        for raw in units:
            op = operation(raw)
            field_counts[op] += 1
            daily_field.setdefault(day, Counter())[op] += 1
            if op != "PASS":
                _set_first(first_steps, f"field_{op}", step)
            if op == "PLANT" and isinstance(raw, (list, tuple)) and len(raw) >= 2:
                placements[f"PLANT_{str(raw[1]).upper()}"] += 1
            elif op == "PLACE" and isinstance(raw, (list, tuple)) and len(raw) >= 2:
                placements[f"PLACE_{str(raw[1]).upper()}"] += quantity(raw)

        prices = (pre.get("market", {}) or {}).get("prices", {}) or {}
        for raw in action.get("market", []) or []:
            op = operation(raw)
            market_counts[op] += 1
            daily_market.setdefault(day, Counter())[op] += 1
            _set_first(first_steps, f"market_{op}", step)
            if op == "HIRE":
                hires_by_day[day] += 1
                market_quantities[op] += 1
            elif op == "BUY_LAND":
                land_steps.append(step)
                market_quantities[op] += 1
            elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
                item = str(raw[1]).upper()
                amount = quantity(raw)
                market_quantities[op] += amount
                if op == "BUY_SEED":
                    seed_buys[item] += amount
                    daily_buys.setdefault(day, Counter())[f"SEED_{item}"] += amount
                elif op == "BUY_ANIMAL":
                    animal_buys[item] += amount
                    daily_buys.setdefault(day, Counter())[f"ANIMAL_{item}"] += amount
                elif op == "BUY_PRODUCT":
                    product_buys[item] += amount
                    daily_buys.setdefault(day, Counter())[f"PRODUCT_{item}"] += amount
                elif op == "SELL":
                    sales[item] += amount
                    daily_sales.setdefault(day, Counter())[item] += amount
                    estimated_sale_mark_value += amount * int(prices.get(item, 0) or 0)

    final_state = steps[-1][seat]
    final_obs = final_state.get("observation", {}) or {}
    final_farms = final_obs.get("farms", []) or []
    final_farm = final_farms[seat] if seat < len(final_farms) else {}
    final_private = final_obs.get("private", {}) or {}
    final_tiles = tile_counts(final_farm)
    final_quadrants = list(final_farm.get("unlocked_quadrants", []) or [])
    final_shed = {
        key: int(value or 0)
        for key, value in (final_private.get("shed", {}) or {}).items()
        if int(value or 0) > 0
    }
    own_bank = rewards[seat] if seat < len(rewards) else float(final_state.get("reward", 0) or 0)
    opponent_bank = rewards[opponent] if opponent < len(rewards) else 0.0
    outcome = 1.0 if own_bank > opponent_bank else 0.0 if own_bank < opponent_bank else 0.5

    for op in FIELD_OPERATIONS:
        field_counts.setdefault(op, 0)
    for op in MARKET_OPERATIONS:
        market_counts.setdefault(op, 0)
    for item in CROPS:
        seed_buys.setdefault(item, 0)
    for item in ANIMALS:
        animal_buys.setdefault(item, 0)
    for item in PRODUCTS:
        sales.setdefault(item, 0)

    return {
        "episode_id": int(replay.get("info", {}).get("EpisodeId", 0) or 0),
        "seed": int(replay.get("info", {}).get("seed", 0) or 0),
        "seat": seat,
        "name": names[seat] if seat < len(names) else f"seat-{seat}",
        "opponent": names[opponent] if opponent < len(names) else f"seat-{opponent}",
        "final_bank": own_bank,
        "opponent_bank": opponent_bank,
        "margin": own_bank - opponent_bank,
        "outcome": outcome,
        "final_money_public": float(final_farm.get("money", own_bank) or 0),
        "final_quadrants": final_quadrants,
        "final_quadrant_count": len(final_quadrants),
        "bought_fourth_quadrant": len(final_quadrants) == 4,
        "land_purchase_steps": land_steps,
        "total_hires": sum(hires_by_day.values()),
        "hires_by_day": dict(sorted(hires_by_day.items())),
        "daily_field_actions": {
            str(day): dict(sorted(counts.items())) for day, counts in sorted(daily_field.items())
        },
        "daily_market_actions": {
            str(day): dict(sorted(counts.items())) for day, counts in sorted(daily_market.items())
        },
        "daily_buys": {
            str(day): dict(sorted(counts.items())) for day, counts in sorted(daily_buys.items())
        },
        "daily_sales": {
            str(day): dict(sorted(counts.items())) for day, counts in sorted(daily_sales.items())
        },
        "daily_snapshots": daily_snapshots,
        "peak_hands": peak_hands,
        "field_actions": dict(sorted(field_counts.items())),
        "market_actions": dict(sorted(market_counts.items())),
        "market_quantities": dict(sorted(market_quantities.items())),
        "seed_buys": dict(sorted(seed_buys.items())),
        "animal_buys": dict(sorted(animal_buys.items())),
        "product_buys": dict(sorted(product_buys.items())),
        "sales": dict(sorted(sales.items())),
        "estimated_sale_mark_value": estimated_sale_mark_value,
        "placements": dict(sorted(placements.items())),
        "first_steps": dict(sorted(first_steps.items())),
        "final_tiles": final_tiles,
        "peak_tiles": dict(sorted(peak_tiles.items())),
        "final_shed": final_shed,
        "money_checkpoints": money_checkpoints,
    }


def scalar_metrics(game: dict) -> dict[str, float]:
    metrics = {
        "final_bank": float(game["final_bank"]),
        "margin": float(game["margin"]),
        "outcome": float(game["outcome"]),
        "final_quadrant_count": float(game["final_quadrant_count"]),
        "bought_fourth_quadrant": float(game["bought_fourth_quadrant"]),
        "total_hires": float(game["total_hires"]),
        "peak_hands": float(game["peak_hands"]),
        "estimated_sale_mark_value": float(game["estimated_sale_mark_value"]),
        "total_animal_buys": float(sum(game["animal_buys"].values())),
        "total_seed_buys": float(sum(game["seed_buys"].values())),
    }
    for index in range(3):
        metrics[f"land_purchase_{index + 1}_step"] = float(
            game["land_purchase_steps"][index]
            if index < len(game["land_purchase_steps"])
            else 720
        )
    for animal in ANIMALS:
        metrics[f"animal_buys_{animal.lower()}"] = float(game["animal_buys"].get(animal, 0))
        metrics[f"final_animals_{animal.lower()}"] = float(game["final_tiles"].get(f"animal_{animal}", 0))
        metrics[f"peak_animals_{animal.lower()}"] = float(game["peak_tiles"].get(f"animal_{animal}", 0))
    for crop in CROPS:
        metrics[f"seed_buys_{crop.lower()}"] = float(game["seed_buys"].get(crop, 0))
        metrics[f"final_crops_{crop.lower()}"] = float(game["final_tiles"].get(f"crop_{crop}", 0))
        metrics[f"peak_crops_{crop.lower()}"] = float(game["peak_tiles"].get(f"crop_{crop}", 0))
    for op in ("WATER", "HARVEST", "FERTILIZE", "FEED", "CARE", "COLLECT_FERTILIZER", "DIG", "DROP"):
        metrics[f"actions_{op.lower()}"] = float(game["field_actions"].get(op, 0))
    for item in PRODUCTS:
        metrics[f"sales_{item.lower()}"] = float(game["sales"].get(item, 0))
    return metrics


def aggregate_games(games: list[dict], metadata: dict) -> dict:
    vectors = [scalar_metrics(game) for game in games]
    keys = sorted({key for vector in vectors for key in vector})
    averages = {key: mean(vector.get(key, 0.0) for vector in vectors) for key in keys}
    medians = {key: median(vector.get(key, 0.0) for vector in vectors) for key in keys}
    return {
        **metadata,
        "games": len(games),
        "episodes": [game["episode_id"] for game in games],
        "averages": averages,
        "medians": medians,
        "min_bank": min(game["final_bank"] for game in games),
        "max_bank": max(game["final_bank"] for game in games),
        "fourth_quadrant_rate": mean(float(game["bought_fourth_quadrant"]) for game in games),
    }


def vector_difference(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {
        key: left.get(key, 0.0) - right.get(key, 0.0)
        for key in sorted(set(left) | set(right))
    }


def mean_vectors(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {}
    keys = sorted({key for vector in vectors for key in vector})
    return {key: mean(vector.get(key, 0.0) for vector in vectors) for key in keys}


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_scale = sum((x - left_mean) ** 2 for x in left) ** 0.5
    right_scale = sum((y - right_mean) ** 2 for y in right) ** 0.5
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def analyze_manifest(manifest: dict) -> dict:
    games = []
    all_players = []
    matchups = []
    missing = []
    seen = set()
    for episode in manifest.get("episodes", []):
        path = Path(episode["path"])
        replay = json.loads(path.read_text(encoding="utf-8"))
        names = player_names(replay)
        normalized = [normalize_name(name) for name in names]
        episode_players = [analyze_player(replay, seat) for seat in range(min(2, len(names)))]
        all_players.extend(episode_players)
        if len(episode_players) == 2 and episode_players[0]["outcome"] != 0.5:
            winner = episode_players[0] if episode_players[0]["outcome"] == 1.0 else episode_players[1]
            loser = episode_players[1] if winner is episode_players[0] else episode_players[0]
            matchups.append(
                {
                    "episode_id": episode["episode_id"],
                    "seed": winner["seed"],
                    "winner": winner["name"],
                    "loser": loser["name"],
                    "winner_bank": winner["final_bank"],
                    "loser_bank": loser["final_bank"],
                    "differences": vector_difference(scalar_metrics(winner), scalar_metrics(loser)),
                }
            )
        for request in episode.get("requested_for", []):
            key = (int(request["submission_id"]), int(episode["episode_id"]))
            if key in seen:
                continue
            seen.add(key)
            target = normalize_name(request.get("replay_name", request["name"]))
            if target not in normalized:
                missing.append({"episode_id": episode["episode_id"], **request, "replay_names": names})
                continue
            seat = normalized.index(target)
            game = analyze_player(replay, seat)
            game["target"] = request
            games.append(game)

    grouped: dict[int, list[dict]] = {}
    metadata: dict[int, dict] = {}
    for game in games:
        request = game["target"]
        submission_id = int(request["submission_id"])
        grouped.setdefault(submission_id, []).append(game)
        metadata[submission_id] = dict(request)
    agents = [
        aggregate_games(grouped[submission_id], metadata[submission_id])
        for submission_id in sorted(
            grouped,
            key=lambda value: (
                metadata[value].get("cohort") != "top20",
                metadata[value].get("rank") if metadata[value].get("rank") is not None else 10_000,
            ),
        )
    ]

    def cohort_summary(selected: list[dict]) -> dict:
        if not selected:
            return {}
        keys = sorted({key for agent in selected for key in agent["averages"]})
        return {
            "agents": len(selected),
            "agent_equal_weight_means": {
                key: mean(agent["averages"].get(key, 0.0) for agent in selected)
                for key in keys
            },
        }

    top20 = [agent for agent in agents if agent.get("cohort") == "top20"]
    top5 = [agent for agent in top20 if int(agent.get("rank", 999)) <= 5]
    comparators = [agent for agent in agents if agent.get("cohort") == "comparator"]
    top20_names = {normalize_name(agent["name"]) for agent in top20}
    top20_matchups = [
        matchup
        for matchup in matchups
        if normalize_name(matchup["winner"]) in top20_names
        and normalize_name(matchup["loser"]) in top20_names
    ]
    feature_names = sorted({key for agent in top20 for key in agent["averages"]})
    score_correlations = {}
    for feature in feature_names:
        value = pearson(
            [float(agent["score"]) for agent in top20],
            [float(agent["averages"].get(feature, 0.0)) for agent in top20],
        )
        if value is not None:
            score_correlations[feature] = value
    return {
        "schema": "kaggriculture-replay-meta-v1",
        "manifest_schema": manifest.get("schema"),
        "target_game_count": len(games),
        "missing_target_count": len(missing),
        "missing_targets": missing,
        "agents": agents,
        "all_players": all_players,
        "matchups": matchups,
        "matched_winner_minus_loser": {
            "all_decisive_games": len(matchups),
            "all_mean_differences": mean_vectors([matchup["differences"] for matchup in matchups]),
            "top20_vs_top20_games": len(top20_matchups),
            "top20_vs_top20_mean_differences": mean_vectors(
                [matchup["differences"] for matchup in top20_matchups]
            ),
        },
        "leaderboard_score_correlations": score_correlations,
        "cohorts": {
            "top5": cohort_summary(top5),
            "top20": cohort_summary(top20),
            "comparators": cohort_summary(comparators),
        },
        "games": games,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = analyze_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "target_games": report["target_game_count"],
                "agents": len(report["agents"]),
                "missing_targets": report["missing_target_count"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

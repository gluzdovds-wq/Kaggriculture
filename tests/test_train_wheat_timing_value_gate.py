import copy

import numpy as np
import pytest

from tools.train_wheat_timing_value_gate import (
    FEATURES,
    RUNTIME_SCHEMA,
    TREATMENT_LABEL,
    arrays,
    build_rows,
    choose_spec_inner,
)


def public_context(*, wheat_price=25, opponent_money=100):
    return {
        "step": 112,
        "day": 4,
        "hour": 16,
        "shops": ["BAKERY"],
        "market_inventory": {"WHEAT": 9990, "WOOL": 9990},
        "market_prices": {"WHEAT": wheat_price},
        "candidate": {
            "money": 20,
            "hands": [],
            "occupied": [],
        },
        "opponent": {
            "money": opponent_money,
            "hands": [[1, 2]],
            "occupied": [[0, 0, "PLANT", "WHEAT", None]],
        },
    }


def telemetry(*, advanced=1, repaid=1, debt=0, cap=1):
    return {
        "label": TREATMENT_LABEL,
        "checkpoint_step": 112,
        "execute_step": 119,
        "sell_cap": cap,
        "model_schema": RUNTIME_SCHEMA,
        "executed": advanced,
        "market_advanced": {"WHEAT": advanced},
        "market_repaid": {"WHEAT": repaid},
        "debt": {0: debt, 1: 0},
    }


def paired_reports(
    *,
    episode=1,
    opponent="Opponent A",
    margin_delta=1,
    treatment_telemetry=None,
):
    case = {
        "episode_id": episode,
        "seed": 1000 + episode,
        "target_seat": 0,
        "target_name": "Top Bot",
        "target_rank": 1,
        "target_submission_id": 55,
        "opponent_name": opponent,
        "recorded_target_bank": 100.0,
        "recorded_opponent_bank": 90.0,
    }
    base = {
        "candidate": "S09",
        "episode_id": episode,
        "target_rank": 1,
        "target_name": "Top Bot",
        "target_seat": 0,
        "opponent_name": opponent,
        "candidate_bank": 110.0,
        "opponent_bank": 100.0,
        "margin": 10.0,
        "outcome": 1.0,
        "public_context_checkpoints": [public_context()],
        "candidate_telemetry": {},
    }
    advanced = copy.deepcopy(base)
    advanced["candidate"] = "ADVANCE1"
    advanced["candidate_bank"] += margin_delta
    advanced["margin"] += margin_delta
    advanced["candidate_telemetry"] = (
        telemetry() if treatment_telemetry is None else treatment_telemetry
    )
    reference = {"cases": [copy.deepcopy(case)], "candidates": {"S09": {"matches": [base]}}}
    treatment = {
        "cases": [copy.deepcopy(case)],
        "candidates": {"ADVANCE1": {"matches": [advanced]}},
    }
    return reference, treatment


def build(reference, treatment):
    return build_rows(reference, treatment, "S09", "ADVANCE1")


def test_accepts_exact_advance_and_repayment_contract():
    rows, audit = build(*paired_reports())
    assert len(rows) == 1
    assert rows[0]["eligible"] is True
    assert rows[0]["advanced_units"] == 1
    assert rows[0]["features"]["x_focus_crop_wheat"] == 1.0
    assert tuple(rows[0]["features"]) == FEATURES
    assert audit["eligible_advanced_rows"] == 1


def test_rejects_nonzero_terminal_debt():
    reports = paired_reports(treatment_telemetry=telemetry(debt=1))
    with pytest.raises(ValueError, match="terminal debt"):
        build(*reports)


def test_rejects_cap_or_advanced_quantity_above_one():
    with pytest.raises(ValueError, match="sell_cap"):
        build(*paired_reports(treatment_telemetry=telemetry(cap=2)))
    with pytest.raises(ValueError, match="0 or 1"):
        build(
            *paired_reports(
                treatment_telemetry=telemetry(advanced=2, repaid=2, cap=1)
            )
        )


def test_generic_executed_is_not_a_treatment_fallback():
    payload = telemetry()
    payload.pop("market_advanced")
    payload.pop("market_repaid")
    with pytest.raises(ValueError, match="market_advanced"):
        build(*paired_reports(treatment_telemetry=payload))


def test_rejects_mismatched_case_identity():
    reference, treatment = paired_reports()
    treatment["cases"][0]["seed"] += 1
    with pytest.raises(ValueError, match="differs at seed"):
        build(reference, treatment)


def test_rejects_mismatched_pretreatment_checkpoint():
    reference, treatment = paired_reports()
    treatment["candidates"]["ADVANCE1"]["matches"][0][
        "public_context_checkpoints"
    ][0]["market_prices"]["WHEAT"] += 1
    with pytest.raises(ValueError, match="checkpoint 112"):
        build(reference, treatment)


def test_rejects_missing_or_nonfinite_public_features():
    reference, treatment = paired_reports()
    reference["candidates"]["S09"]["matches"][0]["public_context_checkpoints"][0][
        "market_prices"
    ].pop("WHEAT")
    treatment["candidates"]["ADVANCE1"]["matches"][0][
        "public_context_checkpoints"
    ] = copy.deepcopy(
        reference["candidates"]["S09"]["matches"][0]["public_context_checkpoints"]
    )
    with pytest.raises(ValueError, match="market_prices.WHEAT"):
        build(reference, treatment)

    reference, treatment = paired_reports()
    for report, candidate in ((reference, "S09"), (treatment, "ADVANCE1")):
        report["candidates"][candidate]["matches"][0][
            "public_context_checkpoints"
        ][0]["market_prices"]["WHEAT"] = np.inf
    with pytest.raises(ValueError, match="finite"):
        build(reference, treatment)


def test_untreated_noop_stays_in_all_row_metrics_dataset():
    reference, treatment = paired_reports(
        margin_delta=0, treatment_telemetry=telemetry(advanced=0, repaid=0)
    )
    rows, audit = build(reference, treatment)
    assert len(rows) == 1
    assert rows[0]["eligible"] is False
    assert rows[0]["margin_delta"] == 0.0
    assert audit["paired_rows"] == 1
    assert audit["untreated_noop_rows"] == 1


def test_full_zero_value_dataset_selects_keep_base():
    references = {"cases": [], "candidates": {"S09": {"matches": []}}}
    treatments = {"cases": [], "candidates": {"ADVANCE1": {"matches": []}}}
    for episode in range(1, 13):
        reference, treatment = paired_reports(
            episode=episode,
            opponent=f"Opponent {episode % 4}",
            margin_delta=0,
        )
        references["cases"].extend(reference["cases"])
        references["candidates"]["S09"]["matches"].extend(
            reference["candidates"]["S09"]["matches"]
        )
        treatments["cases"].extend(treatment["cases"])
        treatments["candidates"]["ADVANCE1"]["matches"].extend(
            treatment["candidates"]["ADVANCE1"]["matches"]
        )
    rows, _ = build(references, treatments)
    x, y, groups, episodes = arrays(rows)
    selected, scores = choose_spec_inner(x, y, groups, episodes)
    assert selected.name == "KEEP_BASE"
    assert all(row["mean_policy_uplift"] == 0.0 for row in scores)

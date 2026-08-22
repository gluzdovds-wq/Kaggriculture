from tools.evaluate_live_replay_cohort import (
    classify_replay,
    console_cohort_summary,
    observed_opponent_animals,
    outcome,
    parse_gate_animals,
)


def test_parse_gate_animals_and_outcome():
    assert parse_gate_animals(["cow=3", "SHEEP=2"]) == {"COW": 3, "SHEEP": 2}
    assert outcome(2, 1) == 1.0
    assert outcome(1, 2) == 0.0
    assert outcome(1, 1) == 0.5


def test_console_cohort_summary_is_compact():
    summary = console_cohort_summary(
        {
            "total_replays": 2,
            "active_replays": 1,
            "replays": [
                {"episode_id": 1, "gate_active": True, "recorded_outcome": 1.0},
                {"episode_id": 2, "gate_active": False, "recorded_outcome": 0.0},
            ],
        }
    )
    assert "replays" not in summary
    assert summary["active_episode_ids"] == [1]
    assert summary["loss_episode_ids"] == [2]


def test_observed_opponent_animals_uses_public_opponent_farm():
    observation = {
        "farms": [
            {"tiles": [[{"animal": "GOOSE"}]]},
            {
                "tiles": [
                    [{"animal": "COW"}, {"animal": "COW"}],
                    [{"animal": "SHEEP"}, None],
                ]
            },
        ]
    }
    assert observed_opponent_animals(observation, 0) == {"COW": 2, "SHEEP": 1}


def test_classify_replay_matches_exact_gate(tmp_path):
    observation = {
        "farms": [
            {"tiles": [[None]]},
            {
                "tiles": [
                    [
                        {"animal": "COW"},
                        {"animal": "COW"},
                        {"animal": "COW"},
                        {"animal": "SHEEP"},
                        {"animal": "SHEEP"},
                    ]
                ]
            },
        ]
    }
    steps = [[{"observation": {}}, {"observation": {}}] for _ in range(121)]
    steps[120][0]["observation"] = observation
    replay = {
        "id": 42,
        "info": {
            "EpisodeId": 42,
            "seed": 7,
            "TeamNames": ["Auto Fermers", "Opponent"],
            "Agents": [{"Name": "Auto Fermers"}, {"Name": "Opponent"}],
        },
        "rewards": [100, 90],
        "steps": steps,
    }
    path = tmp_path / "replay.json"
    import json

    path.write_text(json.dumps(replay), encoding="utf-8")
    _, meta = classify_replay(
        path,
        ("Auto Fermers",),
        120,
        {"COW": 3, "SHEEP": 2},
    )
    assert meta.gate_active is True
    assert meta.recorded_outcome == 1.0
    assert meta.opponent_animals == {"COW": 3, "SHEEP": 2}

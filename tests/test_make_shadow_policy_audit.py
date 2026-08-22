import tempfile
import random
import unittest
from pathlib import Path

from tools.make_shadow_policy_audit import render_audit


BASE = '''import random
def agent(obs, configuration=None):
    random.random()
    return {"farmer": ["PASS"], "hands": [["PASS"]], "market": []}
'''

CANDIDATE = '''import random
def agent(obs, configuration=None):
    random.random()
    action = ["WATER"] if obs["hour"] == 2 else ["PASS"]
    return {"farmer": action, "hands": [["PASS"]], "market": []}
'''


class ShadowPolicyAuditTests(unittest.TestCase):
    def render(
        self,
        base_source=BASE,
        candidate_source=CANDIDATE,
        execute_operations=(),
        execute_start=0,
        execute_stop=720,
        drop_only_items=(),
        drop_max_total=None,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        base = root / "base.py"
        candidate = root / "candidate.py"
        base.write_text(base_source, encoding="utf-8")
        candidate.write_text(candidate_source, encoding="utf-8")
        return render_audit(
            base,
            candidate,
            label="test",
            execute_operations=tuple(execute_operations),
            execute_start=execute_start,
            execute_stop=execute_stop,
            drop_only_items=tuple(drop_only_items),
            drop_max_total=drop_max_total,
        )

    def test_returns_base_and_records_shadow_divergence(self):
        namespace = {"__name__": "generated"}
        exec(compile(self.render(), "generated.py", "exec"), namespace)
        agent = namespace["agent"]
        for hour in range(4):
            action = agent(
                {
                    "day": 0,
                    "hour": hour,
                    "player": 0,
                    "farms": [
                        {
                            "farmer": [0, 0],
                            "hands": [[0, 0]],
                            "tiles": [[{"kind": "PLANT", "watered_today": False}]],
                        },
                        {"farmer": [0, 0], "hands": [], "tiles": [[None]]},
                    ],
                    "private": {"inventories": [{}, {}]},
                }
            )
            self.assertEqual(action["farmer"], ["PASS"])
        telemetry = agent.telemetry
        self.assertEqual(telemetry["turns"], 4)
        self.assertEqual(telemetry["joint_equal"], 3)
        self.assertEqual(telemetry["first_joint_divergence"], 2)
        self.assertEqual(telemetry["candidate_nonpass_for_base_pass"], 1)
        self.assertEqual(telemetry["candidate_service_for_base_pass"], 1)
        self.assertEqual(telemetry["candidate_immediate_valid_for_base_pass"], 1)
        self.assertEqual(
            telemetry["candidate_immediate_nonredundant_for_base_pass"], 1
        )
        self.assertEqual(telemetry["immediate_samples"][0]["step"], 2)
        self.assertTrue(telemetry["immediate_samples"][0]["valid"])
        self.assertEqual(telemetry["valid_immediate_samples"][0]["step"], 2)
        self.assertEqual(telemetry["longest_joint_equal_streak"], 2)

    def test_uses_seat_stable_day_hour_clock(self):
        namespace = {"__name__": "generated"}
        exec(compile(self.render(), "generated.py", "exec"), namespace)
        agent = namespace["agent"]
        agent({"step": 0, "day": 1, "hour": 2, "player": 1})
        self.assertEqual(agent.telemetry["first_joint_divergence"], 26)

    def test_candidate_rng_does_not_perturb_base_sequence(self):
        base_source = '''import random
def agent(obs, configuration=None):
    direction = "NORTH" if random.random() < 0.5 else "SOUTH"
    return {"farmer": [direction], "hands": [], "market": []}
'''
        candidate_source = '''import random
def agent(obs, configuration=None):
    for _ in range(7):
        random.random()
    return {"farmer": ["PASS"], "hands": [], "market": []}
'''
        namespace = {"__name__": "generated"}
        exec(
            compile(
                self.render(base_source, candidate_source), "generated.py", "exec"
            ),
            namespace,
        )
        expected_rng = random.Random(12345)
        expected = [
            "NORTH" if expected_rng.random() < 0.5 else "SOUTH" for _ in range(6)
        ]
        random.seed(12345)
        observed = [
            namespace["agent"]({"day": 0, "hour": hour, "player": 0})["farmer"][0]
            for hour in range(6)
        ]
        self.assertEqual(observed, expected)

    def test_executes_only_allowlisted_valid_action_for_passing_actor(self):
        namespace = {"__name__": "generated"}
        exec(
            compile(
                self.render(execute_operations=("water",)), "generated.py", "exec"
            ),
            namespace,
        )
        observation = {
            "day": 0,
            "hour": 2,
            "player": 0,
            "farms": [
                {
                    "farmer": [0, 0],
                    "hands": [[0, 0]],
                    "tiles": [[{"kind": "PLANT", "watered_today": False}]],
                },
                {"farmer": [0, 0], "hands": [], "tiles": [[None]]},
            ],
            "private": {"inventories": [{}, {}]},
        }
        action = namespace["agent"](observation)
        self.assertEqual(action["farmer"], ["WATER"])
        self.assertEqual(action["hands"], [["PASS"]])
        self.assertEqual(namespace["agent"].telemetry["executed"], 1)
        self.assertEqual(
            namespace["agent"].telemetry["executed_by_operation"], {"WATER": 1}
        )

    def test_executes_only_inside_half_open_step_window(self):
        namespace = {"__name__": "generated"}
        exec(
            compile(
                self.render(
                    execute_operations=("WATER",),
                    execute_start=2,
                    execute_stop=3,
                ),
                "generated.py",
                "exec",
            ),
            namespace,
        )
        observation = {
            "day": 0,
            "player": 0,
            "farms": [
                {
                    "farmer": [0, 0],
                    "hands": [],
                    "tiles": [[{"kind": "PLANT", "watered_today": False}]],
                },
                {"farmer": [0, 0], "hands": [], "tiles": [[None]]},
            ],
            "private": {"inventories": [{}]},
        }
        before = namespace["agent"]({**observation, "hour": 1})
        inside = namespace["agent"]({**observation, "hour": 2})
        after = namespace["agent"]({**observation, "hour": 3})
        self.assertEqual(before["farmer"], ["PASS"])
        self.assertEqual(inside["farmer"], ["WATER"])
        self.assertEqual(after["farmer"], ["PASS"])
        self.assertEqual(namespace["agent"].telemetry["executed"], 1)

    def test_drop_context_gate_rejects_mixed_or_large_inventory(self):
        candidate_source = '''def agent(obs, configuration=None):
    return {"farmer": ["DROP"], "hands": [], "market": []}
'''

        def run(inventory):
            namespace = {"__name__": "generated"}
            source = self.render(
                candidate_source=candidate_source,
                execute_operations=("DROP",),
                drop_only_items=("FERTILIZER",),
                drop_max_total=1,
            )
            exec(compile(source, "generated.py", "exec"), namespace)
            action = namespace["agent"](
                {
                    "day": 0,
                    "hour": 2,
                    "player": 0,
                    "farms": [
                        {"farmer": [0, 0], "hands": [], "tiles": [[None]]},
                        {"farmer": [0, 0], "hands": [], "tiles": [[None]]},
                    ],
                    "private": {"inventories": [inventory]},
                }
            )
            return action, namespace["agent"].telemetry

        accepted, accepted_telemetry = run({"FERTILIZER": 1})
        self.assertEqual(accepted["farmer"], ["DROP"])
        self.assertEqual(accepted_telemetry["executed"], 1)
        rejected, rejected_telemetry = run({"FERTILIZER": 3, "STRAWBERRY": 2})
        self.assertEqual(rejected["farmer"], ["PASS"])
        self.assertEqual(rejected_telemetry["executed"], 0)
        self.assertEqual(rejected_telemetry["filtered_by_context"], 1)

    def test_rejects_missing_policy_or_label(self):
        missing = Path("missing.py")
        with self.assertRaises(ValueError):
            render_audit(missing, missing, label="test")
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.py"
            policy.write_text(BASE, encoding="utf-8")
            with self.assertRaises(ValueError):
                render_audit(policy, policy, label="")
            with self.assertRaises(ValueError):
                render_audit(
                    policy,
                    policy,
                    label="test",
                    execute_operations=("TELEPORT",),
                )
            with self.assertRaises(ValueError):
                render_audit(policy, policy, label="test", drop_max_total=-1)
            with self.assertRaises(ValueError):
                render_audit(
                    policy,
                    policy,
                    label="test",
                    execute_start=10,
                    execute_stop=10,
                )


if __name__ == "__main__":
    unittest.main()

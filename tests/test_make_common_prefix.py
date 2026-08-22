import tempfile
import unittest
from pathlib import Path

from tools.make_common_prefix import render_common_prefix


BASE = """
def agent(obs, configuration=None):
    return {"farmer": ["EAST"], "hands": [["SOUTH"]], "market": [["HIRE"], ["BUY_PRODUCT", "WHEAT", 2]]}
"""

DONOR = """
def agent(obs, configuration=None):
    return {"farmer": ["WEST"], "hands": [["SOUTH"]], "market": [["HIRE"], ["BUY_ANIMAL", "COW", 1]]}
"""


class CommonPrefixTests(unittest.TestCase):
    def sources(self, root):
        base = root / "base.py"
        donor = root / "donor.py"
        base.write_text(BASE, encoding="utf-8")
        donor.write_text(DONOR, encoding="utf-8")
        return base, donor

    def load(self, source):
        namespace = {"__name__": "generated_common_prefix"}
        exec(compile(source, "generated.py", "exec"), namespace)
        return namespace["agent"]

    def test_consensus_uses_equal_actor_and_market_intersection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, donor = self.sources(Path(tmp))
            agent = self.load(render_common_prefix(base, donor, 2, "consensus", "base"))
            action = agent({"step": 0, "player": 0}, {})
            self.assertEqual(action["farmer"], ["PASS"])
            self.assertEqual(action["hands"], [["SOUTH"]])
            self.assertEqual(action["market"], [["HIRE"]])

    def test_branch_executes_after_shared_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, donor = self.sources(Path(tmp))
            agent = self.load(render_common_prefix(base, donor, 1, "base_field", "donor"))
            prefix = agent({"step": 0, "player": 0}, {})
            branch = agent({"step": 1, "player": 0}, {})
            self.assertEqual(prefix["farmer"], ["EAST"])
            self.assertEqual(prefix["market"], [["HIRE"]])
            self.assertEqual(branch["farmer"], ["WEST"])
            self.assertEqual(branch["market"][-1], ["BUY_ANIMAL", "COW", 1])

    def test_cross_component_mode_uses_base_field_and_donor_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, donor = self.sources(Path(tmp))
            agent = self.load(
                render_common_prefix(base, donor, 2, "base_field_donor_market", "base")
            )
            action = agent({"step": 0, "player": 0}, {})
            self.assertEqual(action["farmer"], ["EAST"])
            self.assertEqual(
                action["market"], [["HIRE"], ["BUY_ANIMAL", "COW", 1]]
            )

    def test_rejects_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, donor = self.sources(Path(tmp))
            with self.assertRaises(ValueError):
                render_common_prefix(base, donor, 0, "consensus", "base")
            with self.assertRaises(ValueError):
                render_common_prefix(base, donor, 1, "unknown", "base")


if __name__ == "__main__":
    unittest.main()

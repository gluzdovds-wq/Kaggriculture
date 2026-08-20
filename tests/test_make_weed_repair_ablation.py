import tempfile
import unittest
from pathlib import Path

from tools.make_weed_repair_ablation import MOON_OVERLAY, X544_OVERLAY


class WeedRepairAblationTests(unittest.TestCase):
    def test_moon_ablation_discards_repaired_action(self):
        self.assertIn("return baseline", MOON_OVERLAY)
        self.assertIn("_H09_ORIGINAL_REPAIR", MOON_OVERLAY)
        self.assertIn("kaggle_entrypoint = agent", MOON_OVERLAY)

    def test_x544_ablation_rebinds_embedded_repair(self):
        self.assertIn('_X540_NS["_weed_repair_action"] = _h09_no_weed_repair', X544_OVERLAY)
        self.assertIn("return baseline", X544_OVERLAY)
        self.assertIn("kaggle_entrypoint = agent", X544_OVERLAY)


if __name__ == "__main__":
    unittest.main()

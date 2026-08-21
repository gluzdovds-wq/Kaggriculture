import unittest

from tools.audit_same_turn_chains import classify


class SameTurnChainAuditTests(unittest.TestCase):
    def test_detects_plant_water_on_empty_tile(self):
        self.assertEqual(classify(["PLANT", "WHEAT"], ["WATER"], None), "PLANT→WATER")

    def test_detects_ripe_harvest_replant(self):
        tile = {"kind": "PLANT", "crop": "WHEAT", "yield_units": 3}
        self.assertEqual(
            classify(["HARVEST"], ["PLANT", "WHEAT"], tile),
            "HARVEST→PLANT",
        )

    def test_detects_matching_build_place(self):
        self.assertEqual(
            classify(["BUILD_BARN"], ["PLACE", "COW"], None),
            "BUILD_BARN→PLACE_COW",
        )
        self.assertIsNone(classify(["BUILD_COOP"], ["PLACE", "COW"], None))


if __name__ == "__main__":
    unittest.main()

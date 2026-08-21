import unittest

from tools.make_animal_counter_variant import render_variant


class AnimalCounterVariantTests(unittest.TestCase):
    def test_renders_bounded_stateful_substitution(self):
        source = "def agent(obs, configuration=None): return {}\n"
        generated = render_variant(
            source,
            fingerprint_step=112,
            start=264,
            stop=276,
            from_animal="COW",
            to_animal="SHEEP",
            label="n34",
        )
        self.assertIn("_AC_PENDING_PICKUP", generated)
        self.assertIn("_AC_PROFILE = 'uri'", generated)
        self.assertIn('_AC_FROM = \'COW\'', generated)
        self.assertIn('__version__ = "animal-counter-n34"', generated)

    def test_renders_johnson_profile(self):
        generated = render_variant(
            "def agent(obs, configuration=None): return {}\n",
            fingerprint_profile="johnson",
            fingerprint_step=12,
            start=168,
            stop=217,
            from_animal="SHEEP",
            to_animal="COW",
            label="n40",
        )
        self.assertIn("_AC_PROFILE = 'johnson'", generated)
        self.assertIn("250 <= money <= 320", generated)
        self.assertIn("animals.get(\"SHEEP\", 0) == 3", generated)

    def test_rejects_unknown_profile(self):
        with self.assertRaises(ValueError):
            render_variant(
                "",
                fingerprint_profile="unknown",
                fingerprint_step=12,
                start=168,
                stop=217,
                from_animal="SHEEP",
                to_animal="COW",
                label="bad-profile",
            )

    def test_rejects_empty_window(self):
        with self.assertRaises(ValueError):
            render_variant(
                "",
                fingerprint_step=112,
                start=276,
                stop=276,
                from_animal="COW",
                to_animal="SHEEP",
                label="bad",
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from tools.make_reactive_weed_cleaner import render_variant


class ReactiveWeedCleanerTests(unittest.TestCase):
    def test_renders_bounded_public_task(self):
        generated = render_variant(
            "def agent(obs, configuration=None): return {}\n",
            start=432,
            stop=696,
            min_weeds=3,
            allow_moving=True,
            extra_hire=False,
            label="n41",
        )
        self.assertIn("_RWC_START = 432", generated)
        self.assertIn("_RWC_ALLOW_MOVING = True", generated)
        self.assertIn("_RWC_EXTRA_HIRE = False", generated)
        self.assertIn("reactive_weed_cleaner_kaggle_entrypoint = agent", generated)
        compile(generated, "generated.py", "exec")

    def test_rejects_invalid_bounds(self):
        with self.assertRaises(ValueError):
            render_variant(
                "",
                start=700,
                stop=696,
                min_weeds=0,
                allow_moving=False,
                extra_hire=False,
                label="bad",
            )


if __name__ == "__main__":
    unittest.main()

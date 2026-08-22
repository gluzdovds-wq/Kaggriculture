import unittest

from rl.analyze_macro_vocabulary import label_key, summarize_rows, top_k_coverage
from collections import Counter


def row(agent: str, task: str, market: str) -> dict:
    return {
        "agent": agent,
        "label": {"task_macro": task, "market_macro": market},
    }


class MacroVocabularyTest(unittest.TestCase):
    def test_label_key_defaults_to_noop(self):
        self.assertEqual(label_key({}), ("pass", "none"))

    def test_top_k_coverage(self):
        counts = Counter({("a", "x"): 6, ("b", "y"): 3, ("c", "z"): 1})
        self.assertEqual(top_k_coverage(counts, 1), 0.6)
        self.assertEqual(top_k_coverage(counts, 2), 0.9)

    def test_decision_summary_excludes_only_full_noop(self):
        report = summarize_rows(
            [
                row("A", "pass", "none"),
                row("A", "pass", "sell"),
                row("A", "harvest", "none"),
                row("B", "pass", "none"),
            ]
        )
        self.assertEqual(report["overall"]["all_turns"]["rows"], 4)
        self.assertEqual(report["overall"]["decision_turns"]["rows"], 2)
        self.assertEqual(report["agents"]["A"]["decision_rate"], 2 / 3)
        self.assertEqual(
            report["overall"]["decision_turns"]["top_k_market_coverage"]["2"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from tools.collect_top_replays import first_json_document


class CollectTopReplaysTests(unittest.TestCase):
    def test_first_json_document_ignores_cli_hint(self):
        self.assertEqual(
            first_json_document('[{"id": 7}]\nUse "kaggle competitions replay 7"'),
            [{"id": 7}],
        )

    def test_first_json_document_accepts_empty_output(self):
        self.assertEqual(first_json_document("  \n"), [])


if __name__ == "__main__":
    unittest.main()

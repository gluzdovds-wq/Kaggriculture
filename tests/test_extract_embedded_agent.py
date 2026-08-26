import ast
import unittest

from tools.extract_embedded_agent import literal_string_parts


class LiteralStringPartsTests(unittest.TestCase):
    def expression(self, source: str):
        return ast.parse(f"payload = {source}").body[0].value

    def test_literal_tuple(self):
        self.assertEqual(literal_string_parts(self.expression("('a', 'b')")), ["a", "b"])

    def test_bare_literal_string(self):
        self.assertEqual(literal_string_parts(self.expression("'payload'")), ["payload"])

    def test_empty_join_of_literal_tuple(self):
        self.assertEqual(
            literal_string_parts(self.expression("''.join(('a', 'b'))")),
            ["a", "b"],
        )

    def test_rejects_nonempty_separator_and_dynamic_parts(self):
        self.assertIsNone(literal_string_parts(self.expression("'-'.join(('a', 'b'))")))
        self.assertIsNone(literal_string_parts(self.expression("''.join(parts)")))


if __name__ == "__main__":
    unittest.main()

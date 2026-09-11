from django.test import SimpleTestCase

from agent_ready.markdown.normalizer import normalize


class NormalizeTests(SimpleTestCase):
    def test_collapses_consecutive_blank_lines(self):
        self.assertEqual(normalize("one\n\n\n\ntwo"), "one\n\ntwo\n")

    def test_leading_and_trailing_blank_lines_are_stripped_except_the_final_newline(
        self,
    ):
        self.assertEqual(normalize("\n\none\n\n"), "one\n")

    def test_adjacent_list_items_stay_tight(self):
        self.assertEqual(normalize("- a\n\n- b"), "- a\n- b\n")

    def test_adjacent_metadata_lines_stay_tight(self):
        self.assertEqual(
            normalize("**Name:** Ada\n\n**Role:** Engineer"),
            "**Name:** Ada\n**Role:** Engineer\n",
        )

    def test_the_document_always_ends_with_a_single_newline(self):
        self.assertTrue(normalize("hello").endswith("\n"))
        self.assertFalse(normalize("hello").endswith("\n\n"))
        self.assertEqual(normalize("hello\n\n\n"), "hello\n")

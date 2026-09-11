from django.template import Context, Template

from agent_ready.markdown.escaping import (
    SafeMarkdown,
    escape_markdown,
    format_markdown,
    mark_markdown_safe,
    unescape_markdown,
)
from agent_ready.tests.base import AgentReadySiteTestCase


class EscapeMarkdownTests(AgentReadySiteTestCase):
    def test_escapes_each_special_character(self):
        self.assertEqual(escape_markdown(r"\*_[]()"), r"\\\*\_\[\]\(\)")

    def test_none_becomes_empty_safe_markdown(self):
        rendered = escape_markdown(None)
        self.assertEqual(rendered, "")
        self.assertIsInstance(rendered, SafeMarkdown)

    def test_round_trip_user_strings(self):
        samples = [
            r"plain",
            r"a * b _ c",
            r"link [text](url)",
            r"backslash \ and star *",
            r"\*_[]()",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(unescape_markdown(escape_markdown(sample)), sample)

    def test_unescape_none_is_empty_plain_str(self):
        rendered = unescape_markdown(None)
        self.assertEqual(rendered, "")
        self.assertIs(type(rendered), str)

    def test_escape_is_noop_on_safe_markdown(self):
        safe = mark_markdown_safe("**bold**")
        self.assertIs(escape_markdown(safe), safe)
        self.assertEqual(escape_markdown(safe), "**bold**")

    def test_safe_markdown_is_not_html_safe(self):
        self.assertFalse(hasattr(SafeMarkdown("x"), "__html__"))

    def test_adding_two_safe_strings_stays_safe(self):
        joined = mark_markdown_safe("a") + mark_markdown_safe("b")
        self.assertEqual(joined, "ab")
        self.assertIsInstance(joined, SafeMarkdown)

    def test_adding_unsafe_string_drops_safety(self):
        joined = mark_markdown_safe("a") + "*b*"
        self.assertEqual(joined, "a*b*")
        self.assertNotIsInstance(joined, SafeMarkdown)

    def test_format_markdown_escapes_args_and_keeps_urls_when_marked_safe(self):
        rendered = format_markdown(
            "[{}]({})",
            "Ada *Lovelace*",
            mark_markdown_safe("https://example.com/a(b)"),
        )
        self.assertEqual(rendered, r"[Ada \*Lovelace\*](https://example.com/a(b))")
        self.assertIsInstance(rendered, SafeMarkdown)

    def test_format_markdown_requires_args(self):
        with self.assertRaises(TypeError):
            format_markdown("[]")


class EscapeMarkdownFilterTests(AgentReadySiteTestCase):
    def render(self, template, **context):
        return Template("{% load agent_ready %}" + template).render(Context(context))

    def test_escape_markdown_filter(self):
        self.assertEqual(
            self.render("{{ value|escape_markdown }}", value="Ada *L*"),
            r"Ada \*L\*",
        )

    def test_unescape_markdown_filter(self):
        self.assertEqual(
            self.render(r"{{ value|unescape_markdown }}", value=r"Ada \*L\*"),
            "Ada *L*",
        )

    def test_markdown_safe_filter_skips_later_escape(self):
        self.assertEqual(
            self.render(
                "{{ value|markdown_safe|escape_markdown }}",
                value="**bold**",
            ),
            "**bold**",
        )

    def test_to_markdown_then_escape_does_not_escape_richtext_marks(self):
        from wagtail.rich_text import RichText

        rendered = self.render(
            "{{ value|to_markdown|escape_markdown }}",
            value=RichText("<p>Hello <b>there</b></p>"),
        )
        self.assertEqual(rendered, "Hello **there**")

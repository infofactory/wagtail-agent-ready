from datetime import datetime, timezone
from unittest.mock import patch

from django.template import Context, Template
from django.test import override_settings

from agent_ready.markdown.escaping import SafeMarkdown
from agent_ready.markdown.frontmatter import format_yaml_frontmatter, simple_yaml
from agent_ready.mixins import AgentReadyMixin
from agent_ready.test.models import AgentReadyPage
from agent_ready.tests.base import AgentReadySiteTestCase


def _load_frontmatter(text):
    import yaml

    lines = text.strip().splitlines()
    return yaml.safe_load("\n".join(lines[1:-1]))


class MixinFrontmatterTests(AgentReadySiteTestCase):
    def test_default_keys_include_title_published_and_locale(self):
        published = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
        self.page.last_published_at = published
        data = self.page.markdown_frontmatter()
        self.assertEqual(data["title"], "About")
        self.assertEqual(data["published"], published)
        self.assertEqual(data["locale"], "en")
        self.assertNotIn("search_description", data)

    def test_search_description_is_included_when_filled(self):
        self.page.search_description = "  A short teaser  "
        data = self.page.markdown_frontmatter()
        self.assertEqual(data["search_description"], "A short teaser")

    def test_search_description_is_omitted_when_blank(self):
        self.page.search_description = "   "
        self.assertNotIn("search_description", self.page.markdown_frontmatter())

    def test_published_is_omitted_when_missing(self):
        self.page.last_published_at = None
        self.assertNotIn("published", self.page.markdown_frontmatter())

    @override_settings(WAGTAIL_I18N_ENABLED=False)
    def test_locale_is_omitted_when_i18n_is_disabled(self):
        self.assertNotIn("locale", self.page.markdown_frontmatter())

    def test_page_type_override_adds_a_key_via_super(self):
        original = AgentReadyPage.markdown_frontmatter

        def extra(self):
            data = AgentReadyMixin.markdown_frontmatter(self)
            data["author"] = "Ada"
            return data

        AgentReadyPage.markdown_frontmatter = extra
        try:
            data = self.page.markdown_frontmatter()
        finally:
            AgentReadyPage.markdown_frontmatter = original
        self.assertEqual(data["title"], "About")
        self.assertEqual(data["author"], "Ada")


class FormatYamlFrontmatterTests(AgentReadySiteTestCase):
    def test_empty_or_none_mapping_is_empty(self):
        self.assertEqual(format_yaml_frontmatter({}), "")
        self.assertEqual(format_yaml_frontmatter(None), "")
        self.assertIsInstance(format_yaml_frontmatter({}), SafeMarkdown)

    def test_none_values_are_omitted(self):
        rendered = format_yaml_frontmatter({"title": "About", "author": None})
        self.assertIn("title", rendered)
        self.assertNotIn("author", rendered)
        self.assertNotIn("null", rendered)

    @patch("agent_ready.markdown.frontmatter.yaml_module", return_value=simple_yaml)
    def test_scalar_dumper_quotes_special_titles(self, _yaml):
        rendered = format_yaml_frontmatter(
            {
                "colon": "Hello: world",
                "quoted": 'Say "hi"',
                "star": "Ada *L*",
                "yes": "Yes",
            }
        )
        self.assertEqual(
            rendered,
            "\n".join(
                [
                    "---",
                    'colon: "Hello: world"',
                    'quoted: "Say \\"hi\\""',
                    'star: "Ada *L*"',
                    'yes: "Yes"',
                    "---",
                ]
            ),
        )
        self.assertIsInstance(rendered, SafeMarkdown)

    @patch("agent_ready.markdown.frontmatter.yaml_module", return_value=simple_yaml)
    def test_scalar_dumper_writes_lists_of_scalars(self, _yaml):
        rendered = format_yaml_frontmatter({"tags": ["news", "press"]})
        self.assertEqual(
            rendered,
            "\n".join(
                [
                    "---",
                    "tags:",
                    '- "news"',
                    '- "press"',
                    "---",
                ]
            ),
        )

    @patch("agent_ready.markdown.frontmatter.yaml_module", return_value=simple_yaml)
    def test_scalar_dumper_rejects_nested_values(self, _yaml):
        with self.assertRaises(TypeError) as ctx:
            format_yaml_frontmatter({"meta": {"author": "Ada"}})
        self.assertIn("[yaml]", str(ctx.exception))
        with self.assertRaises(TypeError):
            format_yaml_frontmatter({"tags": [["nested"]]})

    @patch("agent_ready.markdown.frontmatter.yaml_module", return_value=simple_yaml)
    def test_scalar_dumper_writes_iso_datetimes(self, _yaml):
        published = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
        rendered = format_yaml_frontmatter({"published": published})
        self.assertIn("2026-09-11 10:00:00+00:00", rendered)

    def test_simple_yaml_safe_dump_matches_pyyaml_call_shape(self):
        dumped = simple_yaml.safe_dump(
            {"title": "About"},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        self.assertEqual(dumped, 'title: "About"\n')
        self.assertEqual(simple_yaml.safe_dump({}), "{}\n")
        self.assertEqual(simple_yaml.safe_dump({"tags": []}), "tags: []\n")

    def test_pyyaml_dumps_a_tags_list(self):
        rendered = format_yaml_frontmatter(
            {"title": "About", "tags": ["news", "press"]}
        )
        loaded = _load_frontmatter(rendered)
        self.assertEqual(loaded["title"], "About")
        self.assertEqual(loaded["tags"], ["news", "press"])


class MarkdownFrontmatterTagTests(AgentReadySiteTestCase):
    def render(self, template, **context):
        return Template("{% load agent_ready %}" + template).render(Context(context))

    def test_tag_with_no_arg_uses_the_mixin_dict(self):
        self.page.last_published_at = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
        rendered = self.render("{% markdown_frontmatter %}", page=self.page)
        loaded = _load_frontmatter(rendered)
        self.assertEqual(loaded["title"], "About")
        self.assertEqual(loaded["locale"], "en")
        self.assertIn("published", loaded)

    def test_tag_with_a_dict_replaces_the_mixin_dict(self):
        rendered = self.render(
            "{% markdown_frontmatter custom %}",
            page=self.page,
            custom={"author": "Ada"},
        )
        loaded = _load_frontmatter(rendered)
        self.assertEqual(loaded, {"author": "Ada"})

    def test_tag_without_a_page_is_empty(self):
        self.assertEqual(self.render("{% markdown_frontmatter %}"), "")

    def test_existing_twin_is_not_auto_wrapped(self):
        response = self.client.get("/en/about.md")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertTrue(body.lstrip().startswith("# About"))
        self.assertNotIn("---", body)

    def test_served_twin_emits_frontmatter_when_the_tag_is_used(self):
        original = AgentReadyPage.markdown_template
        AgentReadyPage.markdown_template = "agent_ready_test/frontmatter.md"
        try:
            response = self.client.get("/en/about.md")
        finally:
            AgentReadyPage.markdown_template = original
        self.assertEqual(response.status_code, 200)
        loaded = _load_frontmatter(response.content.decode().split("\n\n", 1)[0])
        self.assertEqual(loaded["title"], "About")
        self.assertIn("# About", response.content.decode())

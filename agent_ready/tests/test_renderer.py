from django.template import Context, Template, TemplateDoesNotExist
from django.test import RequestFactory
from wagtail import blocks

from agent_ready.markdown.renderer import render_block, render_page
from agent_ready.markdown.serializers import (
    _SERIALIZERS,
    register_markdown_serializer,
)
from agent_ready.test.blocks import MethodWinsBlock, TwinTemplateBlock
from agent_ready.test.models import AgentReadyPage
from agent_ready.tests.base import AgentReadySiteTestCase


class RendererCascadeTests(AgentReadySiteTestCase):
    def test_block_to_markdown_wins_over_twin_md_template(self):
        block = MethodWinsBlock()
        rendered = render_block(block, "Hello")
        self.assertEqual(rendered, "FROM_METHOD:Hello")
        self.assertNotIn("FROM_TEMPLATE", rendered)

    def test_block_to_markdown_wins_over_a_registered_serializer(self):
        previous = _SERIALIZERS.get(MethodWinsBlock)
        register_markdown_serializer(
            MethodWinsBlock,
            lambda block, value, context: f"FROM_SERIALIZER:{value}",
        )
        try:
            rendered = render_block(MethodWinsBlock(), "Hello")
        finally:
            if previous is None:
                _SERIALIZERS.pop(MethodWinsBlock, None)
            else:
                register_markdown_serializer(MethodWinsBlock, previous)
        self.assertEqual(rendered, "FROM_METHOD:Hello")
        self.assertNotIn("FROM_SERIALIZER", rendered)

    def test_twin_md_template_wins_over_the_walker(self):
        block = TwinTemplateBlock()
        rendered = render_block(block, "Hello")
        self.assertEqual(rendered.strip(), "FROM_TWIN:Hello")

    def test_missing_block_twin_falls_through_to_the_walker(self):
        block = blocks.CharBlock()
        rendered = render_block(block, "Walker text")
        self.assertEqual(rendered, "Walker text")

    def test_derived_page_twin_renders_the_title(self):
        request = RequestFactory().get("/en/about.md")
        rendered = render_page(self.page, request)
        self.assertIn("# About", rendered)

    def test_missing_page_twin_raises_template_does_not_exist(self):
        request = RequestFactory().get("/en/about.md")
        original = AgentReadyPage.markdown_template
        AgentReadyPage.markdown_template = "agent_ready_test/does_not_exist.md"
        try:
            with self.assertRaises(TemplateDoesNotExist):
                render_page(self.page, request)
        finally:
            AgentReadyPage.markdown_template = original

    def test_non_html_page_template_raises_template_does_not_exist(self):
        request = RequestFactory().get("/en/about.md")
        original_md = AgentReadyPage.markdown_template
        original_html = AgentReadyPage.template
        AgentReadyPage.markdown_template = None
        AgentReadyPage.template = "agent_ready_test/agent_ready_page.jinja"
        try:
            with self.assertRaises(TemplateDoesNotExist):
                render_page(self.page, request)
        finally:
            AgentReadyPage.markdown_template = original_md
            AgentReadyPage.template = original_html

    def test_markdown_template_on_page_model_overrides_derived_name(self):
        original = AgentReadyPage.markdown_template
        AgentReadyPage.markdown_template = "agent_ready_test/override.md"
        try:
            response = self.client.get("/en/about.md")
        finally:
            AgentReadyPage.markdown_template = original
        self.assertIn(b"OVERRIDE About", response.content)

    def test_markdown_block_applies_the_same_cascade_to_streamfield_children(self):
        stream_block = blocks.StreamBlock(
            [
                ("method", MethodWinsBlock()),
                ("twin", TwinTemplateBlock()),
                ("plain", blocks.CharBlock()),
            ]
        )
        value = stream_block.to_python(
            [
                {"type": "method", "value": "A"},
                {"type": "twin", "value": "B"},
                {"type": "plain", "value": "C"},
            ]
        )
        template = Template("{% load agent_ready %}{% markdown_block stream %}")
        rendered = template.render(Context({"stream": value}))
        self.assertIn("FROM_METHOD:A", rendered)
        self.assertIn("FROM_TWIN:B", rendered)
        self.assertIn("C", rendered)

    def test_to_markdown_filter_applies_the_same_cascade_to_a_stream_block(self):
        stream_block = blocks.StreamBlock(
            [
                ("method", MethodWinsBlock()),
                ("twin", TwinTemplateBlock()),
                ("plain", blocks.CharBlock()),
            ]
        )
        value = stream_block.to_python(
            [
                {"type": "method", "value": "A"},
                {"type": "twin", "value": "B"},
                {"type": "plain", "value": "C"},
            ]
        )
        template = Template("{% load agent_ready %}{{ stream|to_markdown }}")
        rendered = template.render(Context({"stream": value}))
        self.assertIn("FROM_METHOD:A", rendered)
        self.assertIn("FROM_TWIN:B", rendered)
        self.assertIn("C", rendered)

    def test_markdown_block_on_a_missing_variable_is_empty(self):
        template = Template("{% load agent_ready %}[{% markdown_block missing %}]")
        self.assertEqual(template.render(Context({})), "[]")

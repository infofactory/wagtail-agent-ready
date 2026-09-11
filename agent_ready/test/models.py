from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

from agent_ready.mixins import AgentReadyMixin


class AgentReadyHomePage(AgentReadyMixin, Page):
    template = "agent_ready_test/agent_ready_home_page.html"

    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]


class AgentReadyPage(AgentReadyMixin, Page):
    template = "agent_ready_test/agent_ready_page.html"

    body = StreamField(
        [
            ("paragraph", blocks.RichTextBlock()),
            ("heading", blocks.CharBlock()),
        ],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]


class PlainPage(Page):
    """A page type without AgentReadyMixin."""

    template = "agent_ready_test/plain_page.html"


class NoAgentPage(Page):
    """Page type without AgentReadyMixin (HTML-only)."""

    template = "agent_ready_test/plain_page.html"


class AgentPage(AgentReadyMixin, Page):
    """Opted-in page that serves Markdown only."""

    serve_html = False
    template = "agent_ready_test/markdown_only_page.html"


class MarkdownOnlyPage(AgentReadyMixin, Page):
    serve_html = False
    template = "agent_ready_test/markdown_only_page.html"

    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

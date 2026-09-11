from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from agent_ready.test.models import (
    AgentPage,
    AgentReadyHomePage,
    AgentReadyPage,
    MarkdownOnlyPage,
    NoAgentPage,
    PlainPage,
)


MARKDOWN_CONTENT_TYPE = "text/markdown; charset=UTF-8"


def snippet_models_for_index_view():
    from wagtail.snippets.models import get_snippet_models

    try:
        from wagtail.snippets.views.snippets import get_snippet_models_for_index_view
    except ImportError:
        return [
            model
            for model in get_snippet_models()
            if not model.snippet_viewset.get_menu_item_is_registered()
        ]
    return get_snippet_models_for_index_view()


def link_parts(response):
    header = response.get("Link") or ""
    return [part.strip() for part in header.split(",") if part.strip()]


def has_link(response, rel, type_=None, url_contains=None):
    needle = f'rel="{rel}"'
    for part in link_parts(response):
        if needle not in part:
            continue
        if type_ and f'type="{type_}"' not in part:
            continue
        if url_contains and url_contains not in part:
            continue
        return True
    return False


class AgentReadySiteTestCase(WagtailPageTestCase):
    """Publish a small site tree shared by routing, Accept, and llms.txt tests."""

    def setUp(self):
        super().setUp()
        root = Page.get_first_root_node()
        self.home = AgentReadyHomePage(title="Home", slug="agent-home")
        root.add_child(instance=self.home)
        self.home.save_revision().publish()

        site = Site.objects.get(is_default_site=True)
        site.root_page = self.home
        site.hostname = "localhost"
        site.save()
        self.site = site

        self.page = AgentReadyPage(title="About", slug="about")
        self.home.add_child(instance=self.page)
        self.page.save_revision().publish()

        self.plain = PlainPage(title="Plain", slug="plain")
        self.home.add_child(instance=self.plain)
        self.plain.save_revision().publish()

        self.markdown_only = MarkdownOnlyPage(title="Secret", slug="secret")
        self.home.add_child(instance=self.markdown_only)
        self.markdown_only.save_revision().publish()

        self.no_agent = NoAgentPage(title="No agent", slug="no-agent")
        self.home.add_child(instance=self.no_agent)
        self.no_agent.save_revision().publish()

        self.agent_page = AgentPage(title="Agent", slug="agent")
        self.home.add_child(instance=self.agent_page)
        self.agent_page.save_revision().publish()

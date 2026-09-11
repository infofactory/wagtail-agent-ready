from django.test import RequestFactory, override_settings

from agent_ready.test.models import AgentReadyPage
from agent_ready.tests.base import MARKDOWN_CONTENT_TYPE, AgentReadySiteTestCase
from agent_ready.views import _route, resolve_markdown_page


class MarkdownRoutingTests(AgentReadySiteTestCase):
    def test_canonical_md_url_for_nested_live_page_returns_200(self):
        nested = AgentReadyPage(title="Team", slug="team")
        self.page.add_child(instance=nested)
        nested.save_revision().publish()

        response = self.client.get("/en/about/team.md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Team", response.content)

    def test_site_root_is_served_at_index_md(self):
        response = self.client.get("/index.md", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Home", response.content)

    def test_locale_prefixed_root_is_served_at_en_index_md(self):
        response = self.client.get("/en/index.md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Home", response.content)

    def test_locale_prefixed_child_is_served_at_en_slug_md(self):
        response = self.client.get("/en/about.md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# About", response.content)

    def test_slug_index_md_redirects_to_slug_md_and_preserves_query_string(self):
        response = self.client.get("/en/about/index.md?ref=nav")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/en/about.md?ref=nav")

    def test_index_md_does_not_301_when_already_canonical(self):
        response = self.client.get("/en/index.md")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Location"))

    def test_real_child_named_index_wins_over_index_md_alias(self):
        index_child = AgentReadyPage(title="Index child", slug="index")
        self.page.add_child(instance=index_child)
        index_child.save_revision().publish()

        response = self.client.get("/en/about/index.md")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# Index child", response.content)

    def test_unknown_md_path_returns_404(self):
        response = self.client.get("/en/does-not-exist.md")
        self.assertEqual(response.status_code, 404)

    def test_md_url_of_page_type_without_mixin_returns_404(self):
        response = self.client.get("/en/plain.md")
        self.assertEqual(response.status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_does_not_301_slug_md_to_slug_md_slash(self):
        response = self.client.get("/en/about.md")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Location"))

    def test_slug_md_slash_returns_404_and_does_not_loop(self):
        response = self.client.get("/en/about.md/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_md_pattern_does_not_steal_paths_from_wagtail_serve(self):
        response = self.client.get("/en/about/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"<h1>About</h1>", response.content)

    def test_retry_after_failed_index_strip_clears_route_cache(self):
        request = RequestFactory().get("/en/about/index.md")
        self.assertIsNone(_route(request, "missing/index"))
        self.assertIsNone(getattr(request, "_wagtail_route_for_request", "missing"))

        page, path = resolve_markdown_page(request, "about/index")
        self.assertEqual(page.pk, self.page.pk)
        self.assertEqual(path, "about")

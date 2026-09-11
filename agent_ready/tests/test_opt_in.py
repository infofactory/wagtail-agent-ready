from django.contrib.auth.models import Group
from wagtail.models import PageViewRestriction

from agent_ready.test.models import AgentReadyPage
from agent_ready.tests.base import MARKDOWN_CONTENT_TYPE, AgentReadySiteTestCase


class OptInAndRestrictionTests(AgentReadySiteTestCase):
    def test_draft_non_live_page_md_returns_404(self):
        draft = AgentReadyPage(title="Draft", slug="draft", live=False)
        self.home.add_child(instance=draft)

        response = self.client.get("/en/draft.md")
        self.assertEqual(response.status_code, 404)

    def test_serve_html_false_html_url_returns_404(self):
        response = self.client.get("/en/secret/")
        self.assertEqual(response.status_code, 404)

    def test_serve_html_false_md_url_returns_200(self):
        response = self.client.get("/en/secret.md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Secret", response.content)
        self.assertEqual(response["X-Robots-Tag"], "noindex, follow")

    def test_serve_html_false_accept_markdown_on_html_url_is_noindex(self):
        response = self.client.get("/en/secret/", HTTP_ACCEPT="text/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertEqual(response["X-Robots-Tag"], "noindex, follow")

    def test_password_view_restriction_on_html_also_applies_to_md(self):
        PageViewRestriction.objects.create(
            page=self.page,
            restriction_type=PageViewRestriction.PASSWORD,
            password="secret",
        )
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        self.assertEqual(html.status_code, markdown.status_code)
        self.assertNotIn(b"# About", markdown.content)

    def test_login_and_group_view_restriction_on_html_also_applies_to_md(self):
        PageViewRestriction.objects.create(
            page=self.page,
            restriction_type=PageViewRestriction.LOGIN,
        )
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        self.assertEqual(html.status_code, markdown.status_code)
        self.assertIn(html.status_code, (302, 303))

        self.page.view_restrictions.all().delete()
        group = Group.objects.create(name="agents")
        restriction = PageViewRestriction.objects.create(
            page=self.page,
            restriction_type=PageViewRestriction.GROUPS,
        )
        restriction.groups.add(group)

        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        self.assertEqual(html.status_code, markdown.status_code)
        self.assertIn(html.status_code, (302, 303))

    def test_non_get_methods_are_rejected_the_same_way_as_html(self):
        html = self.client.post("/en/about/")
        markdown = self.client.post("/en/about.md")
        self.assertEqual(html.status_code, markdown.status_code)

    def test_no_agent_page_stays_html_only_and_agent_page_is_markdown_only(self):
        html = self.client.get("/en/no-agent/")
        self.assertEqual(html.status_code, 200)
        self.assertIn("text/html", html["Content-Type"])
        self.assertEqual(self.client.get("/en/no-agent.md").status_code, 404)

        self.assertEqual(self.client.get("/en/agent/").status_code, 404)
        markdown = self.client.get("/en/agent.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertEqual(markdown["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Agent", markdown.content)

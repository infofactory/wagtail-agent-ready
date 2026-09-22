from agent_ready.test.models import ShadowedPage
from agent_ready.tests.base import (
    MARKDOWN_CONTENT_TYPE,
    AgentReadySiteTestCase,
    has_link,
)


class ShadowedServeTests(AgentReadySiteTestCase):
    def setUp(self):
        super().setUp()
        self.shadowed = ShadowedPage(title="Shadow", slug="shadow")
        self.home.add_child(instance=self.shadowed)
        self.shadowed.save_revision().publish()

    def test_html_response_still_gets_alternate_link_and_vary(self):
        response = self.client.get("/en/shadow/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h1>Blocked</h1>", response.content)
        self.assertTrue(
            has_link(
                response,
                "alternate",
                type_="text/markdown",
                url_contains="/en/shadow.md",
            )
        )
        self.assertIn("Accept", response.get("Vary", ""))

    def test_accept_markdown_skips_shadowing_serve(self):
        response = self.client.get("/en/shadow/", HTTP_ACCEPT="text/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Shadow", response.content)
        self.assertNotIn(b"Blocked", response.content)

    def test_md_url_skips_shadowing_serve(self):
        response = self.client.get("/en/shadow.md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Shadow", response.content)
        self.assertNotIn(b"Blocked", response.content)
        self.assertEqual(response["X-Robots-Tag"], "noindex, follow")

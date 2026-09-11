from agent_ready.tests.base import MARKDOWN_CONTENT_TYPE, AgentReadySiteTestCase


class AcceptNegotiationTests(AgentReadySiteTestCase):
    def test_accept_markdown_on_html_url_returns_markdown(self):
        response = self.client.get("/en/about/", HTTP_ACCEPT="text/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# About", response.content)
        self.assertFalse(response.has_header("X-Robots-Tag"))

    def test_accept_html_returns_html(self):
        response = self.client.get("/en/about/", HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"<h1>About</h1>", response.content)

    def test_accept_markdown_q0_does_not_switch_to_markdown(self):
        response = self.client.get(
            "/en/about/",
            HTTP_ACCEPT="text/html, text/markdown;q=0",
        )
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"<h1>About</h1>", response.content)

    def test_equal_q_values_prefer_markdown_when_both_listed(self):
        response = self.client.get(
            "/en/about/",
            HTTP_ACCEPT="text/html;q=0.8, text/markdown;q=0.8",
        )
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# About", response.content)

    def test_markdown_and_html_responses_both_send_vary_accept(self):
        html = self.client.get("/en/about/", HTTP_ACCEPT="text/html")
        markdown = self.client.get("/en/about.md")
        self.assertIn("Accept", html.get("Vary", ""))
        self.assertIn("Accept", markdown.get("Vary", ""))

    def test_accept_negotiation_on_non_opted_in_page_is_ignored(self):
        response = self.client.get("/en/plain/", HTTP_ACCEPT="text/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"<h1>Plain</h1>", response.content)

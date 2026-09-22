from django.template import Context, RequestContext, Template
from django.test import RequestFactory, override_settings
from wagtail.models import Locale, Page, Site
from wagtail.views import serve as wagtail_serve

from agent_ready.llms_txt.models import LlmsTxt
from agent_ready.test.models import AgentReadyHomePage, AgentReadyPage
from agent_ready.tests.base import AgentReadySiteTestCase, has_link


OTHER_HOST = "other.example"
MULTI_HOSTS = ["localhost", "testserver", OTHER_HOST]


class DiscoveryTests(AgentReadySiteTestCase):
    def create_document(self, locale=None, title="Site for agents", site=None):
        return LlmsTxt.objects.create(
            title=title,
            locale=locale or Locale.get_default(),
            site=site or self.site,
        )

    def add_site(self, hostname, site_name="Other"):
        root = Page.get_first_root_node()
        home = AgentReadyHomePage(
            title=f"{site_name} home",
            slug=hostname.replace(".", "-"),
        )
        root.add_child(instance=home)
        home.save_revision().publish()
        return Site.objects.create(
            hostname=hostname,
            port=80,
            root_page=home,
            is_default_site=False,
            site_name=site_name,
        )

    def render_head(self, path="/en/about/", page=None, http_host=None):
        request = RequestFactory().get(path)
        if http_host:
            request.META["HTTP_HOST"] = http_host
        return Template("{% load agent_ready %}{% agent_ready_head %}").render(
            RequestContext(request, {"page": page or self.page, "request": request})
        )

    def test_html_response_has_alternate_link_to_canonical_twin(self):
        response = self.client.get("/en/about/")
        self.assertTrue(
            has_link(
                response,
                "alternate",
                type_="text/markdown",
                url_contains="/en/about.md",
            )
        )

    def test_markdown_response_has_canonical_link_to_html_url(self):
        response = self.client.get("/en/about.md")
        self.assertTrue(
            has_link(
                response,
                "canonical",
                type_="text/html",
                url_contains="/en/about/",
            )
        )

    def test_md_url_sends_noindex_and_html_url_does_not(self):
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        self.assertFalse(html.has_header("X-Robots-Tag"))
        self.assertEqual(markdown["X-Robots-Tag"], "noindex, follow")

    def test_agent_ready_head_emits_alternate_only_when_page_has_a_twin(self):
        request = RequestFactory().get("/en/about/")
        template = Template("{% load agent_ready %}{% agent_ready_head %}")
        html = template.render(
            RequestContext(request, {"page": self.page, "request": request})
        )
        self.assertIn('rel="alternate"', html)
        self.assertIn('type="text/markdown"', html)
        self.assertIn("/en/about.md", html)

    def test_agent_ready_head_is_empty_on_pages_without_the_mixin(self):
        template = Template("{% load agent_ready %}{% agent_ready_head %}")
        html = template.render(Context({"page": self.plain}))
        self.assertEqual(html, "")

    def test_describedby_for_language_prefixed_path_points_at_lang_llms_txt(self):
        self.create_document()
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        self.assertTrue(has_link(html, "describedby", url_contains="/en/llms.txt"))
        self.assertTrue(has_link(markdown, "describedby", url_contains="/en/llms.txt"))

    def test_describedby_for_unprefixed_path_points_at_llms_txt(self):
        self.create_document()
        request = RequestFactory().get("/about/")
        request.META["HTTP_HOST"] = "localhost"
        response = wagtail_serve(request, "about")
        self.assertTrue(has_link(response, "describedby", url_contains="/llms.txt"))
        self.assertFalse(has_link(response, "describedby", url_contains="/en/llms.txt"))

    def test_agent_ready_head_emits_describedby_when_llms_txt_is_ready(self):
        self.create_document()
        html = self.render_head()
        self.assertIn('rel="describedby"', html)
        self.assertIn("/en/llms.txt", html)

    def test_describedby_is_omitted_when_llms_txt_does_not_resolve(self):
        self.create_document()
        with override_settings(ROOT_URLCONF="agent_ready.test.urls_no_llms_txt"):
            html = self.client.get("/en/about/")
            markdown = self.client.get("/en/about.md")
            head = self.render_head()
        self.assertFalse(has_link(html, "describedby"))
        self.assertFalse(has_link(markdown, "describedby"))
        self.assertNotIn("describedby", head)

    def test_describedby_is_emitted_when_a_llms_txt_route_is_mounted(self):
        with override_settings(ROOT_URLCONF="agent_ready.test.urls_stub_llms_txt"):
            html = self.client.get("/en/about/")
            markdown = self.client.get("/en/about.md")
            head = self.render_head()
            unprefixed = RequestFactory().get("/about/")
            unprefixed.META["HTTP_HOST"] = "localhost"
            served = wagtail_serve(unprefixed, "about")
        self.assertTrue(has_link(html, "describedby", url_contains="/llms.txt"))
        self.assertFalse(has_link(html, "describedby", url_contains="/en/llms.txt"))
        self.assertTrue(has_link(markdown, "describedby", url_contains="/llms.txt"))
        self.assertIn('rel="describedby"', head)
        self.assertIn("/llms.txt", head)
        self.assertNotIn("/en/llms.txt", head)
        self.assertTrue(has_link(served, "describedby", url_contains="/llms.txt"))
        self.assertFalse(has_link(served, "describedby", url_contains="/en/llms.txt"))

    def test_describedby_is_omitted_when_no_document_exists(self):
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        head = self.render_head()
        self.assertFalse(has_link(html, "describedby"))
        self.assertFalse(has_link(markdown, "describedby"))
        self.assertNotIn("describedby", head)

    def test_describedby_is_omitted_when_title_is_empty_or_whitespace(self):
        self.create_document(title="")
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        head = self.render_head()
        self.assertFalse(has_link(html, "describedby"))
        self.assertFalse(has_link(markdown, "describedby"))
        self.assertNotIn("describedby", head)

        LlmsTxt.objects.all().delete()
        self.create_document(title="   ")
        html = self.client.get("/en/about/")
        markdown = self.client.get("/en/about.md")
        head = self.render_head()
        self.assertFalse(has_link(html, "describedby"))
        self.assertFalse(has_link(markdown, "describedby"))
        self.assertNotIn("describedby", head)

    def test_describedby_is_emitted_when_prefixed_locale_falls_back_to_default(self):
        self.create_document(title="English doc")
        italian, _created = Locale.objects.get_or_create(language_code="it")
        self.create_document(locale=italian, title="   ")
        request = RequestFactory().get("/it/about/")
        request.META["HTTP_HOST"] = "localhost"
        response = wagtail_serve(request, "about")
        self.assertTrue(has_link(response, "describedby", url_contains="/it/llms.txt"))
        head = self.render_head(path="/it/about/", http_host="localhost")
        self.assertIn('rel="describedby"', head)
        self.assertIn("/it/llms.txt", head)

    @override_settings(ALLOWED_HOSTS=MULTI_HOSTS)
    def test_describedby_is_omitted_on_a_host_without_a_ready_document(self):
        self.create_document(title="Default host")
        other = self.add_site(OTHER_HOST)
        about = AgentReadyPage(title="Other about", slug="about")
        other.root_page.add_child(instance=about)
        about.save_revision().publish()
        response = self.client.get("/en/about/", HTTP_HOST=OTHER_HOST)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(has_link(response, "describedby"))
        head = self.render_head(http_host=OTHER_HOST)
        self.assertNotIn("describedby", head)

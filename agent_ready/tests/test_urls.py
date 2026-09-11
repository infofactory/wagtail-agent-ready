from unittest.mock import patch

from django.template import Context, Template
from django.test import RequestFactory, override_settings
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection
from wagtail.rich_text import RichText

from agent_ready.markdown.request import use_request
from agent_ready.markdown.richtext import richtext_to_markdown
from agent_ready.markdown.urls import (
    absolutize_markdown_links,
    absolutize_markdown_urls,
    markdown_path_for,
    markdown_url_for,
    rewrite_internal_links,
    with_md_extension,
)
from agent_ready.tests.base import AgentReadySiteTestCase


class GatedUrlTests(AgentReadySiteTestCase):
    def test_markdown_url_for_returns_none_for_a_page_without_the_mixin(self):
        self.assertIsNone(markdown_url_for(self.plain))

    def test_markdown_url_for_returns_none_for_a_non_live_page(self):
        self.page.unpublish()
        self.assertIsNone(markdown_url_for(self.page))

    def test_markdown_path_for_strips_the_trailing_slash_then_appends_md(self):
        self.assertEqual(markdown_path_for(self.page), "/en/about.md")

    def test_markdown_path_for_on_the_site_root_returns_index_md(self):
        self.assertEqual(markdown_path_for(self.home), "/en/index.md")

    def test_with_md_extension_leaves_urls_with_a_scheme_unchanged(self):
        self.assertEqual(
            with_md_extension("https://example.com/about"),
            "https://example.com/about",
        )

    def test_with_md_extension_leaves_urls_that_already_have_a_file_extension_unchanged(
        self,
    ):
        self.assertEqual(with_md_extension("/files/spec.pdf"), "/files/spec.pdf")

    def test_rewrite_internal_links_rewrites_only_opted_in_destinations(self):
        markdown = f"[About]({self.page.url}) and [Plain]({self.plain.url})"
        rewritten = rewrite_internal_links(markdown)
        self.assertIn(f"[About]({self.page.url.rstrip('/')}.md)", rewritten)
        self.assertIn(f"[Plain]({self.plain.url})", rewritten)

    def test_rewrite_internal_links_preserves_query_strings_and_fragments(self):
        url = f"{self.page.url.rstrip('/')}?q=1#top"
        rewritten = rewrite_internal_links(f"[About]({url})")
        self.assertEqual(rewritten, "[About](/en/about.md?q=1#top)")

    def test_absolutize_markdown_links_turns_path_relative_hrefs_into_absolute_urls(
        self,
    ):
        request = RequestFactory().get("/en/about.md")
        request.META["HTTP_HOST"] = "testserver"
        rewritten = absolutize_markdown_links("[About](/en/about.md)", request=request)
        self.assertEqual(rewritten, "[About](http://testserver/en/about.md)")

    def test_absolutize_markdown_links_leaves_urls_that_already_have_a_scheme_unchanged(
        self,
    ):
        request = RequestFactory().get("/en/about.md")
        rewritten = absolutize_markdown_links(
            "[Ex](https://example.com/a)", request=request
        )
        self.assertEqual(rewritten, "[Ex](https://example.com/a)")

    def test_to_markdown_url_filter_on_a_page_returns_the_twin_or_the_original_url(
        self,
    ):
        template = Template("{% load agent_ready %}{{ page|to_markdown_url }}")
        self.assertEqual(
            template.render(Context({"page": self.page})),
            "/en/about.md",
        )
        self.assertEqual(
            template.render(Context({"page": self.plain})),
            self.plain.url,
        )

    def test_to_markdown_filter_converts_richtext_and_is_a_noop_on_plain_text(self):
        template = Template("{% load agent_ready %}{{ value|to_markdown }}")
        self.assertEqual(
            template.render(Context({"value": RichText("<p><b>Hi</b></p>")})),
            "**Hi**",
        )
        self.assertEqual(
            template.render(Context({"value": "plain text"})), "plain text"
        )

    def test_rewrite_internal_links_does_not_rewrite_image_srcs(self):
        markdown = f"![About]({self.page.url}) and ![](/media/x.png)"
        self.assertEqual(rewrite_internal_links(markdown), markdown)

    def test_absolutize_markdown_urls_absolutizes_links_and_image_srcs(self):
        request = RequestFactory().get("/en/about.md")
        request.META["HTTP_HOST"] = "testserver"
        rewritten = absolutize_markdown_urls(
            "![Hero](/media/x.png) and [About](/en/about.md) and ![](/media/y.png)",
            request=request,
        )
        self.assertEqual(
            rewritten,
            "![Hero](http://testserver/media/x.png) and "
            "[About](http://testserver/en/about.md) and "
            "![](http://testserver/media/y.png)",
        )

    def test_to_markdown_filter_passes_the_bound_request(self):
        request = RequestFactory().get("/en/")
        seen = {}

        def capture(value, request=None):
            seen["request"] = request
            return richtext_to_markdown(value, request=request)

        with (
            use_request(request),
            patch(
                "agent_ready.templatetags.agent_ready.richtext_to_markdown",
                side_effect=capture,
            ),
        ):
            Template("{% load agent_ready %}{{ value|to_markdown }}").render(
                Context({"value": RichText("<p>Hi</p>")})
            )
        self.assertIs(seen["request"], request)

    def test_to_markdown_url_filter_passes_the_bound_request(self):
        request = RequestFactory().get("/en/")
        with (
            use_request(request),
            patch(
                "agent_ready.templatetags.agent_ready.markdown_url_for",
                wraps=markdown_url_for,
            ) as mocked,
        ):
            Template("{% load agent_ready %}{{ page|to_markdown_url }}").render(
                Context({"page": self.page})
            )
        self.assertIs(mocked.call_args.kwargs["request"], request)

    def _hero_image(self):
        collection = Collection.get_first_root_node()
        return Image.objects.create(
            title="Hero",
            file=get_test_image_file(),
            collection=collection,
        )

    def test_to_markdown_filter_in_a_twin_converts_richtext_image_embeds(self):
        image = self._hero_image()
        rendition = image.get_rendition("width-800")
        self.home.body = RichText(
            f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="Hero">'
        )
        self.home.save_revision().publish()
        response = self.client.get("/en/index.md")
        self.assertIn(f"![Hero]({rendition.url})", response.content.decode())

    def test_markdown_twins_keep_path_relative_image_srcs(self):
        image = self._hero_image()
        rendition = image.get_rendition("width-800")
        self.page.body = [
            {
                "type": "paragraph",
                "value": (
                    f'<p><a id="{self.home.pk}" linktype="page">Home</a></p>'
                    f'<embed embedtype="image" id="{image.pk}" '
                    f'format="fullwidth" alt="Hero">'
                ),
            }
        ]
        self.page.save_revision().publish()
        content = self.client.get("/en/about.md").content.decode()
        self.assertIn("](/en/index.md)", content)
        self.assertIn(f"![Hero]({rendition.url})", content)
        self.assertNotIn("http://", content)

    @override_settings(AGENT_READY_ABSOLUTE_MARKDOWN_URLS=True)
    def test_markdown_twins_absolutize_links_and_image_srcs_when_setting_is_on(self):
        image = self._hero_image()
        rendition = image.get_rendition("width-800")
        self.page.body = [
            {
                "type": "paragraph",
                "value": (
                    f'<p><a id="{self.home.pk}" linktype="page">Home</a></p>'
                    f'<embed embedtype="image" id="{image.pk}" '
                    f'format="fullwidth" alt="Hero">'
                ),
            }
        ]
        self.page.save_revision().publish()
        content = self.client.get("/en/about.md").content.decode()
        self.assertIn("](http://testserver/en/index.md)", content)
        self.assertIn(f"![Hero](http://testserver{rendition.url})", content)

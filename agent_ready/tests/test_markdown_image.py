from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection

from agent_ready.markdown.escaping import escape_markdown
from agent_ready.markdown.urls import absolutize_markdown_urls
from agent_ready.tests.base import AgentReadySiteTestCase


class MarkdownImageTagTests(AgentReadySiteTestCase):
    def _image(self, title="Hero"):
        collection = Collection.get_first_root_node()
        return Image.objects.create(
            title=title,
            file=get_test_image_file(),
            collection=collection,
        )

    def render(self, source, context):
        return Template("{% load agent_ready %}" + source).render(Context(context))

    def test_required_filter_spec_emits_alt_and_rendition_url(self):
        image = self._image()
        rendition = image.get_rendition("fill-600x338")
        alt = image.default_alt_text or "Hero"
        rendered = self.render(
            "{% markdown_image photo fill-600x338 %}",
            {"photo": image},
        )
        self.assertEqual(rendered, f"![{alt}]({rendition.url})")

    def test_alt_attribute_overrides_default_alt(self):
        image = self._image("Hero *shot*")
        rendition = image.get_rendition("fill-600x338")
        rendered = self.render(
            "{% markdown_image photo fill-600x338 alt=caption %}",
            {"photo": image, "caption": "Custom *alt*"},
        )
        self.assertEqual(rendered, rf"![Custom \*alt\*]({rendition.url})")
        self.assertNotIn(escape_markdown(image.title), rendered)

    def test_empty_alt_is_decorative(self):
        image = self._image()
        rendition = image.get_rendition("fill-600x338")
        rendered = self.render(
            "{% markdown_image photo fill-600x338 alt=caption %}",
            {"photo": image, "caption": ""},
        )
        self.assertEqual(rendered, f"![]({rendition.url})")

    def test_missing_image_is_empty(self):
        rendered = self.render(
            "{% markdown_image photo fill-600x338 %}",
            {"photo": None},
        )
        self.assertEqual(rendered, "")

    def test_missing_variable_is_empty(self):
        rendered = self.render("{% markdown_image photo fill-600x338 %}", {})
        self.assertEqual(rendered, "")

    def test_missing_filter_spec_is_a_syntax_error(self):
        with self.assertRaises(TemplateSyntaxError):
            Template("{% load agent_ready %}{% markdown_image photo %}")

    def test_as_assignment_is_a_syntax_error(self):
        with self.assertRaises(TemplateSyntaxError):
            Template(
                "{% load agent_ready %}{% markdown_image photo fill-600x338 as img %}"
            )

    def test_html_only_attrs_are_a_syntax_error(self):
        with self.assertRaises(TemplateSyntaxError):
            Template(
                '{% load agent_ready %}{% markdown_image photo fill-600x338 class="hero" %}'
            )

    def test_src_stays_relative_and_post_process_can_absolutize(self):
        image = self._image()
        rendition = image.get_rendition("fill-600x338")
        alt = image.default_alt_text or "Hero"
        rendered = self.render(
            "{% markdown_image photo fill-600x338 %}",
            {"photo": image},
        )
        self.assertEqual(rendered, f"![{alt}]({rendition.url})")
        request = RequestFactory().get("/")
        request.META["HTTP_HOST"] = "testserver"
        self.assertEqual(
            absolutize_markdown_urls(rendered, request=request),
            f"![{alt}](http://testserver{rendition.url})",
        )

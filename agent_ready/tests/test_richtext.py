from unittest.mock import patch

from django.core.files.base import ContentFile
from wagtail.documents.models import Document
from wagtail.images.formats import (
    Format,
    register_image_format,
    unregister_image_format,
)
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection
from wagtail.rich_text import RichText

from agent_ready.markdown.escaping import SafeMarkdown, escape_markdown
from agent_ready.markdown.richtext import richtext_to_markdown
from agent_ready.tests.base import AgentReadySiteTestCase


class RichTextConverterTests(AgentReadySiteTestCase):
    def convert(self, html):
        return richtext_to_markdown(html)

    def test_paragraphs_become_separated_blocks(self):
        self.assertEqual(
            self.convert("<p>One</p><p>Two</p>"),
            "One\n\nTwo",
        )

    def test_headings_become_atx_headings(self):
        html = "".join(f"<h{level}>H{level}</h{level}>" for level in range(1, 7))
        rendered = self.convert(html)
        for level in range(1, 7):
            self.assertIn(f"{'#' * level} H{level}", rendered)

    def test_bold_and_italic_marks(self):
        self.assertEqual(
            self.convert(
                "<p><b>bold</b> and <i>italic</i> and <strong>s</strong> <em>e</em></p>"
            ),
            "**bold** and *italic* and **s** *e*",
        )

    def test_unordered_and_ordered_lists_including_li_p_wrapping(self):
        unordered = self.convert("<ul><li><p>alpha</p></li><li><p>beta</p></li></ul>")
        ordered = self.convert("<ol><li><p>one</p></li><li><p>two</p></li></ol>")
        self.assertEqual(unordered, "- alpha\n- beta")
        self.assertEqual(ordered, "1. one\n2. two")

    def test_nested_lists_indent(self):
        html = "<ul><li>outer<ul><li>inner</li></ul></li></ul>"
        rendered = self.convert(html)
        self.assertIn("- outer", rendered)
        self.assertIn("  - inner", rendered)

    def test_hr_becomes_thematic_break(self):
        self.assertEqual(self.convert("<p>a</p><hr><p>b</p>"), "a\n\n---\n\nb")

    def test_br_becomes_a_line_break(self):
        self.assertEqual(self.convert("<p>a<br>b</p>"), "a\nb")

    def test_external_anchor_href(self):
        self.assertEqual(
            self.convert('<p><a href="https://example.com">Example</a></p>'),
            "[Example](https://example.com)",
        )

    def test_page_linktype_resolves_to_twin_when_opted_in(self):
        html = f'<a id="{self.page.pk}" linktype="page">About</a>'
        self.assertEqual(
            richtext_to_markdown(html),
            f"[About]({self.page.url.rstrip('/')}.md)",
        )

    def test_page_linktype_keeps_html_url_when_not_opted_in(self):
        html = f'<a id="{self.plain.pk}" linktype="page">Plain</a>'
        self.assertEqual(
            richtext_to_markdown(html),
            f"[Plain]({self.plain.url})",
        )

    def test_document_linktype_resolves_to_the_document_url(self):
        collection = Collection.get_first_root_node()
        document = Document.objects.create(
            title="Spec",
            file=ContentFile(b"hello", name="spec.txt"),
            collection=collection,
        )
        html = f'<a id="{document.pk}" linktype="document">Spec</a>'
        self.assertEqual(richtext_to_markdown(html), f"[Spec]({document.url})")

    def test_script_and_style_are_omitted(self):
        html = (
            "<style>body { color: red }</style><p>Visible</p><script>alert(1)</script>"
        )
        self.assertEqual(self.convert(html), "Visible")
        self.assertNotIn("color", self.convert(html))
        self.assertNotIn("alert", self.convert(html))

    def test_highlight_and_unknown_spans_unwrap_to_their_text(self):
        self.assertEqual(
            self.convert(
                '<p><span class="highlight">glow</span> and <mark>x</mark></p>'
            ),
            "glow and x",
        )

    def test_html_entities_are_unescaped(self):
        self.assertEqual(self.convert("<p>Tom &amp; Jerry</p>"), "Tom & Jerry")

    def test_converter_does_not_call_expand_db_html_before_resolving_linktype(self):
        html = f'<a id="{self.page.pk}" linktype="page">About</a>'
        with patch("wagtail.rich_text.expand_db_html") as expand:
            rendered = richtext_to_markdown(RichText(html))
        expand.assert_not_called()
        self.assertIn("/en/about.md", rendered)

    def test_strikethrough_marks(self):
        self.assertEqual(
            self.convert("<p><s>old</s> and <del>gone</del></p>"),
            "~~old~~ and ~~gone~~",
        )
        self.assertEqual(self.convert("<p><strike>x</strike></p>"), "~~x~~")

    def test_underline_super_sub_unwrap_to_text(self):
        self.assertEqual(
            self.convert("<p><u>under</u> E=mc<sup>2</sup> x<sub>i</sub></p>"),
            "under E=mc2 xi",
        )

    def test_draftail_table_does_not_emit_gfm(self):
        html = "<table><tr><th>Name</th><th>Role</th></tr><tr><td>Ada</td><td>Eng</td></tr></table>"
        rendered = self.convert(html)
        self.assertNotIn("| --- |", rendered)
        self.assertNotIn("| ---", rendered)
        self.assertIn("Name", rendered)
        self.assertIn("Ada", rendered)

    def test_footnote_linktype_unwraps_to_text(self):
        html = '<p>See <a id="1" linktype="footnote">1</a></p>'
        self.assertEqual(self.convert(html), "See 1")

    def test_pre_language_class_becomes_fenced_info_string(self):
        html = '<pre><code class="language-python">x</code></pre>'
        self.assertEqual(self.convert(html), "```python\nx\n```")

    def test_pre_without_language_stays_unlabeled_fence(self):
        self.assertEqual(self.convert("<pre>x</pre>"), "```\nx\n```")

    def test_inline_code_body_is_not_escaped(self):
        self.assertEqual(self.convert("<p><code>Ada *L*</code></p>"), "`Ada *L*`")

    def test_user_text_is_escaped_marks_are_not(self):
        rendered = self.convert("<p>Ada *L* and <b>there</b></p>")
        self.assertEqual(rendered, r"Ada \*L\* and **there**")
        self.assertIsInstance(rendered, SafeMarkdown)
        self.assertEqual(escape_markdown(rendered), rendered)

    def test_link_text_is_escaped_href_is_not(self):
        self.assertEqual(
            self.convert('<p><a href="https://example.com/a(b)">Ada *L*</a></p>'),
            r"[Ada \*L\*](https://example.com/a(b))",
        )

    def test_img_escapes_alt_not_src(self):
        self.assertEqual(
            self.convert('<img src="/media/hero.png" alt="Hero *shot*">'),
            r"![Hero \*shot\*](/media/hero.png)",
        )

    def test_media_embed_is_a_markdown_link(self):
        self.assertEqual(
            self.convert('<embed embedtype="media" url="https://youtu.be/abc">'),
            "[https://youtu.be/abc](https://youtu.be/abc)",
        )

    def test_unknown_embedtype_is_omitted(self):
        self.assertEqual(
            self.convert('<p>Hi</p><embed embedtype="other" id="1">'),
            "Hi",
        )


class RichTextImageEmbedTests(AgentReadySiteTestCase):
    def convert(self, html):
        return richtext_to_markdown(html)

    def _image(self, title="Hero"):
        collection = Collection.get_first_root_node()
        return Image.objects.create(
            title=title,
            file=get_test_image_file(),
            collection=collection,
        )

    def test_fullwidth_and_left_use_wagtail_filter_specs(self):
        image = self._image()
        fullwidth = image.get_rendition("width-800")
        left = image.get_rendition("width-500")
        self.assertNotEqual(fullwidth.url, left.url)
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="Hero">'
            ),
            f"![Hero]({fullwidth.url})",
        )
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="left" alt="Hero">'
            ),
            f"![Hero]({left.url})",
        )

    def test_custom_image_format_filter_spec(self):
        image = self._image()
        register_image_format(Format("wide", "Wide", "wide", "width-1200"))
        self.addCleanup(lambda: unregister_image_format("wide"))
        rendition = image.get_rendition("width-1200")
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="wide" alt="Hero">'
            ),
            f"![Hero]({rendition.url})",
        )

    def test_empty_alt_is_decorative(self):
        image = self._image()
        rendition = image.get_rendition("width-800")
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="">'
            ),
            f"![]({rendition.url})",
        )

    def test_missing_image_is_omitted(self):
        self.assertEqual(
            self.convert(
                '<embed embedtype="image" id="99999" format="fullwidth" alt="gone">'
            ),
            "",
        )

    def test_unknown_format_is_omitted(self):
        image = self._image()
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="not-a-format" alt="Hero">'
            ),
            "",
        )

    def test_alt_is_escaped_url_is_not(self):
        image = self._image("Hero *shot*")
        rendition = image.get_rendition("width-800")
        self.assertEqual(
            self.convert(
                f'<embed embedtype="image" id="{image.pk}" format="fullwidth" alt="Hero *shot*">'
            ),
            rf"![Hero \*shot\*]({rendition.url})",
        )

from django.core.files.base import ContentFile
from django.test import RequestFactory
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.documents.models import Document
from wagtail.embeds.blocks import EmbedBlock, EmbedValue
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection
from wagtail.rich_text import RichText

from agent_ready.markdown.escaping import SafeMarkdown, escape_markdown
from agent_ready.markdown.serializers import (
    _SERIALIZERS,
    register_markdown_serializer,
    serialize,
)
from agent_ready.test.blocks import NestedStructBlock
from agent_ready.tests.base import AgentReadySiteTestCase


class SerializerTests(AgentReadySiteTestCase):
    def serialize(self, block, value):
        return serialize(block, value, {})

    def test_structblock_renders_label_value_for_simple_children(self):
        block = blocks.StructBlock([("name", blocks.CharBlock(label="Name"))])
        value = block.to_python({"name": "Ada"})
        self.assertEqual(self.serialize(block, value), "**Name:** Ada")

    def test_structblock_renders_heading_plus_body_for_compound_children(self):
        block = blocks.StructBlock(
            [("details", NestedStructBlock(label="Details"))],
        )
        value = block.to_python({"details": {"note": "Nested"}})
        rendered = self.serialize(block, value)
        self.assertIn("### Details", rendered)
        self.assertIn("**Note:** Nested", rendered)

    def test_streamblock_joins_children_with_blank_line_and_drops_wrapper_divs(self):
        block = blocks.StreamBlock(
            [
                ("one", blocks.CharBlock()),
                ("two", blocks.CharBlock()),
            ]
        )
        value = block.to_python(
            [
                {"type": "one", "value": "First"},
                {"type": "two", "value": "Second"},
            ]
        )
        rendered = self.serialize(block, value)
        self.assertEqual(rendered, "First\n\nSecond")
        self.assertNotIn("<div", rendered)

    def test_listblock_of_simple_values_renders_dash_item(self):
        block = blocks.ListBlock(blocks.CharBlock())
        value = block.to_python(["alpha", "beta"])
        self.assertEqual(self.serialize(block, value), "- alpha\n- beta")

    def test_listblock_of_compound_values_does_not_force_a_bullet_list(self):
        block = blocks.ListBlock(NestedStructBlock())
        value = block.to_python([{"note": "one"}, {"note": "two"}])
        rendered = self.serialize(block, value)
        self.assertNotIn("- ", rendered)
        self.assertIn("**Note:** one", rendered)
        self.assertIn("**Note:** two", rendered)

    def test_richtextblock_delegates_to_the_richtext_converter(self):
        block = blocks.RichTextBlock()
        value = RichText("<p>Hello <b>there</b></p>")
        self.assertEqual(self.serialize(block, value), "Hello **there**")

    def test_rawhtmlblock_delegates_to_the_richtext_converter(self):
        block = blocks.RawHTMLBlock()
        self.assertEqual(
            self.serialize(block, "<p>Raw <em>html</em></p>"),
            "Raw *html*",
        )

    def test_rawhtmlblock_omits_script_and_style(self):
        block = blocks.RawHTMLBlock()
        html = (
            "<style>.hero { display: none }</style>"
            "<p>Intro</p>"
            "<script>window.track()</script>"
        )
        rendered = self.serialize(block, html)
        self.assertEqual(rendered, "Intro")
        self.assertNotIn("hero", rendered)
        self.assertNotIn("track", rendered)

    def test_blockquoteblock_renders_quoted_lines(self):
        block = blocks.BlockQuoteBlock()
        self.assertEqual(
            self.serialize(block, "line one\nline two"),
            "> line one\n> line two",
        )

    def test_pagechooserblock_links_to_the_twin_when_target_is_opted_in(self):
        block = blocks.PageChooserBlock()
        rendered = self.serialize(block, self.page)
        self.assertEqual(rendered, f"[About]({self.page.url.rstrip('/')}.md)")

    def test_pagechooserblock_keeps_the_html_url_when_target_is_not_opted_in(self):
        block = blocks.PageChooserBlock()
        rendered = self.serialize(block, self.plain)
        self.assertEqual(rendered, f"[Plain]({self.plain.url})")

    def test_documentchooserblock_renders_title_url(self):
        collection = Collection.get_first_root_node()
        document = Document.objects.create(
            title="Spec",
            file=ContentFile(b"hello", name="spec.txt"),
            collection=collection,
        )
        block = DocumentChooserBlock()
        rendered = self.serialize(block, document)
        self.assertEqual(rendered, f"[Spec]({document.url})")

    def test_imagechooserblock_renders_alt_and_original_rendition_url(self):
        collection = Collection.get_first_root_node()
        image = Image.objects.create(
            title="Hero",
            file=get_test_image_file(),
            collection=collection,
        )
        rendition = image.get_rendition("original")
        block = ImageChooserBlock()
        rendered = self.serialize(block, image)
        self.assertEqual(
            rendered, f"![{image.default_alt_text or 'Hero'}]({rendition.url})"
        )

    def test_embedblock_renders_title_url(self):
        block = EmbedBlock()
        value = EmbedValue("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        rendered = self.serialize(block, value)
        self.assertEqual(
            rendered,
            "[https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)",
        )

    def test_staticblock_renders_empty(self):
        block = blocks.StaticBlock()
        self.assertEqual(self.serialize(block, None), "")
        self.assertEqual(self.serialize(block, "ignored"), "")

    def test_empty_and_null_values_are_omitted(self):
        block = blocks.StructBlock(
            [
                ("name", blocks.CharBlock(label="Name", required=False)),
                ("bio", blocks.TextBlock(label="Bio", required=False)),
            ]
        )
        value = block.to_python({"name": "", "bio": None})
        self.assertEqual(self.serialize(block, value), "")

    def test_charblock_escapes_markdown_punctuation(self):
        block = blocks.CharBlock()
        rendered = self.serialize(block, r"Ada *L*_ [x](y)")
        self.assertEqual(rendered, r"Ada \*L\*\_ \[x\]\(y\)")
        self.assertIsInstance(rendered, SafeMarkdown)
        self.assertEqual(escape_markdown(rendered), rendered)

    def test_structblock_escapes_labels(self):
        block = blocks.StructBlock([("name", blocks.CharBlock(label="Name *"))])
        value = block.to_python({"name": "Ada"})
        self.assertEqual(self.serialize(block, value), r"**Name \*:** Ada")

    def test_pagechooserblock_escapes_title_not_url(self):
        block = blocks.PageChooserBlock()
        self.page.title = "About *us*"
        href = self.page.url.rstrip("/") + ".md"
        self.assertEqual(self.serialize(block, self.page), rf"[About \*us\*]({href})")

    def test_blockquoteblock_escapes_text(self):
        block = blocks.BlockQuoteBlock()
        self.assertEqual(self.serialize(block, "line *one*"), r"> line \*one\*")

    def test_richtextblock_marks_stay_unescaped(self):
        block = blocks.RichTextBlock()
        rendered = self.serialize(block, RichText("<p>Hello <b>there</b></p>"))
        self.assertEqual(rendered, "Hello **there**")
        self.assertEqual(escape_markdown(rendered), "Hello **there**")

    def test_imagechooserblock_escapes_alt(self):
        collection = Collection.get_first_root_node()
        image = Image.objects.create(
            title="Hero *shot*",
            file=get_test_image_file(),
            collection=collection,
        )
        rendition = image.get_rendition("original")
        block = ImageChooserBlock()
        alt = image.default_alt_text or "Hero *shot*"
        self.assertEqual(
            self.serialize(block, image),
            f"![{escape_markdown(alt)}]({rendition.url})",
        )

    def test_imagechooserblock_stays_relative_when_request_is_present(self):
        collection = Collection.get_first_root_node()
        image = Image.objects.create(
            title="Hero",
            file=get_test_image_file(),
            collection=collection,
        )
        rendition = image.get_rendition("original")
        request = RequestFactory().get("/")
        request.META["HTTP_HOST"] = "testserver"
        rendered = serialize(ImageChooserBlock(), image, {"request": request})
        self.assertEqual(
            rendered, f"![{image.default_alt_text or 'Hero'}]({rendition.url})"
        )
        self.assertNotIn("http://", rendered)


class BuiltinFieldSerializerTests(AgentReadySiteTestCase):
    def serialize(self, block, value):
        return serialize(block, value, {})

    def test_choiceblock_uses_label_not_stored_value(self):
        block = blocks.ChoiceBlock(choices=[("draft", "Draft"), ("live", "Live")])
        self.assertEqual(self.serialize(block, "live"), "Live")

    def test_choiceblock_walks_optgroups(self):
        block = blocks.ChoiceBlock(
            choices=[("Group", [("a", "Alpha"), ("b", "Beta")])],
        )
        self.assertEqual(self.serialize(block, "b"), "Beta")

    def test_choiceblock_unknown_value_is_escaped(self):
        block = blocks.ChoiceBlock(choices=[("draft", "Draft")])
        self.assertEqual(self.serialize(block, "wat *x*"), r"wat \*x\*")

    def test_multiplechoiceblock_joins_labels(self):
        block = blocks.MultipleChoiceBlock(
            choices=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
        )
        self.assertEqual(self.serialize(block, ["a", "c"]), "Alpha, Gamma")

    def test_date_datetime_time_use_django_formats(self):
        from datetime import date, datetime, time

        from django.utils import formats, timezone

        day = date(2024, 1, 15)
        self.assertEqual(
            self.serialize(blocks.DateBlock(), day),
            formats.date_format(day),
        )
        self.assertNotEqual(self.serialize(blocks.DateBlock(), day), "2024-01-15")

        moment = timezone.make_aware(datetime(2024, 1, 15, 14, 30))
        self.assertEqual(
            self.serialize(blocks.DateTimeBlock(), moment),
            formats.date_format(timezone.localtime(moment), "DATETIME_FORMAT"),
        )
        clock = time(14, 30)
        self.assertEqual(
            self.serialize(blocks.TimeBlock(), clock),
            formats.time_format(clock),
        )

    def test_urlblock_and_emailblock_are_autolinks(self):
        self.assertEqual(
            self.serialize(blocks.URLBlock(), "https://example.com/a(b)"),
            "<https://example.com/a(b)>",
        )
        self.assertEqual(
            self.serialize(blocks.EmailBlock(), "ada@example.com"),
            "<ada@example.com>",
        )

    def test_snippetchooserblock_uses_str_and_escapes(self):
        from wagtail.snippets.blocks import SnippetChooserBlock

        class Person:
            def __str__(self):
                return "Ada *Lovelace*"

        block = SnippetChooserBlock("wagtailcore.Page")
        self.assertEqual(self.serialize(block, Person()), r"Ada \*Lovelace\*")


class ImageBlockSerializerTests(AgentReadySiteTestCase):
    def serialize(self, block, value):
        return serialize(block, value, {})

    def _image(self, title="Hero"):
        collection = Collection.get_first_root_node()
        return Image.objects.create(
            title=title,
            file=get_test_image_file(),
            collection=collection,
        )

    def test_imageblock_uses_fill_spec_and_contextual_alt(self):
        from wagtail.images.blocks import ImageBlock

        image = self._image()
        block = ImageBlock()
        value = block.to_python(
            {"image": image.pk, "decorative": False, "alt_text": "Hero *alt*"},
        )
        rendition = image.get_rendition("fill-600x338")
        self.assertEqual(
            self.serialize(block, value), rf"![Hero \*alt\*]({rendition.url})"
        )
        original = image.get_rendition("original")
        self.assertNotEqual(rendition.url, original.url)

    def test_imageblock_decorative_uses_empty_alt(self):
        from wagtail.images.blocks import ImageBlock

        image = self._image("Hero *shot*")
        block = ImageBlock()
        value = block.to_python(
            {"image": image.pk, "decorative": True, "alt_text": "ignored"},
        )
        rendition = image.get_rendition("fill-600x338")
        self.assertEqual(self.serialize(block, value), f"![]({rendition.url})")

    def test_imageblock_stays_relative_when_request_is_present(self):
        from wagtail.images.blocks import ImageBlock

        image = self._image()
        block = ImageBlock()
        value = block.to_python(
            {"image": image.pk, "decorative": False, "alt_text": "Hero"},
        )
        rendition = image.get_rendition("fill-600x338")
        request = RequestFactory().get("/")
        request.META["HTTP_HOST"] = "testserver"
        rendered = serialize(block, value, {"request": request})
        self.assertEqual(rendered, f"![Hero]({rendition.url})")
        self.assertNotIn("http://", rendered)


class TableSerializerTests(AgentReadySiteTestCase):
    def serialize(self, block, value):
        return serialize(block, value, {})

    def test_tableblock_with_header_row_and_caption(self):
        from wagtail.contrib.table_block.blocks import TableBlock

        block = TableBlock()
        value = {
            "data": [["Name *", "Role"], ["Ada", "Engineer"]],
            "first_row_is_table_header": True,
            "first_col_is_header": False,
            "table_caption": "People *",
        }
        rendered = self.serialize(block, value)
        self.assertEqual(
            rendered,
            "People \\*\n\n| Name \\* | Role |\n| --- | --- |\n| Ada | Engineer |",
        )

    def test_tableblock_without_header_uses_blank_header_row(self):
        from wagtail.contrib.table_block.blocks import TableBlock

        block = TableBlock()
        value = {
            "data": [["a", "b"], ["c", "d"]],
            "first_row_is_table_header": False,
            "first_col_is_header": False,
        }
        rendered = self.serialize(block, value)
        self.assertEqual(
            rendered,
            "|  |  |\n| --- | --- |\n| a | b |\n| c | d |",
        )

    def test_tableblock_first_column_header_is_bold(self):
        from wagtail.contrib.table_block.blocks import TableBlock

        block = TableBlock()
        value = {
            "data": [["Name", "Ada"], ["Role", "Engineer"]],
            "first_row_is_table_header": False,
            "first_col_is_header": True,
        }
        rendered = self.serialize(block, value)
        self.assertIn("| **Name** | Ada |", rendered)
        self.assertIn("| **Role** | Engineer |", rendered)

    def test_typed_tableblock_serializes_typed_cells(self):
        from wagtail.contrib.typed_table_block.blocks import TypedTableBlock

        block = TypedTableBlock([("text", blocks.CharBlock())])
        value = block.to_python(
            {
                "columns": [{"type": "text", "heading": "Name *"}],
                "rows": [{"values": ["Ada *"]}],
                "caption": "Cast",
            }
        )
        rendered = self.serialize(block, value)
        self.assertEqual(
            rendered,
            "Cast\n\n| Name \\* |\n| --- |\n| Ada \\* |",
        )

    def test_typed_table_value_serializes_without_the_parent_block(self):
        from django.template import Context, Template
        from wagtail.contrib.typed_table_block.blocks import TypedTableBlock

        from agent_ready.markdown.serializers import serialize_plain

        block = TypedTableBlock([("text", blocks.CharBlock())])
        value = block.to_python(
            {
                "columns": [{"type": "text", "heading": "Name *"}],
                "rows": [{"values": ["Ada *"]}],
                "caption": "Cast",
            }
        )
        expected = "Cast\n\n| Name \\* |\n| --- |\n| Ada \\* |"
        self.assertEqual(serialize_plain(value), expected)
        rendered = Template("{% load agent_ready %}{{ table|to_markdown }}").render(
            Context({"table": value})
        )
        self.assertEqual(rendered, expected)
        self.assertNotIn("TypedTable", rendered)


class BaseChooserBlock(blocks.CharBlock):
    pass


class SubChooserBlock(BaseChooserBlock):
    pass


class OtherSubChooserBlock(BaseChooserBlock):
    pass


class SerializerRegistryTests(AgentReadySiteTestCase):
    def setUp(self):
        super().setUp()
        self._previous = {}

    def tearDown(self):
        for block_class, previous in self._previous.items():
            if previous is None:
                _SERIALIZERS.pop(block_class, None)
            else:
                register_markdown_serializer(block_class, previous)
        super().tearDown()

    def register(self, block_class, fn):
        self._previous.setdefault(block_class, _SERIALIZERS.get(block_class))
        return register_markdown_serializer(block_class, fn)

    def serialize(self, block, value):
        return serialize(block, value, {})

    def test_registered_custom_block_class_is_used(self):
        self.register(
            BaseChooserBlock,
            lambda block, value, context: f"CUSTOM:{value}",
        )
        self.assertEqual(self.serialize(BaseChooserBlock(), "Ada"), "CUSTOM:Ada")

    def test_subclass_inherits_base_class_registration(self):
        self.register(
            BaseChooserBlock,
            lambda block, value, context: f"BASE:{value}",
        )
        self.assertEqual(self.serialize(SubChooserBlock(), "Ada"), "BASE:Ada")

    def test_subclass_registration_shadows_the_base(self):
        self.register(
            BaseChooserBlock,
            lambda block, value, context: f"BASE:{value}",
        )
        self.register(
            SubChooserBlock,
            lambda block, value, context: f"SUB:{value}",
        )
        self.assertEqual(self.serialize(SubChooserBlock(), "Ada"), "SUB:Ada")
        self.assertEqual(self.serialize(OtherSubChooserBlock(), "Ada"), "BASE:Ada")

    def test_reregistering_the_same_class_overrides(self):
        def first(block, value, context):
            return "first"

        self.register(BaseChooserBlock, first)
        self.register(
            BaseChooserBlock,
            lambda block, value, context: "second",
        )
        self.assertEqual(self.serialize(BaseChooserBlock(), "Ada"), "second")
        register_markdown_serializer(BaseChooserBlock, first)
        self.assertEqual(self.serialize(BaseChooserBlock(), "Ada"), "first")

    def test_can_be_used_as_a_decorator(self):
        self._previous.setdefault(BaseChooserBlock, _SERIALIZERS.get(BaseChooserBlock))

        @register_markdown_serializer(BaseChooserBlock)
        def serialize_chooser(block, value, context):
            return f"DECO:{value}"

        self.assertEqual(self.serialize(BaseChooserBlock(), "Ada"), "DECO:Ada")
        self.assertEqual(serialize_chooser(None, "Ada", {}), "DECO:Ada")

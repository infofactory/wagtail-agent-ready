from django.utils import formats, timezone
from django.utils.encoding import force_str
from wagtail import blocks
from wagtail.blocks.base import BoundBlock
from wagtail.blocks.list_block import ListValue
from wagtail.blocks.stream_block import StreamValue
from wagtail.blocks.struct_block import StructValue
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageBlock, ImageChooserBlock
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.snippets.blocks import SnippetChooserBlock

from agent_ready.markdown.escaping import (
    escape_markdown,
    format_markdown,
    mark_markdown_safe,
)
from agent_ready.markdown.richtext import richtext_to_markdown
from agent_ready.markdown.urls import markdown_url_for


try:
    from wagtail.embeds.blocks import EmbedBlock, EmbedValue
except ImportError:  # pragma: no cover
    EmbedBlock = None
    EmbedValue = type("EmbedValue", (), {})

try:
    from wagtail.contrib.table_block.blocks import TableBlock
except ImportError:  # pragma: no cover
    TableBlock = None

try:
    from wagtail.contrib.typed_table_block.blocks import TypedTableBlock
except ImportError:  # pragma: no cover
    TypedTableBlock = None


COMPOUND_BLOCK_TYPES = (blocks.StructBlock, blocks.StreamBlock, blocks.ListBlock)


def _image_model():
    from wagtail.images import get_image_model

    return get_image_model()


def _document_model():
    from wagtail.documents import get_document_model

    return get_document_model()


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, RichText) and not value.source:
        return True
    if isinstance(value, (list, tuple, StreamValue, ListValue)) and len(value) == 0:
        return True
    return False


def request_from(context):
    if not context:
        return None
    return context.get("request")


def serialize(block, value, context=None):
    """Serialize a block value using the render_basic mapping, without templates."""
    if is_empty(value):
        return mark_markdown_safe("")
    serializer = _serializer_for(block)
    return mark_markdown_safe(serializer(block, value, context or {}) or "")


def register_markdown_serializer(block_class, fn=None):
    """Register a walker serializer for ``block_class`` (MRO, last write wins).

    ``fn(block, value, context) -> str``. Does not override ``to_markdown()`` or
    a twin ``.md`` template.

    Call as ``register_markdown_serializer(Block, fn)`` or as a decorator::

        @register_markdown_serializer(PersonChooserBlock)
        def serialize_person(block, value, context): ...
    """

    def decorator(fn):
        _SERIALIZERS[block_class] = fn
        return fn

    if fn is None:
        return decorator
    return decorator(fn)


def _serializer_for(block):
    for cls in type(block).__mro__:
        if cls in _SERIALIZERS:
            return _SERIALIZERS[cls]
    return _serialize_default


def _render_child(child_block, child_value, context):
    """Apply the full cascade to a child (twin template, then walker)."""
    from agent_ready.markdown.renderer import render_block

    return render_block(child_block, child_value, context)


def _join_md(sep, parts):
    return mark_markdown_safe(sep.join(parts))


def _serialize_stream(block, value, context):
    parts = []
    for child in value:
        rendered = _render_child(child.block, child.value, context)
        if rendered:
            parts.append(rendered)
    return _join_md("\n\n", parts)


def _serialize_list(block, value, context):
    bound_blocks = (
        value.bound_blocks
        if isinstance(value, ListValue)
        else [block.child_block.bind(item) for item in value]
    )
    if bound_blocks and isinstance(block.child_block, COMPOUND_BLOCK_TYPES):
        parts = []
        for child in bound_blocks:
            rendered = _render_child(child.block, child.value, context)
            if rendered:
                parts.append(rendered)
        return _join_md("\n\n", parts)

    lines = []
    for child in bound_blocks:
        rendered = _render_child(child.block, child.value, context)
        if not rendered:
            continue
        indented = rendered.replace("\n", "\n  ")
        lines.append(f"- {indented}")
    return _join_md("\n", lines)


def _serialize_struct(block, value, context):
    lines = []
    child_blocks = block.child_blocks
    for name, child_block in child_blocks.items():
        child_value = (
            value.get(name) if hasattr(value, "get") else getattr(value, name, None)
        )
        rendered = serialize(child_block, child_value, context)
        if not rendered:
            continue
        label = child_block.label or name
        if isinstance(child_block, COMPOUND_BLOCK_TYPES) or "\n" in rendered:
            lines.append(format_markdown("### {}\n\n{}", label, rendered))
        else:
            lines.append(format_markdown("**{}:** {}", label, rendered))
    return _join_md("\n", lines)


def _serialize_richtext(block, value, context):
    return mark_markdown_safe(
        richtext_to_markdown(value, request=request_from(context))
    )


def _serialize_raw_html(block, value, context):
    return mark_markdown_safe(
        richtext_to_markdown(value, request=request_from(context))
    )


def _serialize_blockquote(block, value, context):
    text = force_str(value).strip()
    if not text:
        return mark_markdown_safe("")
    escaped = escape_markdown(text)
    return mark_markdown_safe(
        "\n".join(f"> {line}" if line else ">" for line in escaped.split("\n"))
    )


def _serialize_page(block, value, context):
    if not value:
        return mark_markdown_safe("")
    page = value.specific if hasattr(value, "specific") else value
    request = request_from(context)
    href = (
        markdown_url_for(page, request=request) or page.get_url(request=request) or ""
    )
    title = page.title
    if not href:
        return escape_markdown(title)
    return format_markdown("[{}]({})", title, mark_markdown_safe(href))


def _serialize_document(block, value, context):
    if not value:
        return mark_markdown_safe("")
    url = value.url
    title = getattr(value, "title", None) or getattr(value, "filename", url)
    if not url:
        return escape_markdown(title)
    return format_markdown("[{}]({})", title, mark_markdown_safe(url))


def _serialize_image(block, value, context):
    return _image_markdown(value)


def _serialize_image_block(block, value, context):
    if hasattr(value, "contextual_alt_text"):
        alt = value.contextual_alt_text or ""
    else:
        alt = (
            getattr(value, "default_alt_text", None)
            or getattr(value, "title", "")
            or ""
        )
    return _image_markdown(value, spec="fill-600x338", alt=alt)


def _serialize_embed(block, value, context):
    if not value:
        return mark_markdown_safe("")
    url = getattr(value, "url", None) or force_str(value)
    title = getattr(value, "title", None) or url
    if not url:
        return mark_markdown_safe("")
    return format_markdown("[{}]({})", title, mark_markdown_safe(url))


def _serialize_static(block, value, context):
    return mark_markdown_safe("")


def _choice_label(block, value):
    text_value = force_str(value)
    for key, label in block.field.choices:
        if isinstance(label, (list, tuple)):
            for subkey, sublabel in label:
                if value == subkey or text_value == force_str(subkey):
                    return force_str(sublabel)
        elif value == key or text_value == force_str(key):
            return force_str(label)
    return text_value


def _serialize_choice(block, value, context):
    return escape_markdown(_choice_label(block, value))


def _serialize_multiple_choice(block, value, context):
    labels = [_choice_label(block, item) for item in value]
    return escape_markdown(", ".join(labels))


def _serialize_date(block, value, context):
    return escape_markdown(formats.date_format(value))


def _serialize_datetime(block, value, context):
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return escape_markdown(formats.date_format(value, "DATETIME_FORMAT"))


def _serialize_time(block, value, context):
    return escape_markdown(formats.time_format(value))


def _serialize_url(block, value, context):
    url = force_str(value).strip()
    if not url:
        return mark_markdown_safe("")
    return format_markdown("<{}>", mark_markdown_safe(url))


def _serialize_email(block, value, context):
    email = force_str(value).strip()
    if not email:
        return mark_markdown_safe("")
    return format_markdown("<{}>", mark_markdown_safe(email))


def _serialize_snippet(block, value, context):
    if not value:
        return mark_markdown_safe("")
    return escape_markdown(force_str(value))


def _table_cell(text):
    return force_str(text or "").replace("\n", " ").replace("|", r"\|")


def _markdown_table_row(cells):
    return "| " + " | ".join(cells) + " |"


def _markdown_table_sep(count):
    return "| " + " | ".join("---" for _ in range(count)) + " |"


def _markdown_table(header, body, caption=""):
    if not header:
        return mark_markdown_safe("")
    lines = []
    if caption:
        lines.append(str(escape_markdown(caption)))
        lines.append("")
    lines.append(_markdown_table_row(header))
    lines.append(_markdown_table_sep(len(header)))
    width = len(header)
    for row in body:
        padded = list(row) + [""] * (width - len(row))
        lines.append(_markdown_table_row(padded[:width]))
    return _join_md("\n", lines)


def _serialize_table(block, value, context):
    if not value:
        return mark_markdown_safe("")
    data = value.get("data") or []
    if not data:
        return mark_markdown_safe("")
    first_row_is_header = value.get("first_row_is_table_header", False)
    first_col_is_header = value.get("first_col_is_header", False)
    caption = value.get("table_caption") or ""

    def cells_from(row):
        out = []
        for index, cell in enumerate(row or []):
            text = _table_cell(escape_markdown(cell or ""))
            if first_col_is_header and index == 0 and text:
                text = f"**{text}**"
            out.append(text)
        return out

    if first_row_is_header:
        header = cells_from(data[0])
        body = [cells_from(row) for row in data[1:]]
    else:
        width = max((len(row or []) for row in data), default=0)
        if not width:
            return mark_markdown_safe("")
        header = [""] * width
        body = [cells_from(row) for row in data]
    return _markdown_table(header, body, caption=caption)


def _serialize_typed_table(block, value, context):
    if not value or not value.columns:
        return mark_markdown_safe("")
    header = [
        _table_cell(escape_markdown(column.get("heading") or ""))
        for column in value.columns
    ]
    body = []
    for row in value.row_data:
        cells = []
        for column, cell_value in zip(value.columns, row["values"], strict=False):
            rendered = serialize(column["block"], cell_value, context)
            cells.append(_table_cell(rendered))
        body.append(cells)
    return _markdown_table(header, body, caption=value.caption or "")


def _serialize_default(block, value, context):
    return serialize_plain(value, context)


def serialize_plain(value, context=None):
    context = context or {}
    request = request_from(context)
    if is_empty(value):
        return mark_markdown_safe("")
    if isinstance(value, BoundBlock):
        return serialize(value.block, value.value, context)
    if isinstance(value, StreamValue):
        return serialize(value.stream_block, value, context)
    if isinstance(value, ListValue):
        return serialize(value.list_block, value, context)
    if isinstance(value, StructValue):
        return serialize(value.block, value, context)
    if isinstance(value, RichText):
        return mark_markdown_safe(richtext_to_markdown(value, request=request))
    image_model = _image_model()
    if isinstance(value, image_model):
        return _image_markdown(value)
    if isinstance(value, Page):
        return _serialize_page(None, value, context)
    document_model = _document_model()
    if isinstance(value, document_model):
        return _serialize_document(None, value, context)
    if isinstance(value, EmbedValue):
        return _serialize_embed(None, value, context)
    if hasattr(value, "url") and hasattr(value, "filename"):
        url = value.url
        title = getattr(value, "title", None) or value.filename
        if not url:
            return escape_markdown(title)
        return format_markdown("[{}]({})", title, mark_markdown_safe(url))
    if isinstance(value, bool):
        return mark_markdown_safe("true" if value else "false")
    return escape_markdown(force_str(value).strip())


def _image_markdown(image, spec="original", alt=None):
    if not image:
        return mark_markdown_safe("")
    if alt is None:
        alt = getattr(image, "default_alt_text", None) or image.title or ""
    try:
        from wagtail.images.shortcuts import get_rendition_or_not_found

        rendition = get_rendition_or_not_found(image, spec)
        url = rendition.url
        return format_markdown("![{}]({})", alt, mark_markdown_safe(url))
    except Exception:
        url = getattr(getattr(image, "file", None), "url", "")
        if not url:
            return mark_markdown_safe("")
        return format_markdown("![{}]({})", alt, mark_markdown_safe(url))


_SERIALIZERS = {}
register_markdown_serializer(blocks.StreamBlock, _serialize_stream)
register_markdown_serializer(blocks.ListBlock, _serialize_list)
register_markdown_serializer(blocks.StructBlock, _serialize_struct)
register_markdown_serializer(blocks.RichTextBlock, _serialize_richtext)
register_markdown_serializer(blocks.RawHTMLBlock, _serialize_raw_html)
register_markdown_serializer(blocks.BlockQuoteBlock, _serialize_blockquote)
register_markdown_serializer(blocks.PageChooserBlock, _serialize_page)
register_markdown_serializer(DocumentChooserBlock, _serialize_document)
register_markdown_serializer(ImageChooserBlock, _serialize_image)
register_markdown_serializer(ImageBlock, _serialize_image_block)
register_markdown_serializer(blocks.StaticBlock, _serialize_static)
register_markdown_serializer(blocks.ChoiceBlock, _serialize_choice)
register_markdown_serializer(blocks.MultipleChoiceBlock, _serialize_multiple_choice)
register_markdown_serializer(blocks.DateBlock, _serialize_date)
register_markdown_serializer(blocks.DateTimeBlock, _serialize_datetime)
register_markdown_serializer(blocks.TimeBlock, _serialize_time)
register_markdown_serializer(blocks.URLBlock, _serialize_url)
register_markdown_serializer(blocks.EmailBlock, _serialize_email)
register_markdown_serializer(SnippetChooserBlock, _serialize_snippet)
if EmbedBlock is not None:
    register_markdown_serializer(EmbedBlock, _serialize_embed)
if TableBlock is not None:
    register_markdown_serializer(TableBlock, _serialize_table)
if TypedTableBlock is not None:
    register_markdown_serializer(TypedTableBlock, _serialize_typed_table)

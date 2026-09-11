from django import template
from django.utils.safestring import mark_safe
from wagtail.images.models import Filter
from wagtail.models import Page

from agent_ready.markdown import escaping as markdown_escaping
from agent_ready.markdown.frontmatter import format_yaml_frontmatter
from agent_ready.markdown.renderer import render_value
from agent_ready.markdown.request import current_request
from agent_ready.markdown.richtext import richtext_to_markdown
from agent_ready.markdown.serializers import _image_markdown
from agent_ready.markdown.urls import (
    markdown_path_for,
    markdown_url_for,
    with_md_extension,
)
from agent_ready.mixins import AgentReadyMixin, _describedby_href


register = template.Library()


@register.filter
def collapse_whitespace(value):
    """Trim and replace consecutive whitespace (including newlines) with a single space."""
    if value is None:
        return ""
    return " ".join(str(value).split())


@register.filter
def escape_markdown(value):
    return markdown_escaping.escape_markdown(value)


@register.filter
def unescape_markdown(value):
    return markdown_escaping.unescape_markdown(value)


@register.filter
def markdown_safe(value):
    return markdown_escaping.mark_markdown_safe("" if value is None else value)


def _markdown_from_value(value, context=None):
    """Same cascade as {% markdown_block %}: method > twin .md > walker."""
    if value is None:
        return markdown_escaping.mark_markdown_safe("")
    parent = {}
    if context is not None:
        parent = context.flatten() if hasattr(context, "flatten") else dict(context)
    return markdown_escaping.mark_markdown_safe(
        render_value(value, context=parent) or ""
    )


def _filter_request_context():
    request = current_request()
    if request is None:
        return None, None
    return request, {"request": request}


@register.filter
def to_markdown(value):
    if value is None:
        return markdown_escaping.mark_markdown_safe("")
    from wagtail.rich_text import RichText

    request, context = _filter_request_context()
    if isinstance(value, RichText) or (
        isinstance(value, str) and ("<" in value and ">" in value)
    ):
        return markdown_escaping.mark_markdown_safe(
            richtext_to_markdown(value, request=request)
        )
    return _markdown_from_value(value, context)


@register.filter
def to_markdown_url(value):
    if value is None:
        return ""
    request = current_request()
    if isinstance(value, Page):
        return (
            markdown_url_for(value, request=request)
            or value.get_url(request=request)
            or ""
        )
    if isinstance(value, str):
        return with_md_extension(value, request=request)
    return value


@register.simple_tag(takes_context=True)
def markdown_frontmatter(context, mapping=None):
    if mapping is None:
        page = context.get("page") or context.get("self")
        if page is None:
            return markdown_escaping.mark_markdown_safe("")
        specific = getattr(page, "specific", page)
        if not isinstance(specific, AgentReadyMixin):
            return markdown_escaping.mark_markdown_safe("")
        mapping = specific.markdown_frontmatter()
    return format_yaml_frontmatter(mapping)


@register.simple_tag(takes_context=True)
def agent_ready_head(context):
    page = context.get("page") or context.get("self")
    request = context.get("request")
    if page is None or not isinstance(page.specific, AgentReadyMixin):
        return ""
    tags = []
    path = markdown_path_for(page.specific, request)
    if path:
        href = request.build_absolute_uri(path) if request is not None else path
        tags.append(f'<link rel="alternate" type="text/markdown" href="{href}">')
    describedby = _describedby_href(request)
    if describedby:
        tags.append(f'<link rel="describedby" href="{describedby}">')
    return mark_safe("\n".join(tags))


@register.tag
def markdown_block(parser, token):
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(
            f"{bits[0]!r} tag requires a single argument"
        )
    return MarkdownBlockNode(parser.compile_filter(bits[1]))


class MarkdownBlockNode(template.Node):
    def __init__(self, value):
        self.value = value

    def render(self, context):
        try:
            value = self.value.resolve(context)
        except template.VariableDoesNotExist:
            return ""
        return markdown_escaping.mark_markdown_safe(
            _markdown_from_value(value, context)
        )


@register.tag
def markdown_image(parser, token):
    bits = token.split_contents()
    tag_name = bits[0]
    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            f"{tag_name!r} tag requires an image and at least one filter spec"
        )
    image_expr = parser.compile_filter(bits[1])
    filter_specs = []
    alt_expr = None
    for bit in bits[2:]:
        if bit == "as":
            raise template.TemplateSyntaxError(f"{tag_name!r} does not support 'as'")
        if "=" in bit:
            name, value = bit.split("=", 1)
            if name != "alt":
                raise template.TemplateSyntaxError(
                    f"{tag_name!r} does not support the {name!r} attribute"
                )
            if alt_expr is not None:
                raise template.TemplateSyntaxError(
                    f"{tag_name!r} received multiple alt attributes"
                )
            alt_expr = parser.compile_filter(value)
            continue
        if Filter.spec_pattern.match(bit):
            filter_specs.append(bit)
            continue
        raise template.TemplateSyntaxError(
            "filter specs in image tags may only contain A-Z, a-z, 0-9, dots, "
            f"hyphens and underscores. (given filter: {bit})"
        )
    if not filter_specs:
        raise template.TemplateSyntaxError(
            f"{tag_name!r} tag requires at least one filter spec"
        )
    return MarkdownImageNode(image_expr, filter_specs, alt_expr)


class MarkdownImageNode(template.Node):
    def __init__(self, image_expr, filter_specs, alt_expr=None):
        self.image_expr = image_expr
        self.filter_specs = filter_specs
        self.alt_expr = alt_expr

    def render(self, context):
        try:
            image = self.image_expr.resolve(context)
        except template.VariableDoesNotExist:
            return ""
        if not image:
            return ""
        alt = None
        if self.alt_expr is not None:
            resolved = self.alt_expr.resolve(context)
            alt = "" if resolved is None else str(resolved)
        spec = "|".join(self.filter_specs)
        return markdown_escaping.mark_markdown_safe(
            _image_markdown(image, spec=spec, alt=alt)
        )

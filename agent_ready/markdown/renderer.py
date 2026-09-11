from django.template import Context, RequestContext, TemplateDoesNotExist
from django.template.backends.django import Template as DjangoTemplate
from django.template.loader import get_template

from agent_ready.markdown.escaping import mark_markdown_safe
from agent_ready.markdown.request import use_request
from agent_ready.markdown.serializers import serialize, serialize_plain


def template_exists(name):
    try:
        get_template(name)
        return True
    except TemplateDoesNotExist:
        return False


def html_to_md_name(template_name):
    if template_name and template_name.endswith(".html"):
        return template_name[:-5] + ".md"
    return None


def render_markdown_template(template_name, context, request=None):
    template = get_template(template_name)
    context = dict(context or {})
    # get_template() returns a backend wrapper whose render() only accepts a
    # dict. Render the underlying compiled template so we can turn autoescape
    # off (markdown must not HTML-escape *, _, [], etc.).
    with use_request(request):
        if isinstance(template, DjangoTemplate):
            if request is not None:
                ctx = RequestContext(request, context, autoescape=False)
            else:
                ctx = Context(context, autoescape=False)
            return template.template.render(ctx)
        return template.render(context, request)


def markdown_template_for_block(block, value, context):
    html_template = block.get_template(value, context=context)
    candidate = html_to_md_name(html_template)
    if candidate and template_exists(candidate):
        return candidate
    return None


def render_block(block, value, context=None):
    """Render a block: to_markdown() > twin .md template > walker."""
    context = dict(context or {})
    if hasattr(block, "to_markdown") and callable(block.to_markdown):
        return mark_markdown_safe(block.to_markdown(value, context) or "")

    template_name = markdown_template_for_block(block, value, context)
    if template_name:
        parent = dict(context)
        block_context = block.get_context(value, parent_context=parent)
        request = context.get("request")
        return mark_markdown_safe(
            render_markdown_template(template_name, block_context, request=request)
        )

    return serialize(block, value, context)


def render_value(value, context=None, block=None):
    """Render a BoundBlock, StreamValue, or plain value through the cascade."""
    from wagtail.blocks.base import BoundBlock
    from wagtail.blocks.list_block import ListValue
    from wagtail.blocks.stream_block import StreamValue
    from wagtail.blocks.struct_block import StructValue

    context = dict(context or {})
    if value is None:
        return mark_markdown_safe("")
    if isinstance(value, BoundBlock):
        return render_block(value.block, value.value, context)
    if isinstance(value, StreamValue):
        return render_block(value.stream_block, value, context)
    if isinstance(value, ListValue):
        return render_block(value.list_block, value, context)
    if isinstance(value, StructValue):
        return render_block(value.block, value, context)
    if block is not None:
        return render_block(block, value, context)
    return serialize_plain(value, context)


def render_page(page, request):
    template_name = page.get_markdown_template()
    context = page.get_markdown_context(request)
    return render_markdown_template(template_name, context, request=request)

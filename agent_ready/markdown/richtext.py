import re

from html.parser import HTMLParser

from wagtail.models import Page
from wagtail.rich_text import RichText

from agent_ready.markdown.escaping import (
    escape_markdown,
    format_markdown,
    mark_markdown_safe,
)


HEADINGS = {f"h{level}": level for level in range(1, 7)}
VOID = {"br", "hr", "img", "embed"}
SKIP = {
    "script",
    "style",
    "template",
    "head",
    "meta",
    "link",
    "noscript",
    "iframe",
    "object",
    "canvas",
    "svg",
}
INLINE_PARENTS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "a",
    "em",
    "i",
    "strong",
    "b",
    "span",
    "code",
    "u",
    "s",
    "del",
    "strike",
    "sup",
    "sub",
    "mark",
}
INLINE_UNWRAP = {"span", "u", "sup", "sub", "mark"}
BLOCK_UNWRAP = {"div", "section"}
_LANGUAGE_CLASS_RE = re.compile(r"(?:^|\s)(?:language|lang)-([A-Za-z0-9_+-]+)(?:\s|$)")


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node(None)
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self._stack[-1].children.append(node)
        if tag not in VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def richtext_to_markdown(value, request=None):
    if value is None:
        return mark_markdown_safe("")
    if isinstance(value, RichText):
        source = value.source or ""
    else:
        source = str(value)
    source = source.strip()
    if not source:
        return mark_markdown_safe("")
    builder = _TreeBuilder()
    builder.feed(source)
    builder.close()
    return mark_markdown_safe(
        _render_nodes(builder.root.children, request=request).strip()
    )


def _escape_text(text):
    return escape_markdown(text.replace("\xa0", " "))


def _render_nodes(nodes, request=None, parent=None):
    parts = []
    for node in nodes:
        rendered = _render_node(node, request=request, parent=parent)
        if rendered:
            parts.append(rendered)
    joiner = "" if parent in INLINE_PARENTS else "\n\n"
    if parent in {"ul", "ol"}:
        joiner = "\n"
    return mark_markdown_safe(joiner.join(parts))


def _render_node(node, request=None, parent=None):
    if isinstance(node, str):
        return _escape_text(node)

    tag = node.tag
    if tag in SKIP:
        return mark_markdown_safe("")
    if tag in HEADINGS:
        body = _inline(node.children, request=request, parent=tag)
        return mark_markdown_safe(f"{'#' * HEADINGS[tag]} {body}".rstrip())
    if tag == "p":
        return _inline(node.children, request=request, parent="p")
    if tag == "blockquote":
        inner = _render_nodes(node.children, request=request, parent="blockquote")
        lines = inner.split("\n")
        return mark_markdown_safe(
            "\n".join(f"> {line}" if line else ">" for line in lines)
        )
    if tag == "ul":
        return _render_list(node, ordered=False, request=request)
    if tag == "ol":
        return _render_list(node, ordered=True, request=request)
    if tag == "li":
        return _inline(node.children, request=request, parent="li")
    if tag == "pre":
        return _render_pre(node)
    if tag == "hr":
        return mark_markdown_safe("---")
    if tag == "br":
        return mark_markdown_safe("\n")
    if tag == "img":
        return _render_img(node)
    if tag == "embed":
        return _render_embed(node, request=request)
    if tag == "a":
        return _render_link(node, request=request)
    if tag in {"strong", "b"}:
        return _wrap_mark("**{}**", node, request=request)
    if tag in {"em", "i"}:
        return _wrap_mark("*{}*", node, request=request)
    if tag in {"s", "del", "strike"}:
        return _wrap_mark("~~{}~~", node, request=request)
    if tag == "code":
        return mark_markdown_safe(f"`{_text_content(node)}`")
    if tag in INLINE_UNWRAP:
        return _inline(node.children, request=request, parent=tag)
    if tag in BLOCK_UNWRAP or tag is None:
        return _render_nodes(node.children, request=request, parent=tag or parent)
    return _render_nodes(node.children, request=request, parent=tag)


def _wrap_mark(template, node, request=None):
    inner = _inline(node.children, request=request, parent=node.tag)
    if not inner:
        return mark_markdown_safe("")
    return format_markdown(template, inner)


def _inline(nodes, request=None, parent=None):
    parts = []
    for node in nodes:
        if isinstance(node, str):
            parts.append(_escape_text(node))
            continue
        if node.tag in {"p", "div"}:
            parts.append(_inline(node.children, request=request, parent=parent))
        elif node.tag in {"ul", "ol"} and parent == "li":
            parts.append(
                mark_markdown_safe(
                    "\n" + _render_node(node, request=request, parent=parent)
                )
            )
        else:
            parts.append(_render_node(node, request=request, parent=parent))
    return mark_markdown_safe("".join(parts).strip())


def _render_list(node, ordered, request=None):
    items = [child for child in node.children if not isinstance(child, str)]
    lines = []
    for index, item in enumerate(items, start=1):
        if item.tag != "li":
            continue
        prefix = f"{index}. " if ordered else "- "
        body = _render_node(item, request=request, parent="li")
        indented = body.replace("\n", "\n  ")
        lines.append(f"{prefix}{indented}")
    return mark_markdown_safe("\n".join(lines))


def _render_link(node, request=None):
    text = _inline(node.children, request=request, parent="a")
    if not text:
        text = escape_markdown(_link_fallback_text(node))
    href = _resolve_href(node.attrs, request=request)
    if not href:
        return text
    return format_markdown("[{}]({})", text, mark_markdown_safe(href))


def _link_fallback_text(node):
    return node.attrs.get("title") or node.attrs.get("id") or ""


def _resolve_href(attrs, request=None):
    from agent_ready.markdown.urls import markdown_url_for

    linktype = attrs.get("linktype")
    ident = attrs.get("id")
    if linktype == "page" and ident:
        page = Page.objects.filter(pk=ident).specific().first()
        if page is None:
            return "#"
        return (
            markdown_url_for(page, request=request)
            or page.get_url(request=request)
            or "#"
        )
    if linktype == "document" and ident:
        from wagtail.documents import get_document_model

        document = get_document_model().objects.filter(pk=ident).first()
        return document.url if document else "#"
    return attrs.get("href") or ""


def _render_img(node):
    src = node.attrs.get("src", "")
    if not src:
        return mark_markdown_safe("")
    return format_markdown(
        "![{}]({})",
        node.attrs.get("alt", ""),
        mark_markdown_safe(src),
    )


def _render_embed(node, request=None):
    embedtype = node.attrs.get("embedtype")
    if embedtype == "image":
        return _render_image_embed(node, request=request)
    if embedtype == "media":
        url = node.attrs.get("url") or ""
        if not url:
            return mark_markdown_safe("")
        return format_markdown("[{}]({})", url, mark_markdown_safe(url))
    return mark_markdown_safe("")


def _render_image_embed(node, request=None):
    from wagtail.images import get_image_model
    from wagtail.images.formats import get_image_format

    from agent_ready.markdown.serializers import _image_markdown

    ident = node.attrs.get("id")
    format_name = node.attrs.get("format")
    if not ident or not format_name:
        return mark_markdown_safe("")
    image = get_image_model().objects.filter(pk=ident).first()
    if image is None:
        return mark_markdown_safe("")
    try:
        filter_spec = get_image_format(format_name).filter_spec
    except KeyError:
        return mark_markdown_safe("")
    return _image_markdown(
        image,
        spec=filter_spec,
        alt=node.attrs.get("alt", ""),
    )


def _render_pre(node):
    code = _text_content(node)
    lang = _fenced_language(node)
    info = lang or ""
    return mark_markdown_safe(f"```{info}\n{code}\n```")


def _fenced_language(node):
    for child in node.children:
        if not isinstance(child, str) and child.tag == "code":
            lang = _language_from_class(child.attrs.get("class", ""))
            if lang:
                return lang
    return _language_from_class(node.attrs.get("class", ""))


def _language_from_class(class_attr):
    match = _LANGUAGE_CLASS_RE.search(class_attr or "")
    return match.group(1) if match else ""


def _text_content(node):
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(_text_content(child))
    return "".join(parts)

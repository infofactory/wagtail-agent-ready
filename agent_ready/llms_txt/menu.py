from django.db.models import Q
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _
from django.utils.translation import override
from wagtail.models import Page
from wagtail.utils.text import text_from_html


def body_is_empty(html):
    if html is None:
        return True
    if hasattr(html, "source"):
        html = html.source or ""
    return not text_from_html(html)


def menu_pages(site, locale):
    if site is None or site.root_page_id is None:
        return Page.objects.none()
    root = site.root_page.get_translation_or_none(locale)
    if root is None:
        return Page.objects.none()
    return (
        Page.objects.descendant_of(root, inclusive=True)
        .live()
        .filter(locale=locale)
        .filter(Q(pk=root.pk) | Q(show_in_menus=True))
        .order_by("path")
    )


def menu_dump_html(instance):
    pages = list(menu_pages(instance.site, instance.locale))
    if not pages:
        return ""
    items = format_html_join(
        "",
        '<li><a id="{}" linktype="page">{}</a></li>',
        ((page.pk, page.title) for page in pages),
    )
    with override(instance.locale.language_code):
        heading = _("Pages")
    return format_html("<h2>{}</h2><ul>{}</ul>", heading, items)

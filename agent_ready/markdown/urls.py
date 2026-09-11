import re

from urllib.parse import urlparse

from django.conf import settings
from django.http import Http404
from wagtail.models import Site

from agent_ready.conf import get_setting


_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HAS_EXTENSION_RE = re.compile(r"\.[a-z0-9]{2,4}$", re.IGNORECASE)


def is_agent_ready(page):
    from agent_ready.mixins import AgentReadyMixin

    if page is None:
        return False
    specific = page.specific if hasattr(page, "specific") else page
    return isinstance(specific, AgentReadyMixin) and bool(specific.live)


def markdown_path_for(page, request=None):
    """Return the canonical markdown path (with locale prefix), or None."""
    if page is None:
        return None
    specific = page.specific if hasattr(page, "specific") else page
    url = specific.get_url(request=request)
    if not url:
        return None
    site = specific.get_site()
    if site is not None and specific.translation_key == site.root_page.translation_key:
        prefix = url.rstrip("/")
        return f"{prefix}/index.md" if prefix else "/index.md"
    return f"{url.rstrip('/')}.md"


def markdown_url_for(page, request=None):
    """Return the markdown twin path if the page is opted in and live, else None."""
    if not is_agent_ready(page):
        return None
    return markdown_path_for(page, request=request)


def html_url_for(page, request=None):
    if page is None:
        return None
    specific = page.specific if hasattr(page, "specific") else page
    if request is not None:
        return specific.get_full_url(request)
    return specific.full_url


def split_suffix(url):
    parts = re.split(r"(?=[#?])", url, maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def has_scheme(url):
    return bool(_SCHEME_RE.match(url))


def strip_md_extension(path):
    if path.endswith(".md"):
        return path[:-3]
    return path


def strip_language_prefix(path):
    path = "/" + path.lstrip("/")
    languages = [code for code, _name in get_setting("LANGUAGES", settings.LANGUAGES)]
    for code in languages:
        prefix = f"/{code}/"
        if path.startswith(prefix):
            return path[len(prefix) :]
        if path.rstrip("/") == f"/{code}":
            return ""
    return path.lstrip("/")


def find_page_by_url(url, request=None):
    """Resolve a site-relative or absolute-on-site URL to a live Page, or None."""
    if not url:
        return None

    path, _suffix = split_suffix(url)
    if has_scheme(path):
        path = _path_if_same_site(path, request)
        if path is None:
            return None

    path = strip_md_extension(path)
    path = strip_language_prefix(path)
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if segments and segments[-1] == "index":
        segments = segments[:-1]

    site = None
    if request is not None:
        site = Site.find_for_request(request)
    if site is None:
        site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        return None

    try:
        result = site.root_page.localized.specific.route(request, segments)
    except Http404:
        return None
    if result is None:
        return None
    return result[0].specific


def with_md_extension(url, request=None):
    """Rewrite an internal URL to its markdown twin when the page is opted in."""
    path, suffix = split_suffix(url)
    if not should_consider_for_md(path):
        return url
    page = find_page_by_url(url, request=request)
    markdown_path = markdown_url_for(page, request=request)
    if markdown_path is None:
        return url
    return markdown_path + suffix


def should_consider_for_md(path):
    if not path:
        return False
    if has_scheme(path):
        return False
    if _HAS_EXTENSION_RE.search(path.rstrip("/")):
        return False
    return True


def rewrite_internal_links(markdown, request=None):
    def replace(match):
        text, url = match.group(1), match.group(2)
        return f"[{text}]({with_md_extension(url, request=request)})"

    return _MD_LINK_RE.sub(replace, markdown)


def absolutize_markdown_links(markdown, request=None):
    def replace(match):
        text, url = match.group(1), match.group(2)
        return f"[{text}]({absolutize(url, request=request)})"

    return _MD_LINK_RE.sub(replace, markdown)


def absolutize_markdown_images(markdown, request=None):
    def replace(match):
        alt, url = match.group(1), match.group(2)
        return f"![{alt}]({absolutize(url, request=request)})"

    return _MD_IMAGE_RE.sub(replace, markdown)


def absolutize_markdown_urls(markdown, request=None):
    return absolutize_markdown_images(
        absolutize_markdown_links(markdown, request=request),
        request=request,
    )


def absolutize(url, request=None):
    if not url:
        return url
    if has_scheme(url):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def _path_if_same_site(url, request=None):
    parts = urlparse(url)
    if not parts.hostname:
        return None
    if request is not None:
        host = request.get_host().split(":")[0]
        if parts.hostname != host:
            return None
    else:
        site = Site.objects.filter(is_default_site=True).first()
        if site is None or parts.hostname != site.hostname:
            return None
    return parts.path or "/"

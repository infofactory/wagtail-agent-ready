from django.urls import Resolver404, resolve
from django.utils.cache import patch_vary_headers
from django.utils.translation import get_language_from_path, override


LLMS_TXT_PATH = "/llms.txt"
LLMS_TXT_URL_NAME = "agent_ready_llms_txt"


def llms_txt_path_for(path=None, request=None):
    """Return the covering llms.txt path for a request or URL path."""
    if path is None and request is not None:
        path = request.path
    if not path:
        return LLMS_TXT_PATH
    lang = get_language_from_path(path)
    if lang:
        return f"/{lang}/llms.txt"
    return LLMS_TXT_PATH


def resolve_llms_txt(path):
    """Resolve *path*, activating its locale prefix so i18n_patterns match."""
    lang = get_language_from_path(path)
    try:
        if lang:
            with override(lang):
                return resolve(path)
        return resolve(path)
    except Resolver404:
        return None


def prefers_markdown(request):
    """Return True when Accept prefers text/markdown over text/html."""
    markdown_q = None
    html_q = None
    for media in request.accepted_types:
        if media.main_type == "text" and media.sub_type == "markdown":
            markdown_q = media.quality
        elif media.main_type == "text" and media.sub_type == "html":
            html_q = media.quality
    if not markdown_q:
        return False
    if html_q is None:
        return True
    return markdown_q >= html_q


def add_vary_accept(response):
    patch_vary_headers(response, ("Accept",))
    return response


def add_noindex(response):
    response["X-Robots-Tag"] = "noindex, follow"
    return response


def format_link(url, rel, type_=None):
    if type_:
        return f'<{url}>; rel="{rel}"; type="{type_}"'
    return f'<{url}>; rel="{rel}"'


def append_link_header(response, *links):
    existing = response.get("Link")
    pieces = [existing] if existing else []
    pieces.extend(link for link in links if link)
    if pieces:
        response["Link"] = ", ".join(pieces)
    return response

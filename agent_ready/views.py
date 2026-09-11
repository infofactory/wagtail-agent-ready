from django.http import Http404, HttpResponsePermanentRedirect
from wagtail import views as wagtail_views
from wagtail.models import Page

from agent_ready.markdown.urls import markdown_path_for
from agent_ready.mixins import AgentReadyMixin


def _route(request, path):
    # Page.route_for_request memos the result on the request without keying on
    # path. resolve_markdown_page may call this twice (literal path, then with
    # a trailing "index" segment stripped), so drop the memo or the second call
    # would reuse the first miss. The winning lookup is left in place for
    # wagtail.views.serve to reuse.
    request.__dict__.pop("_wagtail_route_for_request", None)
    result = Page.route_for_request(request, path)
    if result is None:
        return None
    return result[0].specific


def resolve_markdown_page(request, path):
    path = path.strip("/")
    page = _route(request, path)
    if page is not None:
        return page, path
    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[-1] == "index":
        stripped = "/".join(segments[:-1])
        page = _route(request, stripped)
        if page is not None:
            return page, stripped
    return None, path


def serve_markdown(request, path):
    page, path = resolve_markdown_page(request, path)
    if page is None or not isinstance(page, AgentReadyMixin):
        raise Http404

    canonical = markdown_path_for(page, request)
    if not canonical:
        raise Http404
    if canonical != request.path:
        if request.GET:
            canonical = f"{canonical}?{request.GET.urlencode()}"
        return HttpResponsePermanentRedirect(canonical)

    request.agent_ready_markdown = True
    return wagtail_views.serve(request, path)

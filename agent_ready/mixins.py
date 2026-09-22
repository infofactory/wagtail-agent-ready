from django.http import Http404, HttpResponse
from wagtail.models import PAGE_TEMPLATE_VAR

from agent_ready.http import (
    LLMS_TXT_PATH,
    LLMS_TXT_URL_NAME,
    add_noindex,
    add_vary_accept,
    append_link_header,
    format_link,
    llms_txt_path_for,
    prefers_markdown,
    resolve_llms_txt,
)


def _describedby_href(request):
    if request is None:
        return None
    path = llms_txt_path_for(request=request)
    match = resolve_llms_txt(path)
    if match is None and path != LLMS_TXT_PATH:
        path = LLMS_TXT_PATH
        match = resolve_llms_txt(path)
    if match is None:
        return None
    if match.url_name == LLMS_TXT_URL_NAME:
        from agent_ready.llms_txt.models import LlmsTxt

        if LlmsTxt.get_for_request(request) is None:
            return None
    return request.build_absolute_uri(path)


def _describedby_link(request):
    href = _describedby_href(request)
    if href:
        return format_link(href, "describedby")
    return None


class AgentReadyMixin:
    serve_html = True
    markdown_template = None

    def get_markdown_template(self):
        from django.template import TemplateDoesNotExist

        from agent_ready.markdown.renderer import html_to_md_name

        if self.markdown_template:
            return self.markdown_template
        candidate = html_to_md_name(getattr(self, "template", None))
        if not candidate:
            raise TemplateDoesNotExist(getattr(self, "template", None) or "")
        return candidate

    def get_markdown_context(self, request, *args, **kwargs):
        context = self.get_context(request, *args, **kwargs)
        context[PAGE_TEMPLATE_VAR] = self
        context["self"] = self
        context["request"] = request
        return context

    def markdown_frontmatter(self):
        from agent_ready.conf import get_setting

        data = {"title": self.title}
        description = (getattr(self, "search_description", None) or "").strip()
        if description:
            data["search_description"] = description
        published = getattr(self, "last_published_at", None)
        if published is not None:
            data["published"] = published
        if get_setting("WAGTAIL_I18N_ENABLED", False):
            locale = getattr(self, "locale", None)
            if locale is not None:
                data["locale"] = locale.language_code
        return data

    def serve_markdown(self, request, *args, **kwargs):
        from agent_ready.conf import absolute_markdown_urls
        from agent_ready.markdown.normalizer import normalize
        from agent_ready.markdown.renderer import render_page
        from agent_ready.markdown.urls import (
            absolutize_markdown_urls,
            html_url_for,
            rewrite_internal_links,
        )

        body = rewrite_internal_links(render_page(self, request), request=request)
        if absolute_markdown_urls():
            body = absolutize_markdown_urls(body, request=request)
        body = normalize(body)
        response = HttpResponse(body, content_type="text/markdown; charset=UTF-8")
        html_url = html_url_for(self, request)
        links = []
        if html_url:
            links.append(format_link(html_url, "canonical", "text/html"))
        describedby = _describedby_link(request)
        if describedby:
            links.append(describedby)
        if links:
            append_link_header(response, *links)
        add_vary_accept(response)
        if getattr(request, "agent_ready_markdown", False) or not self.serve_html:
            add_noindex(response)
        return response


def on_serve_agent_ready(next_serve_page):
    """Negotiate markdown around ``page.serve()``, independent of mixin MRO."""

    def wrapper(page, request, args, kwargs):
        from agent_ready.markdown.urls import markdown_path_for

        specific = page.specific if hasattr(page, "specific") else page
        if not isinstance(specific, AgentReadyMixin):
            return next_serve_page(page, request, args, kwargs)

        serve_args = args or ()
        serve_kwargs = kwargs or {}
        if getattr(request, "agent_ready_markdown", False) or prefers_markdown(request):
            return specific.serve_markdown(request, *serve_args, **serve_kwargs)
        if not specific.serve_html:
            raise Http404

        response = next_serve_page(page, request, args, kwargs)
        links = []
        markdown_path = markdown_path_for(specific, request)
        if markdown_path:
            links.append(
                format_link(
                    request.build_absolute_uri(markdown_path),
                    "alternate",
                    "text/markdown",
                )
            )
        describedby = _describedby_link(request)
        if describedby:
            links.append(describedby)
        if links:
            append_link_header(response, *links)
        add_vary_accept(response)
        return response

    return wrapper

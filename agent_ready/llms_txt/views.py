from django.http import Http404, HttpResponse

from agent_ready.llms_txt.models import LlmsTxt


def serve_llms_txt(request):
    instance = LlmsTxt.get_for_request(request)
    if instance is None:
        raise Http404
    return HttpResponse(
        instance.to_markdown(request=request),
        content_type="text/markdown; charset=UTF-8",
    )

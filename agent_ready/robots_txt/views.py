from django.http import Http404, HttpResponse

from agent_ready.robots_txt.models import RobotsTxt


def serve_robots_txt(request):
    instance = RobotsTxt.get_for_request(request)
    if instance is None:
        raise Http404
    return HttpResponse(
        instance.to_robots_txt(request=request),
        content_type="text/plain; charset=UTF-8",
    )

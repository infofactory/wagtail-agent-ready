from django.urls import re_path

from agent_ready.views import serve_markdown


urlpatterns = [
    re_path(r"^(?P<path>.*)\.md$", serve_markdown, name="agent_ready_markdown"),
]

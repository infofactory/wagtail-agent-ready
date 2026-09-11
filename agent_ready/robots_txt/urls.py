from django.urls import path

from agent_ready.robots_txt.views import serve_robots_txt


urlpatterns = [
    path("robots.txt", serve_robots_txt, name="agent_ready_robots_txt"),
]

from wagtail.snippets.models import register_snippet

from agent_ready.robots_txt.viewset import RobotsTxtViewSet


register_snippet(RobotsTxtViewSet)

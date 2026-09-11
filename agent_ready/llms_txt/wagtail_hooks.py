from wagtail.snippets.models import register_snippet

from agent_ready.llms_txt.viewset import LlmsTxtViewSet


register_snippet(LlmsTxtViewSet)

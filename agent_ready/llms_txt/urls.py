from django.urls import path

from agent_ready.http import LLMS_TXT_URL_NAME, llms_txt_path_for
from agent_ready.llms_txt.views import serve_llms_txt


__all__ = ["llms_txt_path_for", "urlpatterns"]


urlpatterns = [
    path("llms.txt", serve_llms_txt, name=LLMS_TXT_URL_NAME),
]

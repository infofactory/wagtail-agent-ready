from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from agent_ready.robots_txt.urls import urlpatterns as robots_txt_urls
from agent_ready.urls import urlpatterns as agent_ready_urls


def stub_sitemap(request):
    return HttpResponse(
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>",
        content_type="application/xml",
    )


urlpatterns = [
    *robots_txt_urls,
    path("sitemap.xml", stub_sitemap),
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
]

urlpatterns += i18n_patterns(
    *agent_ready_urls,
    path("", include(wagtail_urls)),
)

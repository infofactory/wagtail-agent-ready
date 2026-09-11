from django.contrib.admin.utils import quote
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy
from wagtail.admin.utils import set_query_params
from wagtail.models import Site
from wagtail.snippets.views.snippets import CreateView as SnippetCreateView
from wagtail.snippets.views.snippets import DeleteView as SnippetDeleteView
from wagtail.snippets.views.snippets import EditView as SnippetEditView
from wagtail.snippets.views.snippets import IndexView as SnippetIndexView
from wagtail.snippets.views.snippets import SnippetViewSet

from agent_ready.robots_txt.models import RobotsTxt


INDEX_TEMPLATE = "agent_ready_robots_txt/index.html"


def _site_from_request(request):
    raw = request.GET.get("site")
    if raw:
        site = Site.objects.filter(pk=raw).first()
        if site is not None:
            return site
    if Site.objects.count() == 1:
        return Site.objects.get()
    return None


def _edit_redirect(view, request, site):
    obj = RobotsTxt.get_for_site(site)
    return redirect(reverse(view.edit_url_name, args=[obj.pk]))


class RobotsTxtIndexView(SnippetIndexView):
    template_name = INDEX_TEMPLATE

    def get(self, request, *args, **kwargs):
        sites = list(Site.objects.order_by("hostname"))
        if len(sites) == 1:
            return _edit_redirect(self, request, site=sites[0])
        add_url = reverse(self.add_url_name)
        site_rows = [
            {
                "site": site,
                "url": set_query_params(add_url, {"site": str(site.pk)}),
            }
            for site in sites
        ]
        return TemplateResponse(
            request,
            INDEX_TEMPLATE,
            {"site_rows": site_rows},
        )


class RobotsTxtCreateView(SnippetCreateView):
    permission_required = "change"

    def get(self, request, *args, **kwargs):
        site = _site_from_request(request)
        if site is None:
            return redirect(reverse(self.index_url_name))
        obj = RobotsTxt.get_for_site(site)
        return redirect(reverse(self.edit_url_name, args=[obj.pk]))

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class RobotsTxtEditView(SnippetEditView):
    add_url_name = None

    def get_delete_url(self):
        return None

    def get_translations(self):
        return []


class RobotsTxtDeleteView(SnippetDeleteView):
    def dispatch(self, request, *args, **kwargs):
        return redirect(reverse(self.edit_url_name, args=[quote(self.object.pk)]))


class RobotsTxtViewSet(SnippetViewSet):
    model = RobotsTxt
    icon = "doc-full"
    menu_label = gettext_lazy("robots.txt")
    add_to_admin_menu = False
    add_to_settings_menu = True
    copy_view_enabled = False
    inspect_view_enabled = False
    base_url_path = "robots-txt"
    form_fields = ["comment", "groups"]
    index_template_name = INDEX_TEMPLATE
    index_view_class = RobotsTxtIndexView
    add_view_class = RobotsTxtCreateView
    edit_view_class = RobotsTxtEditView
    delete_view_class = RobotsTxtDeleteView

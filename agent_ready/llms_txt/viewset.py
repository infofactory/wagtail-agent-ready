import json

from django.apps import apps
from django.contrib.admin.utils import quote
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from wagtail.admin.rich_text.converters.contentstate import ContentstateConverter
from wagtail.admin.utils import set_query_params
from wagtail.admin.widgets.button import Button
from wagtail.models import Locale, Site
from wagtail.snippets.views.snippets import CreateView as SnippetCreateView
from wagtail.snippets.views.snippets import DeleteView as SnippetDeleteView
from wagtail.snippets.views.snippets import EditView as SnippetEditView
from wagtail.snippets.views.snippets import IndexView as SnippetIndexView
from wagtail.snippets.views.snippets import SnippetViewSet

from agent_ready.llms_txt.menu import body_is_empty, menu_dump_html
from agent_ready.llms_txt.models import BODY_FEATURES, LlmsTxt


INDEX_TEMPLATE = "agent_ready_llms_txt/index.html"


def _locale_from_request(request):
    code = request.GET.get("locale")
    if code:
        locale = Locale.objects.filter(language_code=code).first()
        if locale is not None:
            return locale
    return Locale.get_active()


def _site_from_request(request):
    raw = request.GET.get("site")
    if raw:
        site = Site.objects.filter(pk=raw).first()
        if site is not None:
            return site
    if Site.objects.count() == 1:
        return Site.objects.get()
    return None


def _object_for_edit(request, site):
    locale = _locale_from_request(request)
    existing = LlmsTxt.objects.filter(site=site, locale=locale).first()
    if existing is not None:
        return existing
    return LlmsTxt.get_for_locale(site, Locale.get_default())


def _edit_redirect(view, request, site):
    obj = _object_for_edit(request, site)
    return redirect(reverse(view.edit_url_name, args=[obj.pk]))


def _localize_submit_url(instance, locale=None):
    if not apps.is_installed("wagtail_localize"):
        return None
    url = reverse(
        "wagtail_localize:submit_snippet_translation",
        args=[
            instance._meta.app_label,
            instance._meta.model_name,
            quote(instance.pk),
        ],
    )
    if locale is not None:
        url = set_query_params(url, {"select_locale": locale.language_code})
    return url


def _localize_sync_url(instance, next_url=None):
    if not apps.is_installed("wagtail_localize"):
        return None
    from wagtail_localize.models import TranslationSource

    source = TranslationSource.objects.get_for_instance_or_none(instance)
    if source is None or not source.translations.filter(enabled=True).exists():
        return None
    url = reverse("wagtail_localize:update_translations", args=[source.id])
    if next_url:
        url = set_query_params(url, {"next": next_url})
    return url


def _has_untranslated_locale(instance):
    return Locale.objects.exclude(
        id__in=instance.get_translations(inclusive=True).values_list(
            "locale_id", flat=True
        )
    ).exists()


def _can_delete_llms_txt(obj):
    """Locale copies can be removed; the default-locale source cannot."""
    if obj.locale_id == Locale.get_default().pk:
        return False
    return type(obj).objects.filter(site=obj.site).exclude(pk=obj.pk).exists()


def _posted_body_html(raw):
    raw = raw or ""
    if not str(raw).strip() or str(raw).strip() in {"null", "undefined"}:
        return ""
    try:
        json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw
    return ContentstateConverter(BODY_FEATURES).to_database_format(raw)


def _remaining_edit_url(view, deleted):
    remaining = (
        LlmsTxt.objects.filter(site=deleted.site, locale=Locale.get_default())
        .exclude(pk=deleted.pk)
        .first()
        or LlmsTxt.objects.filter(site=deleted.site).exclude(pk=deleted.pk).first()
    )
    if remaining is None:
        return reverse(view.index_url_name)
    return reverse(view.edit_url_name, args=[quote(remaining.pk)])


class LlmsTxtIndexView(SnippetIndexView):
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


class LlmsTxtCreateView(SnippetCreateView):
    permission_required = "change"

    def get(self, request, *args, **kwargs):
        site = _site_from_request(request)
        if site is None:
            return redirect(reverse(self.index_url_name))
        obj = LlmsTxt.get_for_locale(site, _locale_from_request(request))
        return redirect(reverse(self.edit_url_name, args=[obj.pk]))

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class LlmsTxtEditView(SnippetEditView):
    add_url_name = None

    def post(self, request, *args, **kwargs):
        if "dump_menu" in request.POST:
            return self.dump_menu()
        return super().post(request, *args, **kwargs)

    def dump_menu(self):
        if not hasattr(self, "object"):
            self.object = self.get_object()
        data = self.request.POST.copy()
        html = _posted_body_html(data.get("body", ""))
        if body_is_empty(html):
            html = menu_dump_html(self.object)
        data["body"] = ContentstateConverter(BODY_FEATURES).from_database_format(
            html or ""
        )
        kwargs = self.get_form_kwargs()
        kwargs["data"] = data
        self.form = self.get_form_class()(**kwargs)
        return self.render_to_response(self.get_context_data(form=self.form))

    def get_delete_url(self):
        if not _can_delete_llms_txt(self.object):
            return None
        return super().get_delete_url()

    @cached_property
    def header_more_buttons(self):
        buttons = list(super().header_more_buttons)
        if not self.request.user.has_perm("wagtail_localize.submit_translation"):
            return buttons
        edit_url = self.get_edit_url()
        if _has_untranslated_locale(self.object):
            translate_url = _localize_submit_url(self.object)
            if translate_url:
                buttons.append(
                    Button(
                        _("Translate"),
                        url=translate_url,
                        icon_name="wagtail-localize-language",
                        priority=15,
                    )
                )
        sync_url = _localize_sync_url(self.object, next_url=edit_url)
        if sync_url:
            buttons.append(
                Button(
                    _("Sync translated snippets"),
                    url=sync_url,
                    icon_name="resubmit",
                    priority=16,
                )
            )
        return buttons

    def get_translations(self):
        if not self.edit_url_name:
            return []
        existing = {
            translation.locale_id: translation
            for translation in self.object.get_translations(
                inclusive=True
            ).select_related("locale")
        }
        translations = []
        for locale in Locale.objects.all():
            if locale.id == self.object.locale_id:
                continue
            obj = existing.get(locale.id)
            if obj is not None:
                url = reverse(self.edit_url_name, args=[quote(obj.pk)])
            elif localize_url := _localize_submit_url(self.object, locale=locale):
                url = localize_url
            elif self.add_url_name:
                url = set_query_params(
                    reverse(self.add_url_name), {"locale": locale.language_code}
                )
            else:
                continue
            translations.append({"locale": locale, "url": url})
        return translations


class LlmsTxtDeleteView(SnippetDeleteView):
    def dispatch(self, request, *args, **kwargs):
        if not _can_delete_llms_txt(self.object):
            return redirect(reverse(self.edit_url_name, args=[quote(self.object.pk)]))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return _remaining_edit_url(self, self.object)


class LlmsTxtViewSet(SnippetViewSet):
    model = LlmsTxt
    icon = "doc-full"
    menu_label = gettext_lazy("llms.txt")
    add_to_admin_menu = False
    add_to_settings_menu = True
    copy_view_enabled = False
    inspect_view_enabled = False
    base_url_path = "llms-txt"
    form_fields = ["title", "summary", "body"]
    index_template_name = INDEX_TEMPLATE
    index_view_class = LlmsTxtIndexView
    add_view_class = LlmsTxtCreateView
    edit_view_class = LlmsTxtEditView
    delete_view_class = LlmsTxtDeleteView

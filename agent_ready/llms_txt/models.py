from django.db import models
from django.forms import Media
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Locale, Site, TranslatableMixin

from agent_ready.llms_txt.menu import body_is_empty


BODY_FEATURES = ["h2", "bold", "italic", "link", "ul", "ol"]


class MenuDumpBodyPanel(FieldPanel):
    class BoundPanel(FieldPanel.BoundPanel):
        template_name = "agent_ready_llms_txt/panels/body.html"

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            value = ""
            if self.bound_field is not None:
                value = self.bound_field.value()
            context["show_menu_dump"] = body_is_empty(value)
            return context

        @property
        def media(self):
            return super().media + Media(js=["agent_ready_llms_txt/js/menu_dump.js"])


class LlmsTxt(TranslatableMixin, models.Model):
    site = models.ForeignKey(
        "wagtailcore.Site",
        on_delete=models.CASCADE,
        related_name="llms_txt_documents",
        verbose_name=_("Site"),
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Title"),
        help_text=_("Rendered as the H1. Required by the llms.txt spec."),
    )
    summary = models.TextField(
        blank=True,
        verbose_name=_("Summary"),
        help_text=_("Optional blockquote under the H1."),
    )
    body = RichTextField(
        blank=True,
        features=BODY_FEATURES,
        verbose_name=_("Body"),
        help_text=_(
            "The rest of the human-authored file: introduction, "
            "H2 sections, and lists of links."
        ),
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("summary"),
        MenuDumpBodyPanel("body"),
    ]

    class Meta:
        verbose_name = _("llms.txt")
        verbose_name_plural = _("llms.txt")
        unique_together = [("translation_key", "locale")]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "locale"],
                name="unique_llms_txt_per_site_locale",
            ),
        ]

    def __str__(self):
        title = self.title or str(_("llms.txt"))
        if self.site_id:
            return f"{title} ({self.site.hostname})"
        return title

    def to_markdown(self, request=None):
        from agent_ready.llms_txt.markdown import assemble

        return assemble(self, request=request)

    @classmethod
    def get_for_locale(cls, site, locale):
        existing = cls.objects.filter(site=site, locale=locale).first()
        if existing is not None:
            return existing
        source = (
            cls.objects.filter(site=site, locale=Locale.get_default()).first()
            or cls.objects.filter(site=site).first()
        )
        if source is None:
            obj = cls(site=site, locale=locale, title="")
            obj.save()
            return obj
        translation = source.copy_for_translation(locale)
        translation.save()
        return translation

    def is_ready(self):
        return bool(self.title and self.title.strip())

    @classmethod
    def get_for_serve(cls, site, locale):
        """Return the document for site+locale, or that site's default locale.

        Mirrors TranslatableMixin.localized: missing or empty translations fall
        back to the default-locale object for the same site instead of 404.
        Never falls back across sites.
        """
        instance = cls.objects.filter(site=site, locale=locale).first()
        if instance is not None and instance.is_ready():
            return instance
        default_locale = Locale.get_default()
        if locale.pk == default_locale.pk:
            return None
        fallback = cls.objects.filter(site=site, locale=default_locale).first()
        if fallback is not None and fallback.is_ready():
            return fallback
        return None

    @classmethod
    def get_for_request(cls, request):
        """Return the document that GET of the covering llms.txt would serve.

        None when the request is missing, the locale prefix is unknown, no
        Site matches, or get_for_serve would 404.
        """
        if request is None:
            return None
        try:
            locale = locale_for_request(request)
        except (Locale.DoesNotExist, LookupError):
            return None
        site = Site.find_for_request(request)
        if site is None:
            return None
        return cls.get_for_serve(site, locale)


def locale_for_request(request):
    from django.utils.translation import get_language_from_path

    lang = get_language_from_path(request.path)
    if lang:
        return Locale.objects.get_for_language(lang)
    return Locale.get_default()

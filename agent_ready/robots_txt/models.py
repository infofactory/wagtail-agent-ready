from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Site

from agent_ready.robots_txt.blocks import RobotsGroupBlock, default_groups


class RobotsTxt(models.Model):
    site = models.ForeignKey(
        "wagtailcore.Site",
        on_delete=models.CASCADE,
        related_name="robots_txt_documents",
        verbose_name=_("Site"),
    )
    comment = models.TextField(
        blank=True,
        verbose_name=_("Comment"),
        help_text=_("Rendered as # lines at the top of the file."),
    )
    groups = StreamField(
        [("group", RobotsGroupBlock())],
        blank=True,
        use_json_field=True,
        verbose_name=_("Groups"),
    )

    panels = [
        FieldPanel("comment"),
        FieldPanel("groups"),
    ]

    class Meta:
        verbose_name = _("robots.txt")
        verbose_name_plural = _("robots.txt")
        constraints = [
            models.UniqueConstraint(
                fields=["site"],
                name="unique_robots_txt_per_site",
            ),
        ]

    def __str__(self):
        label = str(_("robots.txt"))
        if self.site_id:
            return f"{label} ({self.site.hostname})"
        return label

    def to_robots_txt(self, request=None):
        from agent_ready.robots_txt.assemble import assemble

        return assemble(self, request=request)

    @classmethod
    def get_for_site(cls, site):
        existing = cls.objects.filter(site=site).first()
        if existing is not None:
            return existing
        obj = cls(site=site, groups=default_groups())
        obj.save()
        return obj

    @classmethod
    def get_for_request(cls, request):
        if request is None:
            return None
        site = Site.find_for_request(request)
        if site is None:
            return None
        return cls.objects.filter(site=site).first()

import django.db.models.deletion

from django.db import migrations, models


def assign_default_site(apps, schema_editor):
    Site = apps.get_model("wagtailcore", "Site")
    LlmsTxt = apps.get_model("agent_ready_llms_txt", "LlmsTxt")
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if site is None:
        return
    LlmsTxt.objects.filter(site_id__isnull=True).update(site_id=site.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("agent_ready_llms_txt", "0001_initial"),
        ("wagtailcore", "0094_alter_page_locale"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmstxt",
            name="site",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="llms_txt_documents",
                to="wagtailcore.site",
                verbose_name="Site",
            ),
        ),
        migrations.RunPython(assign_default_site, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="llmstxt",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="llms_txt_documents",
                to="wagtailcore.site",
                verbose_name="Site",
            ),
        ),
        migrations.AddConstraint(
            model_name="llmstxt",
            constraint=models.UniqueConstraint(
                fields=("site", "locale"),
                name="unique_llms_txt_per_site_locale",
            ),
        ),
    ]

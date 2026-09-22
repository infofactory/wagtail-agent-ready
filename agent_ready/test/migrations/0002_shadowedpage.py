import django.db.models.deletion

from django.db import migrations, models

import agent_ready.mixins
import agent_ready.test.models


class Migration(migrations.Migration):
    dependencies = [
        ("agent_ready_test", "0001_initial"),
        ("wagtailcore", "0094_alter_page_locale"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShadowedPage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(
                agent_ready.test.models.BlockingServeMixin,
                agent_ready.mixins.AgentReadyMixin,
                "wagtailcore.page",
            ),
        ),
    ]

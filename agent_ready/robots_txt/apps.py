from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RobotsTxtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent_ready.robots_txt"
    label = "agent_ready_robots_txt"
    verbose_name = _("robots.txt")

from django.apps import AppConfig


class AgentReadyTestAppConfig(AppConfig):
    label = "agent_ready_test"
    name = "agent_ready.test"
    verbose_name = "Agent Ready Test app"
    default_auto_field = "django.db.models.BigAutoField"

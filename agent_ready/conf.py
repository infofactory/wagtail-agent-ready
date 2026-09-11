from django.conf import settings


def get_setting(name, default=None):
    return getattr(settings, name, default)


def absolute_markdown_urls():
    return bool(get_setting("AGENT_READY_ABSOLUTE_MARKDOWN_URLS", False))

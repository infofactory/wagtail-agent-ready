from django import forms
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from wagtail import blocks

from agent_ready.robots_txt.crawlers import SEARCHABLE_AI_CRAWLERS

_ADMIN_URL_NAMES = ("wagtailadmin_home", "admin:index")


class DatalistTextInput(forms.TextInput):
    def __init__(self, suggestions=(), attrs=None):
        super().__init__(attrs)
        self.suggestions = tuple(suggestions)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {} if attrs is None else dict(attrs)
        input_id = attrs.get("id") or name
        datalist_id = f"{input_id}_list"
        attrs["list"] = datalist_id
        html = super().render(name, value, attrs=attrs, renderer=renderer)
        options = format_html_join(
            "",
            '<option value="{}">',
            ((token,) for token in self.suggestions),
        )
        return format_html(
            '{}<datalist id="{}">{}</datalist>',
            html,
            datalist_id,
            options,
        )


class UserAgentCharBlock(blocks.CharBlock):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.field.widget = DatalistTextInput(suggestions=SEARCHABLE_AI_CRAWLERS)


class RobotsGroupBlock(blocks.StructBlock):
    comment = blocks.TextBlock(
        required=False,
        label=_("Comment"),
        help_text=_("Emitted as # lines immediately before this group."),
    )
    user_agents = blocks.ListBlock(
        UserAgentCharBlock(),
        default=[],
        label=_("User-agents"),
        help_text=_("Leave empty to apply this group to all crawlers (*)."),
    )
    search = blocks.BooleanBlock(
        required=False,
        default=True,
        label=_("search"),
    )
    ai_input = blocks.BooleanBlock(
        required=False,
        default=True,
        label=_("ai-input"),
    )
    ai_train = blocks.BooleanBlock(
        required=False,
        default=False,
        label=_("ai-train"),
    )
    allow = blocks.TextBlock(
        required=False,
        default="/",
        label=_("Allow"),
        help_text=_("One path per line."),
    )
    disallow = blocks.TextBlock(
        required=False,
        label=_("Disallow"),
        help_text=_("One path per line."),
    )

    class Meta:
        icon = "list-ul"
        label = _("Group")


def _robots_prefix(path):
    path = path.split("?", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"
    if not path.endswith("/"):
        path = f"{path}/"
    return path


def default_disallow_paths():
    paths = []
    for name in _ADMIN_URL_NAMES:
        try:
            path = reverse(name)
        except NoReverseMatch:
            continue
        prefix = _robots_prefix(path)
        if prefix not in paths:
            paths.append(prefix)
    return paths


def default_groups():
    signals = {
        "comment": "",
        "search": False,
        "ai_input": False,
        "ai_train": False,
        "allow": "/",
        "disallow": "\n".join(default_disallow_paths()),
    }
    return [
        ("group", {**signals, "user_agents": []}),
    ]

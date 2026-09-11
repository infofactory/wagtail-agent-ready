import datetime
import re

from collections.abc import Mapping

from django.utils.encoding import force_str

from agent_ready.markdown.escaping import mark_markdown_safe


_YAML_EXTRA = "wagtail-agent-ready[yaml]"
_SIMPLE_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _complex_value_error(value):
    return TypeError(
        f"Cannot dump {type(value).__name__} as YAML without PyYAML. "
        f"Install with: pip install {_YAML_EXTRA}"
    )


def _quote_string(value):
    escaped = force_str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _simple_key(key):
    if not isinstance(key, str):
        raise _complex_value_error(key)
    if _SIMPLE_KEY_RE.fullmatch(key):
        return key
    return _quote_string(key)


def _simple_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        return _quote_string(value)
    raise _complex_value_error(value)


def _is_mapping(value):
    return isinstance(value, Mapping) and not isinstance(value, str)


def _is_sequence(value):
    return isinstance(value, (list, tuple))


def _dump_sequence_items(value):
    items = []
    for item in value:
        if _is_sequence(item) or _is_mapping(item):
            raise _complex_value_error(item)
        items.append(f"- {_simple_scalar(item)}")
    return items


class SimpleYaml:
    """Stand-in for PyYAML's ``yaml`` module: scalars and lists of scalars."""

    @staticmethod
    def safe_dump(
        data,
        stream=None,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        **kwargs,
    ):
        if not isinstance(data, Mapping):
            raise _complex_value_error(data)
        items = data.items()
        if sort_keys:
            items = sorted(items, key=lambda kv: kv[0])
        if not items:
            text = "{}\n"
        else:
            lines = []
            for key, value in items:
                if _is_mapping(value):
                    raise _complex_value_error(value)
                key = _simple_key(key)
                if _is_sequence(value):
                    if not value:
                        lines.append(f"{key}: []")
                    else:
                        lines.append(f"{key}:")
                        lines.extend(_dump_sequence_items(value))
                else:
                    lines.append(f"{key}: {_simple_scalar(value)}")
            text = "\n".join(lines) + "\n"
        if stream is None:
            return text
        stream.write(text)
        return None


simple_yaml = SimpleYaml()


def yaml_module():
    try:
        import yaml
    except ImportError:
        return simple_yaml
    return yaml


def _without_nones(mapping):
    if mapping is None:
        return {}
    if not isinstance(mapping, Mapping):
        raise TypeError(f"Frontmatter must be a mapping, not {type(mapping).__name__}.")
    return {key: value for key, value in mapping.items() if value is not None}


def format_yaml_frontmatter(mapping):
    """Wrap a mapping in a ``---`` YAML fence. Uses PyYAML when installed."""
    cleaned = _without_nones(mapping)
    if not cleaned:
        return mark_markdown_safe("")
    body = yaml_module().safe_dump(
        dict(cleaned),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    if not body.endswith("\n"):
        body += "\n"
    return mark_markdown_safe(f"---\n{body}---")

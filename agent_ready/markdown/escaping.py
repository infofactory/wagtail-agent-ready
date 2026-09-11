import re

from django.utils.encoding import force_str


_ESCAPE_TABLE = str.maketrans(
    {
        "\\": "\\\\",
        "*": r"\*",
        "_": r"\_",
        "[": r"\[",
        "]": r"\]",
        "(": r"\(",
        ")": r"\)",
    }
)
_UNESCAPE_RE = re.compile(r"\\([\\*_\[\]()])")


class SafeMarkdown(str):
    """A str subclass that has already been escaped for markdown output."""

    __slots__ = ()

    def __add__(self, rhs):
        if isinstance(rhs, str):
            joined = super().__add__(rhs)
            if isinstance(rhs, SafeMarkdown):
                return SafeMarkdown(joined)
            return joined
        return NotImplemented

    def __str__(self):
        return self


def mark_markdown_safe(value):
    """Mark a string as already-safe markdown. ``None`` becomes ``""``."""
    if isinstance(value, SafeMarkdown):
        return value
    if value is None:
        return SafeMarkdown("")
    return SafeMarkdown(force_str(value))


def escape_markdown(value):
    """Narrow-escape ``\\ * _ [ ] ( )``. No-op on ``SafeMarkdown``."""
    if isinstance(value, SafeMarkdown):
        return value
    if value is None:
        return SafeMarkdown("")
    return SafeMarkdown(force_str(value).translate(_ESCAPE_TABLE))


def unescape_markdown(value):
    """Inverse of ``escape_markdown`` for user strings. Returns a plain str."""
    if value is None:
        return ""
    return _UNESCAPE_RE.sub(r"\1", force_str(value))


def format_markdown(format_string, *args, **kwargs):
    """Like ``format_html``: conditional-escape args, then mark the result safe."""
    if not (args or kwargs):
        raise TypeError("args or kwargs must be provided.")
    args_safe = map(escape_markdown, args)
    kwargs_safe = {key: escape_markdown(val) for key, val in kwargs.items()}
    return mark_markdown_safe(format_string.format(*args_safe, **kwargs_safe))

import re

from django.urls import Resolver404, resolve


SITEMAP_PATH = "/sitemap.xml"
_PATH_DIRECTIVE_RE = re.compile(r"^(?:allow|disallow)\s*:\s*", re.IGNORECASE)


def as_comment_lines(text):
    if not text or not str(text).strip():
        return []
    lines = []
    for line in str(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(stripped)
        elif not stripped:
            lines.append("#")
        else:
            lines.append(f"# {line.rstrip()}")
    return lines


def paths_from_text(text):
    if not text:
        return []
    paths = []
    for line in str(text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = _PATH_DIRECTIVE_RE.sub("", stripped, count=1).strip()
        if stripped:
            paths.append(stripped)
    return paths


def yes_no(value):
    return "yes" if value else "no"


def user_agent_tokens(value):
    tokens = []
    for item in value or []:
        token = str(item).strip() if item is not None else ""
        if token:
            tokens.append(token)
    return tokens or ["*"]


def sitemap_href(request=None):
    try:
        resolve(SITEMAP_PATH)
    except Resolver404:
        return None
    if request is not None:
        return request.build_absolute_uri(SITEMAP_PATH)
    return SITEMAP_PATH


def assemble_group(value):
    lines = as_comment_lines(value.get("comment"))
    for token in user_agent_tokens(value.get("user_agents")):
        lines.append(f"User-agent: {token}")
    for path in paths_from_text(value.get("allow")):
        lines.append(f"Allow: {path}")
    for path in paths_from_text(value.get("disallow")):
        lines.append(f"Disallow: {path}")
    lines.append(
        "Content-Signal: "
        f"search={yes_no(value.get('search'))}, "
        f"ai-input={yes_no(value.get('ai_input'))}, "
        f"ai-train={yes_no(value.get('ai_train'))}"
    )
    return "\n".join(lines)


def assemble(instance, request=None):
    parts = []
    header = as_comment_lines(instance.comment)
    if header:
        parts.append("\n".join(header))
    for block in instance.groups:
        parts.append(assemble_group(block.value))
    href = sitemap_href(request=request)
    if href:
        parts.append(f"Sitemap: {href}")
    body = "\n\n".join(parts)
    if body:
        return body + "\n"
    return ""

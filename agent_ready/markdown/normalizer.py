import re


_LIST_ITEM_RE = re.compile(r"^([-*+] |\d+\. )")
_METADATA_RE = re.compile(r"^\*\*[^*]+?\*\*")


def normalize(markdown):
    """Collapse template whitespace into readable Markdown."""
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.split("\n")
    out = []

    for index, line in enumerate(lines):
        if line.strip() != "":
            out.append(line)
            continue

        previous = _previous_non_empty(out)
        nxt = _next_non_empty(lines, index + 1)

        if (_is_list_item(previous) and _is_list_item(nxt)) or (
            _is_metadata_line(previous) and _is_metadata_line(nxt)
        ):
            continue

        if out and out[-1] == "":
            continue

        if previous is None or nxt is None:
            continue

        out.append("")

    return "\n".join(out) + "\n"


def _previous_non_empty(lines):
    for line in reversed(lines):
        if line.strip():
            return line
    return None


def _next_non_empty(lines, start):
    for line in lines[start:]:
        if line.strip():
            return line
    return None


def _is_list_item(line):
    return isinstance(line, str) and bool(_LIST_ITEM_RE.match(line))


def _is_metadata_line(line):
    return isinstance(line, str) and bool(_METADATA_RE.match(line))

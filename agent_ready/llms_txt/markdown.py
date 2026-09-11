from agent_ready.markdown.normalizer import normalize
from agent_ready.markdown.richtext import richtext_to_markdown
from agent_ready.markdown.urls import absolutize_markdown_urls, rewrite_internal_links


def assemble(instance, request=None):
    parts = [f"# {instance.title.strip()}"]
    summary = (instance.summary or "").strip()
    if summary:
        quoted = "\n".join(f"> {line}" if line else ">" for line in summary.split("\n"))
        parts.append(quoted)
    body = richtext_to_markdown(instance.body, request=request)
    if body:
        parts.append(body)
    return normalize(
        absolutize_markdown_urls(
            rewrite_internal_links("\n\n".join(parts), request=request),
            request=request,
        )
    )

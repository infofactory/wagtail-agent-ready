# Wagtail Agent Ready

First-class markdown twins, authored `/llms.txt` and `/robots.txt` builder.

Opted-in Wagtail pages get a markdown representation you can template the same way as HTML. Pages without the mixin stay HTML-only.

This app offers an optional `/llms.txt` and `/robots.txt` editors in the admin. These apps have migrations, if you prefer you can handle them on your own.

## What does it mean to be Agent Ready?

An agent-ready site is one AI agents can discover, parse, and interact with without a human browser. [isitagentready.com](https://isitagentready.com) scores that by probing emerging standards. Cloudflare's scanner groups them into five categories.

The scanner offers **Content Site**, **API / Application**, and **All Checks** presets.

**Discoverability**:
- `robots.txt` (RFC 9309) that points at a sitemap;
- `sitemap.xml`: https://www.sitemaps.org/protocol.html
- `Link` headers to machine-readable resources (RFC 8288) (`api-catalog`, `service-desc`, `service-doc`, `describedby`);
- DNS for AI Discovery (DNS-AID)

**Content accessibility**: 
- `Accept: text/markdown` returns `Content-Type: text/markdown`; HTML stays the default.

**Bot access control**:
- explicit AI crawler `User-agent` rules in `robots.txt`;
- Content Signals (`search`, `ai-input`, `ai-train`);
- Web Bot Auth, if the origin signs outbound bot requests.

**Protocol discovery** — API Catalog, OAuth/OIDC, OAuth Protected Resource, Auth.md, MCP Server Card, A2A Agent Card, Agent Skills, WebMCP, ARD.

**Commerce** — x402, MPP, UCP, ACP.

This package covers the content-site checks that belong in Wagtail:
- markdown twins (`.md` URLs and `Accept` negotiation)
- `Link` headers (`rel="alternate"` for twins, `describedby` whenever `llms.txt` is mounted) plus `{% agent_ready_head %}`
- optional CMS editors for `/llms.txt` and `/robots.txt` (AI bot groups and Content Signals).

It does not ship a sitemap; Wagtail already has [`wagtail.contrib.sitemaps`](https://docs.wagtail.org/en/stable/reference/contrib/sitemaps.html) (see [Sitemap](#sitemap)) — nor `/llms-full.txt`, Web Bot Auth keys, protocol discovery, or commerce.  
[DNS-AID](#dns-aid) records are DNS work. Scan a Wagtail site with the **Content Site** preset.

After those pieces are live, scan the origin on [isitagentready.com](https://isitagentready.com).

## Features

- Opt-in per page type via `AgentReadyMixin`
- `GET /{page-path}.md` and `Accept: text/markdown` on the HTML URL
- Canonical `/index.md` for the site root; `/path/index.md` 301s to `/path.md`
- HTTP Header `Link: rel="alternate"` plus `{% agent_ready_head %}` helper tag
- Pages use a twin `.md` template
- Block rendering cascade: `to_markdown()` → twin `.md` template → StreamField walker
- Link rewriting filter that points at twins only when the target is opted in (`|to_markdown_url`)
- `{% markdown_image %}` twin of Wagtail `{% image %}`
- Optional `agent_ready.llms_txt`: CMS editor and `GET /llms.txt`, including locale-prefixed copies
- Optional `agent_ready.robots_txt`: CMS editor and origin-root `GET /robots.txt`


## Requirements

- Python ≥ 3.10
- Django ≥ 5.2, < 6.2
- Wagtail ≥ 6.4


## Guide to make your site Agent Ready

### Markdown twins and headers (Base installation)

```bash
pip install wagtail-agent-ready
```

1. Add `"agent_ready"` to `INSTALLED_APPS`.
2. Include the package URLs **before** `wagtail_urls`.

```python
from agent_ready.urls import urlpatterns as agent_ready_urls

urlpatterns += [
    # ...
    *agent_ready_urls, # <-- Add this just before wagtail_urls
    path("", include(wagtail_urls)),
    # ...
]
```

3. Mix the mixin into page models that should have a twin:

```python
from agent_ready.mixins import AgentReadyMixin


class HomePage(AgentReadyMixin, Page):
    pass
```

`Accept` negotiation, `Link` headers, and `.md` URLs run from Wagtail’s `on_serve_page` hook, not from `AgentReadyMixin.serve()`. Another mixin can define `serve()` and come first in the MRO. Put `RoutablePageMixin` (or any other serving mixin) before `AgentReadyMixin`:

```python
from wagtail.contrib.routable_page.models import RoutablePageMixin


class EventPage(RoutablePageMixin, AgentReadyMixin, Page):
    pass
```

4. In the HTML layout template load the agent ready templatetags with`{% load agent_ready %}`
5. Add the `{% agent_ready_head %}` tag in the HTML layout template's `&lt;head&gt;`.
6. Add a Markdown twin template next to each opted-in page’s HTML template:

```
myapp/templates/myapp/home_page.html  ->  myapp/templates/myapp/home_page.md
```

Block twins are optional. Without a `.md` next to the block’s HTML template, it will render like it would without an HTML template:

```
myapp/templates/stream_blocks/text_image.html  ->  myapp/templates/stream_blocks/text_image.md
```


### Sitemap

Enable [Wagtail's sitemap contribution](https://docs.wagtail.org/en/stable/reference/contrib/sitemaps.html) (`wagtail.contrib.sitemaps`) or equivalent on the **origin root** so `GET /sitemap.xml` returns live HTML page locs:

```python
from wagtail.contrib.sitemaps.views import sitemap

urlpatterns = [
    path("sitemap.xml", sitemap),
    # ...
]
```


### robots.txt

There must be a valid `robots.txt` served on the **origin root** so `GET /robots.txt` returns the parsable instructions for crawlers.  
Inside the `robots.txt` there should be a reference to the sitemap full path, and there should be [AI Content Signals](https://contentsignals.org/) as well.

You can serve it as a static view or a txt django template.

```python
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
    ),
]
```

If you would like to use an UI builder, you can enable our `robots.txt` builder. To install it you need to:

1. Add `"agent_ready.robots_txt"` to `INSTALLED_APPS` (in addition to `"agent_ready"`).
2. Mount the URLs on the **origin root** so `GET /robots.txt` is not locale-negotiated.

```python
from agent_ready.robots_txt.urls import urlpatterns as robots_txt_urls

urlpatterns = [
    *robots_txt_urls,
    # ...
]
```

`GET /robots.txt` is chosen by host (`Site.find_for_request`). Edit the file under **Settings → robots.txt**. When more than one Wagtail `Site` exists, Settings lists the sites; a single-site install still opens the editor directly.

Each site has one document, checkout the editor to see what you can add.
Installing the app is not enough, `GET /robots.txt` 404s until a document exists.

When `GET /sitemap.xml` is a mounted URL, the `robots.txt` automatically advertises it. A sitemap that exists only as `/{lang}/sitemap.xml` is not advertised.


## llms.txt

While it's not directly required by the Cloudflare agent-ready tests, it is useful to fulfill the `describedby` link requirement of the tests.

Opted-in HTML and markdown responses send `rel="describedby"` pointing at `llms.txt` when that URL is mounted. The covering path is `/{lang}/llms.txt` when the request is language-prefixed and that route exists; otherwise `/llms.txt`. A custom `llms.txt` view is advertised as soon as it resolves.

You can create and serve them using templates and views, by mounting them on the origin root, and on the i18n_patterns if your site is multilingual.


```python
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "llms.txt",
        TemplateView.as_view(
            template_name="llms.txt",
            content_type="text/plain",
        ),
    ),
]
```

We created an admin editor to author these files like they would be pages in the admin. To install it you must:

1. Add `"agent_ready.llms_txt"` to `INSTALLED_APPS` (in addition to `"agent_ready"`).
2. Mount the URLs on the **origin root** so `GET /llms.txt` is not locale-negotiated:

```python
from agent_ready.llms_txt.urls import urlpatterns as llms_txt_urls

urlpatterns = [
    *llms_txt_urls,
    # ...
]
```

3. If the host uses `i18n_patterns`, include the same module **inside** those patterns as well, **before** the `.md` catch-all / `wagtail_urls`:

```python
urlpatterns += i18n_patterns(
    *llms_txt_urls,
    # ...
)
```

A monolingual site only needs the root include.

`GET /llms.txt` is chosen by host (`Site.find_for_request`). Edit the file under **Settings → llms.txt**. When more than one Wagtail `Site` exists, Settings lists the sites; a single-site install still opens the editor directly. One document per site and locale. When the body is empty, **Insert menu pages** fills the editor from that site’s menu (root plus live pages shown in menus) for the document’s locale; Save is still required. Internal page links in the body become markdown twins when the page is opted in, and are emitted as absolute URLs.
`describedby` is sent only when that host and locale would 200 — a title is present, and prefixed paths fall back to that site's default-locale document. Installing the app is not enough.

### DNS-AID

Wagtail does not manage DNS records. Publish them at the DNS host following the [DNS for AI Discovery (DNS-AID) specification](https://specification.website/spec/agent-readiness/dns-aid/).

## Usage

Visit any opted-in live page with a `.md` suffix, or send `Accept: text/markdown` on the HTML URL.

Appending `/index.md` to a page URL redirects to the canonical twin. The homepage is `/index.md` (and `/en/index.md` when a locale prefix is in use).

In Markdown templates:

```
{% load agent_ready %}
{% markdown_frontmatter %}

# {{ page.title|collapse_whitespace|escape_markdown }}

{{ page.body|to_markdown }}
{% markdown_block page.body %}
[{{ other.title|collapse_whitespace|escape_markdown }}]({{ other|to_markdown_url }})
{% markdown_image photo fill-600x338 %}
{% markdown_image photo fill-600x338 alt=caption %}
```

`{% markdown_frontmatter %}` is opt-in. The default dict is `title`, `search_description` when filled, `published` (`last_published_at`, not first published), and `locale` when `WAGTAIL_I18N_ENABLED`. `{% markdown_frontmatter custom %}` dumps that mapping only (no merge). Override `markdown_frontmatter()` on a page type to add keys. Scalars and lists of scalars work without extras; nested mappings need `pip install wagtail-agent-ready[yaml]`.

If a page has no twin, `|to_markdown_url` keeps the HTML URL.

`{% markdown_image %}` is the markdown twin of Wagtail `{% image %}`: a filter spec is required, `alt=` uses the same attribute slot, and HTML-only attrs (`class`, `loading`, `as`, …) are rejected. The walker still uses its own specs (ImageBlock `fill-600x338`, ImageChooser `original`, rich-text format filter_specs), not this tag.

Page twins emit site-relative links and image srcs. Set `AGENT_READY_ABSOLUTE_MARKDOWN_URLS = True` to absolutize both. `/llms.txt` always uses absolute URLs.

Set `serve_html = False` on a page type to 404 the HTML URL and still serve Markdown. Those responses are also `noindex`. `.md` URLs of pages that still serve HTML get the same header; `Accept: text/markdown` on the HTML URL does not, so a crawler cannot noindex the canonical page.

Custom choosers that should not implement `to_markdown()` can register a walker serializer from `wagtail_hooks.py`. Registration only affects the walker (`to_markdown()` and a twin `.md` template still win):

```python
# myapp/wagtail_hooks.py
from agent_ready.markdown import register_markdown_serializer
from myapp.blocks import PersonChooserBlock


@register_markdown_serializer(PersonChooserBlock)
def serialize_person(block, value, context):
    if not value:
        return ""
    return value.name
```



## Package layout

```
agent_ready/
  wagtail_hooks.py           on_serve_page: Accept, Link, .md
  mixins.py                  AgentReadyMixin
  views.py                   serve_markdown
  urls.py                    .md urlpattern
  http.py                    Accept negotiation, Link / Vary helpers
  markdown/
    renderer.py              cascade: method > twin > walker
    serializers.py           render_basic → Markdown
    richtext.py              Draftail HTML → Markdown
    frontmatter.py           YAML fence (PyYAML optional)
    normalizer.py            whitespace
    urls.py                  gated twin URLs
  templatetags/agent_ready.py
  llms_txt/                  optional app: CMS editor + /llms.txt
  robots_txt/                optional app: CMS editor + /robots.txt
```


## Development

### Setup

```bash
# Clone the repo
git clone https://github.com/infofactory/wagtail-agent-ready.git
cd wagtail-agent-ready

# Install with uv
uv sync --extra testing --group test
```

### Running tests

```bash
# Run tests
python testmanage.py test

# Run with coverage
python -m coverage run testmanage.py test
python -m coverage report -m
```

### Running linting

```bash
ruff check .
ruff format --check .
```

### Running tox (matrix testing)

```bash
tox
```

## License

BSD-3-Clause. See [LICENSE](LICENSE) for details.
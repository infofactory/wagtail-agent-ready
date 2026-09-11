import re

from django.urls import reverse
from wagtail.models import Locale, Page, Site
from wagtail.rich_text import RichText

from agent_ready.llms_txt.menu import body_is_empty, menu_dump_html, menu_pages
from agent_ready.llms_txt.models import LlmsTxt
from agent_ready.test.models import AgentReadyHomePage, AgentReadyPage
from agent_ready.tests.base import AgentReadySiteTestCase


OTHER_HOST = "other.example"


def italian_locale():
    locale, _created = Locale.objects.get_or_create(language_code="it")
    return locale


def snippet_url(view_name, *args):
    return reverse(LlmsTxt.snippet_viewset.get_url_name(view_name), args=args)


DUMP_BUTTON_RE = re.compile(r"<button\b[^>]*\bname=\"dump_menu\"[^>]*>", re.I)


def draftail_value(content):
    """Unescape the Draftail hidden-input JSON from an edit-form HTML response."""
    return (
        content.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def dump_button_tag(content):
    match = DUMP_BUTTON_RE.search(content)
    return match.group(0) if match else ""


class LlmsTxtMenuDumpTests(AgentReadySiteTestCase):
    def create_document(
        self, locale=None, title="Site for agents", summary="", body="", site=None
    ):
        return LlmsTxt.objects.create(
            title=title,
            summary=summary,
            body=body,
            locale=locale or Locale.get_default(),
            site=site or self.site,
        )

    def add_site(self, hostname, site_name="Other"):
        root = Page.get_first_root_node()
        home = AgentReadyHomePage(
            title=f"{site_name} home",
            slug=hostname.replace(".", "-"),
        )
        root.add_child(instance=home)
        home.save_revision().publish()
        return Site.objects.create(
            hostname=hostname,
            port=80,
            root_page=home,
            is_default_site=False,
            site_name=site_name,
        )

    def set_in_menus(self, page, in_menus=True):
        page.show_in_menus = in_menus
        page.save()
        page.refresh_from_db()
        return page

    def test_body_is_empty_treats_blank_paragraphs_as_empty(self):
        self.assertTrue(body_is_empty(""))
        self.assertTrue(body_is_empty(None))
        self.assertTrue(body_is_empty("<p></p>"))
        self.assertTrue(body_is_empty("<p><br></p>"))
        self.assertTrue(body_is_empty(RichText("<p></p>")))
        self.assertFalse(body_is_empty("<p>Hello</p>"))

    def test_dump_includes_root_and_live_in_menu_descendants_in_path_order(self):
        nested = AgentReadyPage(title="Team", slug="team", show_in_menus=True)
        self.page.add_child(instance=nested)
        nested.save_revision().publish()
        self.set_in_menus(self.page)
        self.set_in_menus(self.plain)

        doc = self.create_document()
        pages = list(menu_pages(doc.site, doc.locale))
        self.assertEqual(
            [page.pk for page in pages],
            [self.home.pk, self.page.pk, nested.pk, self.plain.pk],
        )
        html = menu_dump_html(doc)
        self.assertIn("<h2>Pages</h2>", html)
        self.assertIn(f'<a id="{self.home.pk}" linktype="page">Home</a>', html)
        self.assertIn(f'<a id="{self.page.pk}" linktype="page">About</a>', html)
        self.assertIn(f'<a id="{nested.pk}" linktype="page">Team</a>', html)
        self.assertIn(f'<a id="{self.plain.pk}" linktype="page">Plain</a>', html)
        self.assertNotIn(f'id="{self.markdown_only.pk}"', html)
        self.assertNotIn(f'id="{self.no_agent.pk}"', html)
        self.assertNotIn(f'id="{self.agent_page.pk}"', html)
        self.assertLess(html.index("Home"), html.index("About"))
        self.assertLess(html.index("About"), html.index("Team"))
        self.assertLess(html.index("Team"), html.index("Plain"))

    def test_dump_omits_unpublished_not_in_menu_other_site_and_other_locale(self):
        self.set_in_menus(self.page)
        self.page.unpublish()
        other = self.add_site(OTHER_HOST)
        other_about = AgentReadyPage(title="Other about", slug="other-about")
        other.root_page.add_child(instance=other_about)
        other_about.save_revision().publish()
        self.set_in_menus(other_about)

        italian = italian_locale()
        home_it = self.home.copy_for_translation(italian)
        home_it.title = "Casa"
        home_it.save_revision().publish()
        about_it = self.page.copy_for_translation(italian)
        about_it.title = "Chi siamo"
        about_it.show_in_menus = True
        about_it.save_revision().publish()

        doc = self.create_document()
        html = menu_dump_html(doc)
        self.assertIn(f'id="{self.home.pk}"', html)
        self.assertNotIn(f'id="{self.page.pk}"', html)
        self.assertNotIn(f'id="{other.root_page.pk}"', html)
        self.assertNotIn(f'id="{other_about.pk}"', html)
        self.assertNotIn(f'id="{home_it.pk}"', html)
        self.assertNotIn(f'id="{about_it.pk}"', html)

        italian_doc = self.create_document(locale=italian, title="Documento")
        italian_html = menu_dump_html(italian_doc)
        self.assertIn(f'<a id="{home_it.pk}" linktype="page">Casa</a>', italian_html)
        self.assertIn(
            f'<a id="{about_it.pk}" linktype="page">Chi siamo</a>', italian_html
        )
        self.assertNotIn(f'id="{self.home.pk}"', italian_html)

    def test_dump_is_empty_when_the_root_has_no_translation(self):
        italian = italian_locale()
        doc = self.create_document(locale=italian, title="Documento")
        self.assertEqual(list(menu_pages(doc.site, italian)), [])
        self.assertEqual(menu_dump_html(doc), "")

    def test_dump_escapes_page_titles(self):
        self.home.title = 'Home & "HQ" <main>'
        self.home.save()
        doc = self.create_document()
        html = menu_dump_html(doc)
        self.assertIn("Home &amp; &quot;HQ&quot; &lt;main&gt;", html)
        self.assertNotIn("<main>", html)

    def test_edit_shows_the_button_when_the_saved_body_is_empty(self):
        self.login()
        doc = self.create_document(body="")
        for body in ("", "<p></p>", "<p><br/></p>"):
            with self.subTest(body=body):
                doc.body = RichText(body)
                doc.save()
                response = self.client.get(snippet_url("edit", doc.pk))
                self.assertEqual(response.status_code, 200)
                button = dump_button_tag(response.content.decode())
                self.assertTrue(button)
                self.assertNotIn("hidden", button)
                self.assertContains(response, "Insert menu pages")
                self.assertContains(response, "menu_dump.js")

        doc.body = RichText("<p>Already curated.</p>")
        doc.save()
        filled_edit = self.client.get(snippet_url("edit", doc.pk))
        self.assertEqual(filled_edit.status_code, 200)
        filled_button = dump_button_tag(filled_edit.content.decode())
        self.assertTrue(filled_button)
        self.assertIn("hidden", filled_button)

    def test_dump_menu_post_fills_empty_body_without_saving(self):
        self.login()
        self.set_in_menus(self.page)
        doc = self.create_document(title="", summary="")
        response = self.client.post(
            snippet_url("edit", doc.pk),
            {
                "title": "Unsaved title",
                "summary": "Unsaved summary",
                "body": "",
                "dump_menu": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        value = draftail_value(response.content.decode())
        self.assertIn('"text": "Home"', value)
        self.assertIn('"text": "About"', value)
        self.assertIn(f'"id": {self.home.pk}', value)
        self.assertIn(f'"id": {self.page.pk}', value)
        self.assertContains(response, "Unsaved title")
        self.assertContains(response, "Unsaved summary")
        dumped_button = dump_button_tag(response.content.decode())
        self.assertTrue(dumped_button)
        self.assertIn("hidden", dumped_button)

        doc.refresh_from_db()
        self.assertEqual(doc.title, "")
        self.assertEqual(doc.summary, "")
        self.assertFalse(doc.body)

    def test_dump_menu_post_does_not_overwrite_a_non_empty_body(self):
        self.login()
        self.set_in_menus(self.page)
        doc = self.create_document(body="")
        existing = "<p>Keep this.</p>"
        response = self.client.post(
            snippet_url("edit", doc.pk),
            {
                "title": "Kept title",
                "summary": "",
                "body": existing,
                "dump_menu": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        value = draftail_value(response.content.decode())
        self.assertIn('"text": "Keep this."', value)
        self.assertNotIn(f'"id": {self.page.pk}', value)
        doc.refresh_from_db()
        self.assertFalse(doc.body)

    def test_dumped_html_assembles_to_markdown_list_items(self):
        self.set_in_menus(self.page)
        self.set_in_menus(self.plain)
        doc = self.create_document()
        doc.body = menu_dump_html(doc)
        doc.save()
        content = self.client.get("/llms.txt").content.decode()
        self.assertIn("## Pages", content)
        self.assertIn("[Home](http://testserver/en/index.md)", content)
        self.assertIn("[About](http://testserver/en/about.md)", content)
        self.assertIn("[Plain](http://", content)
        self.assertIn("/en/plain/", content)
        self.assertNotIn("/en/plain.md", content)

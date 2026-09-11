from django.test import override_settings
from django.urls import reverse
from wagtail.models import Locale, Page, Site
from wagtail.rich_text import RichText
from wagtail.snippets.models import get_snippet_models

from agent_ready.llms_txt.models import LlmsTxt
from agent_ready.test.models import AgentReadyHomePage
from agent_ready.tests.base import (
    MARKDOWN_CONTENT_TYPE,
    AgentReadySiteTestCase,
    snippet_models_for_index_view,
)


OTHER_HOST = "other.example"
MULTI_HOSTS = ["localhost", "testserver", OTHER_HOST]


def italian_locale():
    locale, _created = Locale.objects.get_or_create(language_code="it")
    return locale


def snippet_url(view_name, *args):
    return reverse(LlmsTxt.snippet_viewset.get_url_name(view_name), args=args)


class LlmsTxtTests(AgentReadySiteTestCase):
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

    def test_unprefixed_llms_txt_returns_200_for_the_default_locale_when_titled(self):
        self.create_document(summary="A short summary.")
        response = self.client.get("/llms.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], MARKDOWN_CONTENT_TYPE)
        self.assertIn(b"# Site for agents", response.content)
        self.assertIn(b"> A short summary.", response.content)

    def test_unprefixed_llms_txt_does_not_follow_accept_language(self):
        self.create_document(title="English doc")
        italian = italian_locale()
        self.create_document(locale=italian, title="Documento italiano")
        response = self.client.get("/llms.txt", HTTP_ACCEPT_LANGUAGE="it")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# English doc", response.content)
        self.assertNotIn(b"# Documento italiano", response.content)

    def test_lang_prefixed_llms_txt_returns_that_locales_document_when_it_has_a_title(
        self,
    ):
        self.create_document(title="English doc")
        self.create_document(locale=italian_locale(), title="Documento italiano")
        response = self.client.get("/it/llms.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# Documento italiano", response.content)

    def test_lang_prefixed_llms_txt_falls_back_to_the_default_locale(self):
        self.create_document(title="English doc")
        italian = italian_locale()
        self.create_document(locale=italian, title="   ")
        response = self.client.get("/it/llms.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# English doc", response.content)

        LlmsTxt.objects.filter(locale=italian).delete()
        response = self.client.get("/it/llms.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# English doc", response.content)

    def test_unprefixed_llms_txt_returns_404_when_default_locale_document_is_missing_or_empty(
        self,
    ):
        response = self.client.get("/llms.txt", follow=True)
        self.assertEqual(response.status_code, 404)

        self.create_document(title="")
        response = self.client.get("/llms.txt", follow=True)
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/en/llms.txt")
        self.assertEqual(response.status_code, 404)

    def test_unknown_locale_prefix_returns_404(self):
        self.create_document()
        response = self.client.get("/xx/llms.txt")
        self.assertEqual(response.status_code, 404)

    def test_assembled_markdown_is_title_optional_summary_then_body(self):
        self.create_document(
            title="Site for agents",
            summary="A short summary.",
            body=RichText("<p>Body <b>text</b>.</p>"),
        )
        response = self.client.get("/llms.txt")
        self.assertEqual(
            response.content.decode(),
            "# Site for agents\n\n> A short summary.\n\nBody **text**.\n",
        )

    def test_internal_page_links_in_the_body_rewrite_to_markdown_twins_when_opted_in(
        self,
    ):
        self.create_document(
            body=RichText(
                f'<p><a id="{self.page.pk}" linktype="page">About</a> '
                f'<a id="{self.plain.pk}" linktype="page">Plain</a></p>'
            )
        )
        response = self.client.get("/llms.txt")
        content = response.content.decode()
        self.assertIn("/en/about.md", content)
        self.assertIn(self.plain.url, content)
        self.assertNotIn(self.plain.url.rstrip("/") + ".md", content)

    def test_those_links_and_other_relative_hrefs_are_emitted_as_absolute_urls(self):
        self.create_document(
            body=RichText(
                f'<p><a id="{self.page.pk}" linktype="page">About</a> '
                f'<a href="/relative">Rel</a></p>'
            )
        )
        response = self.client.get("/llms.txt")
        content = response.content.decode()
        self.assertIn("http://", content)
        self.assertIn("/en/about.md", content)
        self.assertIn("/relative", content)
        self.assertNotIn("](/en/about.md)", content)

    def test_markdown_twins_keep_path_relative_links(self):
        self.page.body = [
            {
                "type": "paragraph",
                "value": f'<p><a id="{self.home.pk}" linktype="page">Home</a></p>',
            }
        ]
        self.page.save_revision().publish()
        response = self.client.get("/en/about.md")
        content = response.content.decode()
        self.assertIn("](/en/index.md)", content)
        self.assertNotIn("http://", content.split("](")[-1] if "](" in content else "")

    def test_image_embeds_in_the_body_are_emitted_as_absolute_urls(self):
        from wagtail.images.models import Image
        from wagtail.images.tests.utils import get_test_image_file
        from wagtail.models import Collection

        collection = Collection.get_first_root_node()
        image = Image.objects.create(
            title="Hero",
            file=get_test_image_file(),
            collection=collection,
        )
        rendition = image.get_rendition("width-800")
        self.create_document(
            body=RichText(
                f'<embed embedtype="image" id="{image.pk}" '
                f'format="fullwidth" alt="Hero">'
            )
        )
        content = self.client.get("/llms.txt").content.decode()
        self.assertIn(f"![Hero](http://testserver{rendition.url})", content)
        self.assertNotIn(f"![Hero]({rendition.url})", content)

    @override_settings(ALLOWED_HOSTS=MULTI_HOSTS)
    def test_host_selects_that_sites_document(self):
        self.create_document(title="Default host")
        other = self.add_site(OTHER_HOST)
        self.create_document(site=other, title="Other host")
        default = self.client.get("/llms.txt", HTTP_HOST="localhost")
        self.assertEqual(default.status_code, 200)
        self.assertIn(b"# Default host", default.content)
        self.assertNotIn(b"# Other host", default.content)
        other_resp = self.client.get("/llms.txt", HTTP_HOST=OTHER_HOST)
        self.assertEqual(other_resp.status_code, 200)
        self.assertIn(b"# Other host", other_resp.content)
        self.assertNotIn(b"# Default host", other_resp.content)

    @override_settings(ALLOWED_HOSTS=MULTI_HOSTS)
    def test_lang_prefixed_fallback_stays_within_that_site(self):
        self.create_document(title="Default English")
        other = self.add_site(OTHER_HOST)
        self.create_document(site=other, title="Other English")
        italian = italian_locale()
        self.create_document(site=other, locale=italian, title="   ")
        response = self.client.get("/it/llms.txt", HTTP_HOST=OTHER_HOST)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# Other English", response.content)
        self.assertNotIn(b"# Default English", response.content)

        LlmsTxt.objects.filter(site=other, locale=italian).delete()
        response = self.client.get("/it/llms.txt", HTTP_HOST=OTHER_HOST)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# Other English", response.content)
        self.assertNotIn(b"# Default English", response.content)

    def test_settings_menu_opens_the_singleton_for_the_current_admin_locale(self):
        self.login()
        italian_locale()
        response = self.client.get(snippet_url("list"), {"locale": "it"})
        self.assertEqual(LlmsTxt.objects.count(), 1)
        obj = LlmsTxt.objects.get()
        self.assertEqual(obj.locale, Locale.get_default())
        self.assertEqual(obj.site, self.site)
        self.assertRedirects(response, snippet_url("edit", obj.pk))

    def test_a_second_locale_reuses_the_same_translation_key(self):
        source = self.create_document()
        copy = LlmsTxt.get_for_locale(self.site, italian_locale())
        self.assertEqual(source.translation_key, copy.translation_key)
        self.assertNotEqual(source.locale_id, copy.locale_id)
        self.assertEqual(copy.site_id, source.site_id)

    def test_a_second_site_gets_a_different_translation_key(self):
        source = self.create_document()
        other = self.add_site(OTHER_HOST)
        other_doc = LlmsTxt.get_for_locale(other, Locale.get_default())
        self.assertNotEqual(source.translation_key, other_doc.translation_key)
        self.assertEqual(other_doc.site_id, other.pk)

    def test_copy_for_translation_keeps_the_same_site(self):
        source = self.create_document()
        copy = source.copy_for_translation(italian_locale())
        copy.save()
        self.assertEqual(copy.site_id, source.site_id)
        self.assertEqual(copy.translation_key, source.translation_key)

    def test_multi_site_index_lists_sites_without_creating_documents(self):
        self.login()
        self.add_site(OTHER_HOST)
        response = self.client.get(snippet_url("list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "localhost")
        self.assertContains(response, OTHER_HOST)
        self.assertEqual(LlmsTxt.objects.count(), 0)

    def test_multi_site_add_with_site_creates_that_sites_document(self):
        self.login()
        other = self.add_site(OTHER_HOST)
        response = self.client.get(snippet_url("add"), {"site": other.pk})
        self.assertEqual(LlmsTxt.objects.count(), 1)
        obj = LlmsTxt.objects.get()
        self.assertEqual(obj.site, other)
        self.assertRedirects(response, snippet_url("edit", obj.pk))

    def test_model_is_registered_as_a_snippet_with_add_to_settings_menu(self):
        self.assertIn(LlmsTxt, get_snippet_models())
        self.assertNotIn(LlmsTxt, snippet_models_for_index_view())
        self.assertTrue(LlmsTxt.snippet_viewset.add_to_settings_menu)

    def test_translate_submits_via_submit_snippet_translation_and_edit_is_intercepted(
        self,
    ):
        from wagtail_localize.models import Translation, TranslationSource

        self.login()
        source_doc = self.create_document()
        italian = italian_locale()
        edit_url = snippet_url("edit", source_doc.pk)
        response = self.client.get(edit_url)
        submit_url = reverse(
            "wagtail_localize:submit_snippet_translation",
            args=["agent_ready_llms_txt", "llmstxt", source_doc.pk],
        )
        self.assertContains(response, submit_url)

        source, _created = TranslationSource.get_or_create_from_instance(source_doc)
        translated = source_doc.copy_for_translation(italian)
        translated.title = "Documento italiano"
        translated.save()
        Translation.objects.create(source=source, target_locale=italian, enabled=True)

        intercepted = self.client.get(snippet_url("edit", translated.pk))
        self.assertTemplateUsed(
            intercepted, "wagtail_localize/admin/edit_translation.html"
        )

    def test_translated_locale_copy_can_be_deleted_default_cannot(self):
        self.login()
        source = self.create_document()
        copy = LlmsTxt.get_for_locale(self.site, italian_locale())
        copy.title = "Documento italiano"
        copy.save()

        default_delete = self.client.get(snippet_url("delete", source.pk))
        self.assertRedirects(default_delete, snippet_url("edit", source.pk))
        self.assertTrue(LlmsTxt.objects.filter(pk=source.pk).exists())

        delete_url = snippet_url("delete", copy.pk)
        confirm = self.client.get(delete_url)
        self.assertEqual(confirm.status_code, 200)
        self.client.post(delete_url)
        self.assertFalse(LlmsTxt.objects.filter(pk=copy.pk).exists())
        self.assertTrue(LlmsTxt.objects.filter(pk=source.pk).exists())

    def test_default_locale_of_one_site_cannot_be_deleted_when_another_site_exists(
        self,
    ):
        self.login()
        source = self.create_document()
        other = self.add_site(OTHER_HOST)
        self.create_document(site=other, title="Other site")
        default_delete = self.client.get(snippet_url("delete", source.pk))
        self.assertRedirects(default_delete, snippet_url("edit", source.pk))
        self.assertTrue(LlmsTxt.objects.filter(pk=source.pk).exists())

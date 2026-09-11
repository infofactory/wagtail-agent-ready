from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, reverse
from wagtail.models import Page, Site
from wagtail.snippets.models import get_snippet_models

from agent_ready.robots_txt.blocks import default_groups
from agent_ready.robots_txt.models import RobotsTxt
from agent_ready.test.models import AgentReadyHomePage
from agent_ready.tests.base import AgentReadySiteTestCase, snippet_models_for_index_view


OTHER_HOST = "other.example"
MULTI_HOSTS = ["localhost", "testserver", OTHER_HOST]
ROBOTS_CONTENT_TYPE = "text/plain; charset=UTF-8"


def snippet_url(view_name, *args):
    return reverse(RobotsTxt.snippet_viewset.get_url_name(view_name), args=args)


def group(
    *,
    comment="",
    user_agents=None,
    search=True,
    ai_input=True,
    ai_train=False,
    allow="/",
    disallow="",
):
    return (
        "group",
        {
            "comment": comment,
            "user_agents": user_agents if user_agents is not None else [],
            "search": search,
            "ai_input": ai_input,
            "ai_train": ai_train,
            "allow": allow,
            "disallow": disallow,
        },
    )


class RobotsTxtTests(AgentReadySiteTestCase):
    def create_document(self, comment="", groups=None, site=None):
        return RobotsTxt.objects.create(
            comment=comment,
            groups=groups if groups is not None else [group()],
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

    def test_robots_txt_returns_404_when_no_document_exists(self):
        response = self.client.get("/robots.txt", follow=True)
        self.assertEqual(response.status_code, 404)

    def test_robots_txt_returns_200_with_comment_groups_signals_and_sitemap(self):
        self.create_document(
            comment="file-level comment",
            groups=[
                group(comment="all crawlers"),
                group(
                    user_agents=["GPTBot", "ClaudeBot"],
                    allow="/\n/blog/",
                    disallow="/admin/",
                    ai_train=True,
                ),
            ],
        )
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], ROBOTS_CONTENT_TYPE)
        content = response.content.decode()
        self.assertEqual(
            content,
            "# file-level comment\n"
            "\n"
            "# all crawlers\n"
            "User-agent: *\n"
            "Allow: /\n"
            "Content-Signal: search=yes, ai-input=yes, ai-train=no\n"
            "\n"
            "User-agent: GPTBot\n"
            "User-agent: ClaudeBot\n"
            "Allow: /\n"
            "Allow: /blog/\n"
            "Disallow: /admin/\n"
            "Content-Signal: search=yes, ai-input=yes, ai-train=yes\n"
            "\n"
            "Sitemap: http://testserver/sitemap.xml\n",
        )

    def test_existing_hash_prefix_on_comments_is_not_doubled(self):
        self.create_document(comment="# already hashed\nplain")
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("# already hashed\n", content)
        self.assertIn("# plain\n", content)
        self.assertNotIn("# # already hashed", content)

    def test_empty_user_agents_emit_star(self):
        self.create_document(groups=[group(user_agents=[])])
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("User-agent: *\n", content)

    def test_blank_user_agent_strings_are_treated_as_empty(self):
        self.create_document(groups=[group(user_agents=["", "  "])])
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("User-agent: *\n", content)
        self.assertNotIn("User-agent:  \n", content)

    def test_allow_and_disallow_prefixes_on_pasted_paths_are_stripped(self):
        self.create_document(
            groups=[
                group(
                    allow="Allow: /\nallow:/blog/",
                    disallow="Disallow: /admin/\nDISALLOW: /secret",
                )
            ]
        )
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("Allow: /\n", content)
        self.assertIn("Allow: /blog/\n", content)
        self.assertIn("Disallow: /admin/\n", content)
        self.assertIn("Disallow: /secret\n", content)
        self.assertNotIn("Allow: Allow:", content)
        self.assertNotIn("Disallow: Disallow:", content)

    def test_sitemap_line_is_omitted_when_sitemap_xml_does_not_resolve(self):
        self.create_document()
        with override_settings(ROOT_URLCONF="agent_ready.robots_txt.urls"):
            content = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("Sitemap:", content)
        self.assertIn("User-agent: *\n", content)

    def test_does_not_follow_accept_language_and_is_not_locale_prefixed(self):
        self.create_document(comment="origin")
        response = self.client.get("/robots.txt", HTTP_ACCEPT_LANGUAGE="it")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"# origin", response.content)
        prefixed = self.client.get("/en/robots.txt")
        self.assertEqual(prefixed.status_code, 404)

    @override_settings(ALLOWED_HOSTS=MULTI_HOSTS)
    def test_host_selects_that_sites_document(self):
        self.create_document(comment="Default host")
        other = self.add_site(OTHER_HOST)
        self.create_document(comment="Other host", site=other)
        default = self.client.get("/robots.txt", HTTP_HOST="localhost")
        self.assertEqual(default.status_code, 200)
        self.assertIn(b"# Default host", default.content)
        self.assertNotIn(b"# Other host", default.content)
        other_resp = self.client.get("/robots.txt", HTTP_HOST=OTHER_HOST)
        self.assertEqual(other_resp.status_code, 200)
        self.assertIn(b"# Other host", other_resp.content)
        self.assertNotIn(b"# Default host", other_resp.content)

    def test_settings_menu_opens_the_singleton_and_seeds_default_groups(self):
        self.login()
        response = self.client.get(snippet_url("list"))
        self.assertEqual(RobotsTxt.objects.count(), 1)
        obj = RobotsTxt.objects.get()
        self.assertEqual(obj.site, self.site)
        self.assertRedirects(response, snippet_url("edit", obj.pk))
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("User-agent: *\n", content)
        self.assertIn("Allow: /\n", content)
        self.assertIn("Disallow: /admin/\n", content)
        self.assertIn("Disallow: /django-admin/\n", content)
        self.assertIn("Sitemap: http://testserver/sitemap.xml\n", content)

    def test_multi_site_index_lists_sites_without_creating_documents(self):
        self.login()
        self.add_site(OTHER_HOST)
        response = self.client.get(snippet_url("list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "localhost")
        self.assertContains(response, OTHER_HOST)
        self.assertEqual(RobotsTxt.objects.count(), 0)

    def test_multi_site_add_with_site_creates_that_sites_document(self):
        self.login()
        other = self.add_site(OTHER_HOST)
        response = self.client.get(snippet_url("add"), {"site": other.pk})
        self.assertEqual(RobotsTxt.objects.count(), 1)
        obj = RobotsTxt.objects.get()
        self.assertEqual(obj.site, other)
        self.assertRedirects(response, snippet_url("edit", obj.pk))

    def test_model_is_registered_as_a_snippet_with_add_to_settings_menu(self):
        self.assertIn(RobotsTxt, get_snippet_models())
        self.assertNotIn(RobotsTxt, snippet_models_for_index_view())
        self.assertTrue(RobotsTxt.snippet_viewset.add_to_settings_menu)

    def test_delete_is_hidden_and_redirects_to_edit(self):
        self.login()
        obj = self.create_document()
        edit_url = snippet_url("edit", obj.pk)
        edit = self.client.get(edit_url)
        self.assertEqual(edit.status_code, 200)
        self.assertIsNone(edit.context["view"].get_delete_url())
        delete = self.client.get(snippet_url("delete", obj.pk))
        self.assertRedirects(delete, edit_url)
        self.assertTrue(RobotsTxt.objects.filter(pk=obj.pk).exists())


def _reverse_admins(name):
    if name == "wagtailadmin_home":
        return "/cms"
    if name == "admin:index":
        return "/hidden-admin/"
    raise NoReverseMatch(name)


def _reverse_wagtail_only(name):
    if name == "wagtailadmin_home":
        return "/admin/"
    raise NoReverseMatch(name)


class DefaultRobotsGroupsTests(SimpleTestCase):
    def test_default_disallow_includes_mounted_wagtail_and_django_admin(self):
        self.assertEqual(reverse("wagtailadmin_home"), "/admin/")
        self.assertEqual(reverse("admin:index"), "/django-admin/")
        self.assertEqual(
            default_groups()[0][1]["disallow"],
            "/admin/\n/django-admin/",
        )

    @override_settings(ROOT_URLCONF="agent_ready.robots_txt.urls")
    def test_default_disallow_is_blank_when_admins_are_not_mounted(self):
        self.assertEqual(default_groups()[0][1]["disallow"], "")

    @patch("agent_ready.robots_txt.blocks.reverse", side_effect=_reverse_admins)
    def test_default_disallow_follows_custom_admin_mounts(self, _reverse):
        self.assertEqual(
            default_groups()[0][1]["disallow"],
            "/cms/\n/hidden-admin/",
        )

    @patch("agent_ready.robots_txt.blocks.reverse", side_effect=_reverse_wagtail_only)
    def test_django_admin_is_omitted_when_not_mounted(self, _reverse):
        self.assertEqual(default_groups()[0][1]["disallow"], "/admin/")

from wagtail import hooks

from agent_ready.mixins import on_serve_agent_ready


# order=10 keeps Wagtail's view-restriction hook (order=0) outside this wrapper.
# on_serve_page applies hooks in reverse order, so the lower order stays outer.
hooks.register("on_serve_page", on_serve_agent_ready, order=10)

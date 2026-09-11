from wagtail import blocks


class MethodWinsBlock(blocks.CharBlock):
    class Meta:
        template = "agent_ready_test/blocks/method_wins.html"

    def to_markdown(self, value, context=None):
        return f"FROM_METHOD:{value}"


class TwinTemplateBlock(blocks.CharBlock):
    class Meta:
        template = "agent_ready_test/blocks/twin.html"


class NestedStructBlock(blocks.StructBlock):
    note = blocks.CharBlock(label="Note")

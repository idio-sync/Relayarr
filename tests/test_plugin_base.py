import pytest
from bot.plugins.base import Plugin, Command, CommandContext


class TestCommand:
    def test_command_defaults(self):
        async def handler(ctx):
            pass
        cmd = Command(name="test", handler=handler, help_text="A test command")
        assert cmd.required_role == "user"
        assert cmd.plugin == ""

    def test_command_admin_role(self):
        async def handler(ctx):
            pass
        cmd = Command(name="admin_cmd", handler=handler, help_text="Admin only", required_role="admin")
        assert cmd.required_role == "admin"


class TestCommandContext:
    def test_context_fields(self):
        replies = []
        async def reply_fn(msg):
            replies.append(msg)
        ctx = CommandContext(
            sender="testuser",
            hostmask="testuser!~user@host.example.com",
            channel="#test",
            args=["movie", "Batman"],
            reply=reply_fn,
        )
        assert ctx.sender == "testuser"
        assert ctx.args == ["movie", "Batman"]
        assert ctx.channel == "#test"

    async def test_context_reply(self):
        replies = []
        async def reply_fn(msg):
            replies.append(msg)
        ctx = CommandContext(
            sender="testuser",
            hostmask="testuser!~user@host.example.com",
            channel="#test",
            args=[],
            reply=reply_fn,
        )
        await ctx.reply("hello")
        assert replies == ["hello"]


class DummyPlugin(Plugin):
    def name(self) -> str:
        return "dummy"

    def register_commands(self) -> list[Command]:
        async def hello(ctx: CommandContext):
            await ctx.reply("Hello!")
        return [Command(name="hello", handler=hello, help_text="Say hello")]


class TestPlugin:
    def test_plugin_name(self):
        p = DummyPlugin()
        assert p.name() == "dummy"

    def test_plugin_registers_commands(self):
        p = DummyPlugin()
        commands = p.register_commands()
        assert len(commands) == 1
        assert commands[0].name == "hello"

    async def test_on_load_default(self):
        p = DummyPlugin()
        await p.on_load()

    async def test_on_unload_default(self):
        p = DummyPlugin()
        await p.on_unload()

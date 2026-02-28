import pytest
from bot.core.dispatcher import Dispatcher
from bot.plugins.base import Command, CommandContext, Plugin


class FakePlugin(Plugin):
    def __init__(self):
        self.received_args: list[list[str]] = []

    def name(self) -> str:
        return "fake"

    def register_commands(self) -> list[Command]:
        return [
            Command(name="request", handler=self._handle_request, help_text="Request media"),
            Command(name="status", handler=self._handle_status, help_text="Check status"),
        ]

    async def _handle_request(self, ctx: CommandContext):
        self.received_args.append(ctx.args)
        await ctx.reply("OK")

    async def _handle_status(self, ctx: CommandContext):
        await ctx.reply("No pending requests")


class TestDispatcher:
    def test_register_plugin_commands(self):
        d = Dispatcher(prefix="!")
        plugin = FakePlugin()
        d.register_plugin(plugin)
        assert "request" in d.commands
        assert "status" in d.commands
        assert d.commands["request"].plugin == "fake"

    def test_parse_command(self):
        d = Dispatcher(prefix="!")
        result = d.parse("!request movie Batman")
        assert result is not None
        cmd_name, args = result
        assert cmd_name == "request"
        assert args == ["movie", "Batman"]

    def test_parse_no_prefix(self):
        d = Dispatcher(prefix="!")
        result = d.parse("hello world")
        assert result is None

    def test_parse_different_prefix(self):
        d = Dispatcher(prefix=".")
        result = d.parse(".status")
        assert result is not None
        cmd_name, args = result
        assert cmd_name == "status"
        assert args == []

    def test_parse_empty_after_prefix(self):
        d = Dispatcher(prefix="!")
        result = d.parse("!")
        assert result is None

    async def test_dispatch_calls_handler(self):
        d = Dispatcher(prefix="!")
        plugin = FakePlugin()
        d.register_plugin(plugin)
        replies = []
        async def reply(msg):
            replies.append(msg)
        await d.dispatch(
            command_name="request",
            ctx=CommandContext(sender="user", hostmask="user!~u@host", channel="#test", args=["movie", "Batman"], reply=reply),
        )
        assert replies == ["OK"]
        assert plugin.received_args == [["movie", "Batman"]]

    async def test_dispatch_unknown_command(self):
        d = Dispatcher(prefix="!")
        replies = []
        async def reply(msg):
            replies.append(msg)
        await d.dispatch(
            command_name="nonexistent",
            ctx=CommandContext(sender="user", hostmask="user!~u@host", channel="#test", args=[], reply=reply),
        )
        assert any("Unknown command" in r for r in replies)

    def test_generate_help(self):
        d = Dispatcher(prefix="!")
        plugin = FakePlugin()
        d.register_plugin(plugin)
        help_lines = d.help_text()
        assert any("request" in line for line in help_lines)
        assert any("status" in line for line in help_lines)

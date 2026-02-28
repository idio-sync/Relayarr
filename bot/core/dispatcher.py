import logging
from bot.plugins.base import Command, CommandContext, Plugin

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, prefix: str = "!"):
        self.prefix = prefix
        self.commands: dict[str, Command] = {}

    def register_plugin(self, plugin: Plugin) -> None:
        for cmd in plugin.register_commands():
            cmd.plugin = plugin.name()
            self.commands[cmd.name] = cmd
            logger.info(f"Registered command: {self.prefix}{cmd.name} [{plugin.name()}]")

    def parse(self, message: str) -> tuple[str, list[str]] | None:
        if not message.startswith(self.prefix):
            return None
        without_prefix = message[len(self.prefix):].strip()
        if not without_prefix:
            return None
        parts = without_prefix.split()
        return parts[0].lower(), parts[1:]

    async def dispatch(self, command_name: str, ctx: CommandContext) -> None:
        if command_name not in self.commands:
            await ctx.reply(f"Unknown command: {self.prefix}{command_name}. Use {self.prefix}help for available commands.")
            return
        cmd = self.commands[command_name]
        await cmd.handler(ctx)

    def help_text(self) -> list[str]:
        lines = ["Available commands:"]
        by_plugin: dict[str, list[Command]] = {}
        for cmd in self.commands.values():
            by_plugin.setdefault(cmd.plugin, []).append(cmd)
        for plugin_name, cmds in sorted(by_plugin.items()):
            lines.append(f"  [{plugin_name}]")
            for cmd in sorted(cmds, key=lambda c: c.name):
                lines.append(f"    {self.prefix}{cmd.name} - {cmd.help_text}")
        return lines

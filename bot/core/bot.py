# bot/core/bot.py
import asyncio
import logging
import ssl as ssl_module

import irc.client_aio
import irc.client
import irc.connection

from bot.core.auth import AuthManager
from bot.core.dispatcher import Dispatcher
from bot.plugins.base import CommandContext

logger = logging.getLogger(__name__)

FLOOD_DELAY = 0.35


class IRCBot:
    def __init__(self, server: str, port: int, ssl: bool, nickname: str, channels: list[str], command_prefix: str):
        self.server = server
        self.port = port
        self.ssl = ssl
        self.nickname = nickname
        self.channels = channels
        self.dispatcher = Dispatcher(prefix=command_prefix)
        self.auth: AuthManager | None = None
        self._reactor: irc.client_aio.AioReactor | None = None
        self._connection = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @staticmethod
    def build_hostmask(nick: str, user: str, host: str) -> str:
        return f"{nick}!{user}@{host}"

    async def connect(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._reactor = irc.client_aio.AioReactor(loop=self._loop)
        server = self._reactor.server()

        connect_kwargs = {}
        if self.ssl:
            ssl_ctx = ssl_module.create_default_context()
            connect_kwargs["connect_factory"] = irc.connection.AioFactory(ssl=ssl_ctx)

        self._connection = await server.connect(
            self.server, self.port, self.nickname, **connect_kwargs
        )

        self._connection.add_global_handler("welcome", self._on_welcome)
        self._connection.add_global_handler("pubmsg", self._on_pubmsg)
        self._connection.add_global_handler("disconnect", self._on_disconnect)
        self._connection.add_global_handler("nicknameinuse", self._on_nick_in_use)

        logger.info(f"Connected to {self.server}:{self.port} as {self.nickname}")

    def _on_welcome(self, connection, event):
        for channel in self.channels:
            connection.join(channel)
            logger.info(f"Joining {channel}")

    def _on_nick_in_use(self, connection, event):
        new_nick = self.nickname + "_"
        logger.warning(f"Nickname in use, trying {new_nick}")
        connection.nick(new_nick)

    def _on_disconnect(self, connection, event):
        logger.warning("Disconnected from server, reconnecting in 30s...")
        if self._loop:
            self._loop.call_later(30, lambda: asyncio.ensure_future(self.connect()))

    def _on_pubmsg(self, connection, event):
        message = event.arguments[0]
        parsed = self.dispatcher.parse(message)
        if parsed is None:
            return

        cmd_name, args = parsed
        nick = event.source.nick
        user = event.source.user or "unknown"
        host = event.source.host or "unknown"
        hostmask = self.build_hostmask(nick, user, host)
        channel = event.target

        if self.auth and cmd_name in self.dispatcher.commands:
            required_role = self.dispatcher.commands[cmd_name].required_role
            if not self.auth.check_permission(hostmask, required_role):
                asyncio.ensure_future(self._send(connection, channel, f"{nick}: Permission denied."))
                return

        if cmd_name == "help":
            asyncio.ensure_future(self._send_help(connection, channel))
            return

        async def reply(msg: str):
            await self._send(connection, channel, msg)

        ctx = CommandContext(
            sender=nick, hostmask=hostmask, channel=channel, args=args, reply=reply,
        )
        asyncio.ensure_future(self.dispatcher.dispatch(cmd_name, ctx))

    async def _send(self, connection, target: str, message: str) -> None:
        connection.privmsg(target, message)
        await asyncio.sleep(FLOOD_DELAY)

    async def _send_help(self, connection, channel: str) -> None:
        for line in self.dispatcher.help_text():
            await self._send(connection, channel, line)

    async def run(self) -> None:
        await self.connect()
        self._reactor.process_forever()

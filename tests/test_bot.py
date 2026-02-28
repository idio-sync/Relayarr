# tests/test_bot.py
import pytest
from bot.core.bot import IRCBot


class TestIRCBotSetup:
    def test_bot_initializes(self):
        bot = IRCBot(
            server="irc.example.com",
            port=6697,
            ssl=True,
            nickname="TestBot",
            channels=["#test"],
            command_prefix="!",
        )
        assert bot.nickname == "TestBot"
        assert bot.channels == ["#test"]

    def test_bot_builds_hostmask(self):
        assert IRCBot.build_hostmask(
            nick="user", user="~realuser", host="example.com"
        ) == "user!~realuser@example.com"

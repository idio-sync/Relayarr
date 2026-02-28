# main.py
import asyncio
import logging
import sys
from pathlib import Path

from bot.core.bot import IRCBot
from bot.core.config import Config
from bot.core.database import Database
from bot.core.auth import AuthManager
from bot.plugins.overseerr.api import OverseerrClient
from bot.plugins.overseerr.plugin import OverseerrPlugin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("relayarr")


async def main():
    # Load config
    config_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "/data/config.yaml"
    )
    logger.info(f"Loading config from {config_path}")
    config = Config.load(config_path)

    # Initialize database
    db_path = Path(config.get("database.path", "/data/bot.db"))
    db = Database(db_path)
    await db.initialize()
    logger.info(f"Database initialized at {db_path}")

    # Create IRC bot
    bot = IRCBot(
        server=config["irc"]["server"],
        port=config["irc"]["port"],
        ssl=config["irc"].get("ssl", False),
        nickname=config["irc"]["nickname"],
        channels=config["irc"]["channels"],
        command_prefix=config["irc"].get("command_prefix", "!"),
    )

    # Set up auth
    auth_config = config.get("auth", {}) or {}
    bot.auth = AuthManager(
        admins=auth_config.get("admins", []),
        users=auth_config.get("users", []),
        default_role=auth_config.get("default_role", "none"),
    )

    # Load enabled plugins
    enabled = config.get("plugins.enabled", []) or []

    if "overseerr" in enabled:
        overseerr_config = config["overseerr"]
        api = OverseerrClient(
            base_url=overseerr_config["url"],
            api_key=overseerr_config["api_key"],
        )
        plugin = OverseerrPlugin(
            api=api,
            db=db,
            irc_colors=config.get("formatting.irc_colors", True),
            session_timeout=config.get("session.timeout_seconds", 300),
        )
        bot.dispatcher.register_plugin(plugin)
        await plugin.on_load()
        logger.info("Overseerr plugin loaded")

    # Run bot
    logger.info(f"Connecting to {config['irc']['server']}:{config['irc']['port']}")
    try:
        await bot.run()
    finally:
        await db.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

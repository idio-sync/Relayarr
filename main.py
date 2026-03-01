# main.py
import asyncio
import logging
import os
import sys
from pathlib import Path

from bot.core.bot import IRCBot
from bot.core.config import Config
from bot.core.database import Database
from bot.core.auth import AuthManager
from bot.plugins.overseerr.api import OverseerrClient
from bot.plugins.overseerr.plugin import OverseerrPlugin
from bot.plugins.lidarr.api import LidarrClient
from bot.plugins.lidarr.plugin import LidarrPlugin
from bot.plugins.media_coordinator import MediaCoordinator
from bot.plugins.romm.api import RommClient
from bot.plugins.romm.plugin import RommPlugin
from bot.plugins.romm.igdb import IGDBClient
from bot.plugins.plex.plex_client import PlexClient
from bot.plugins.plex.tautulli_client import TautulliClient
from bot.plugins.plex.plugin import PlexPlugin
from bot.plugins.plex.formatters import PlexFormatter
from bot.web import create_web_app, run_web_server
from bot.web.auth import hash_password

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

    # Load enabled plugins via media coordinator
    enabled = config.get("plugins.enabled", []) or []
    backends = {}

    if "overseerr" in enabled:
        overseerr_config = config["overseerr"]
        overseerr_api = OverseerrClient(
            base_url=overseerr_config["url"],
            api_key=overseerr_config["api_key"],
        )
        overseerr_plugin = OverseerrPlugin(
            api=overseerr_api,
            db=db,
            irc_colors=config.get("formatting.irc_colors", True),
            session_timeout=config.get("session.timeout_seconds", 300),
        )
        backends["movie"] = overseerr_plugin
        backends["tv"] = overseerr_plugin
        await overseerr_plugin.on_load()
        logger.info("Overseerr plugin loaded")

    if "lidarr" in enabled:
        lidarr_config = config["lidarr"]
        lidarr_api = LidarrClient(
            base_url=lidarr_config["url"],
            api_key=lidarr_config["api_key"],
            quality_profile_id=lidarr_config.get("quality_profile_id", 1),
            metadata_profile_id=lidarr_config.get("metadata_profile_id", 1),
            root_folder_path=lidarr_config.get("root_folder_path", "/music"),
        )
        lidarr_plugin = LidarrPlugin(
            api=lidarr_api,
            db=db,
            irc_colors=config.get("formatting.irc_colors", True),
            session_timeout=config.get("session.timeout_seconds", 300),
        )
        backends["music"] = lidarr_plugin
        await lidarr_plugin.on_load()
        logger.info("Lidarr plugin loaded")

    romm_plugin = None
    if "romm" in enabled:
        romm_config = config["romm"]
        romm_api = RommClient(
            base_url=romm_config["url"],
            username=romm_config["username"],
            password=romm_config["password"],
            domain=romm_config.get("domain", romm_config["url"]),
        )
        igdb = None
        igdb_id = romm_config.get("igdb_client_id")
        igdb_secret = romm_config.get("igdb_client_secret")
        if igdb_id and igdb_secret:
            igdb = IGDBClient(client_id=igdb_id, client_secret=igdb_secret)
            logger.info("IGDB integration enabled for RomM")
        romm_plugin = RommPlugin(
            api=romm_api,
            db=db,
            igdb=igdb,
            irc_colors=config.get("formatting.irc_colors", True),
            session_timeout=config.get("session.timeout_seconds", 300),
        )
        bot.dispatcher.register_plugin(romm_plugin)
        await romm_plugin.on_load()
        logger.info("RomM plugin loaded")

    if romm_plugin:
        notif_config = config.get("romm.notifications", {}) or {}
        if notif_config.get("enabled", False):
            notif_channel = notif_config.get("channel", "#romm")
            notif_interval = notif_config.get("interval", 300)

            async def send_to_channel(msg):
                await bot.send_message(notif_channel, msg)

            romm_plugin.start_notifications(send_to_channel, interval=notif_interval)
            logger.info(f"RomM notifications enabled for {notif_channel} every {notif_interval}s")

    if "plex" in enabled:
        plex_config = config["plex"]
        plex_api = PlexClient(
            base_url=plex_config["url"],
            token=plex_config["token"],
        )
        tautulli_api = None
        if config.get("tautulli"):
            tautulli_config = config["tautulli"]
            tautulli_api = TautulliClient(
                base_url=tautulli_config["url"],
                api_key=tautulli_config["api_key"],
            )
        plex_plugin = PlexPlugin(
            plex_api=plex_api,
            tautulli_api=tautulli_api,
            formatter=PlexFormatter(irc_colors=config.get("formatting.irc_colors", True)),
            announce_channel=plex_config.get("announce_channel"),
            announce_interval=plex_config.get("announce_interval", 300),
            send_callback=bot.send_message,
        )
        bot.dispatcher.register_plugin(plex_plugin)
        await plex_plugin.on_load()
        logger.info("Plex plugin loaded")

    if backends:
        coordinator = MediaCoordinator(
            backends=backends,
            session_timeout=config.get("session.timeout_seconds", 300),
            romm_backend=romm_plugin,
        )
        bot.dispatcher.register_plugin(coordinator)

    # Start web UI
    web_password = os.environ.get("WEB_PASSWORD")
    web_runner = None
    if web_password:
        password_hash = hash_password(web_password)
        web_port = config.get("web.port", 9090)
        app = create_web_app(config_path, password_hash)
        web_runner = await run_web_server(app, port=web_port)
    else:
        logger.warning("WEB_PASSWORD not set, web UI disabled")

    # Run bot
    logger.info(f"Connecting to {config['irc']['server']}:{config['irc']['port']}")
    try:
        await bot.run()
    finally:
        if web_runner:
            await web_runner.cleanup()
        await db.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

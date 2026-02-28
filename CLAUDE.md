# Relayarr

## Project Overview
IRC bot that interfaces with media management APIs (Overseerr, Lidarr) for requesting media. Plugin-based architecture for extensibility. Includes a web UI for configuration.

## Tech Stack
- Python 3.12, asyncio throughout
- `irc` (jaraco) for IRC connectivity (`irc.client_aio.AioReactor`)
- `aiohttp` for HTTP client (Overseerr/Lidarr APIs) and web server (config UI)
- `aiosqlite` for async SQLite database
- `pyyaml` for config loading
- `bcrypt` for web UI password hashing
- `aiohttp-jinja2` + `aiohttp-session[secure]` for web UI
- `pytest` with `asyncio_mode = "auto"`

## Project Structure
```
bot/
  core/         - Config, Database, AuthManager, Dispatcher, IRCBot
  plugins/
    base.py     - Plugin ABC, Command, CommandContext dataclasses
    overseerr/  - Overseerr plugin (api.py, formatters.py, plugin.py)
    lidarr/     - Lidarr plugin (api.py, formatters.py, plugin.py)
    media_coordinator.py - Routes shared commands to backend plugins
  web/          - Web config UI (auth, routes, server, config_form, templates, static)
main.py         - Entry point wiring everything together
tests/          - All tests (pytest)
config/         - config.example.yaml
```

## Key Patterns
- Plugins implement `Plugin` ABC with `name()` and `register_commands()` methods
- MediaCoordinator routes shared commands (request/select/status) to backend plugins
- Commands use `CommandContext` dataclass with async `reply` callback
- Config uses YAML with `${VAR}` env substitution and `SECTION__KEY` env overrides
- Auth uses fnmatch hostmask patterns with role hierarchy (admin > user > none)
- Web UI uses save-and-restart model (config saved to disk, bot must restart)
- Sensitive fields (API keys) are masked in web UI forms

## Build & Test
```bash
source .venv/bin/activate
python -m pytest tests/ -v          # Run all tests
python main.py                      # Run bot (needs /data/config.yaml)
python main.py path/to/config.yaml  # Run with custom config path
```

## Environment Variables
- `OVERSEERR_API_KEY` - API key for Overseerr (used in config via `${OVERSEERR_API_KEY}`)
- `LIDARR_API_KEY` - API key for Lidarr (used in config via `${LIDARR_API_KEY}`)
- `WEB_PASSWORD` - Set to enable web UI (bcrypt hashed at startup)
- `IRC__SERVER`, `IRC__PORT`, etc. - Config overrides via `SECTION__KEY` format

## Docker
```bash
docker compose up -d                # Runs on media network, port 9090 for web UI
```
Volume: `./bot-data:/data` (config.yaml + bot.db)

## Important Notes
- Web server and IRC bot share the same asyncio event loop (single process)
- `EncryptedCookieStorage` needs the session middleware registered BEFORE auth middleware
- `MultiDict.getall()` raises `KeyError` (not returns []) when key is missing
- Config atomic writes use `os.replace()` via temp file to prevent corruption

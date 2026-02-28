# Relayarr

An IRC bot for requesting media through Overseerr/Seerr, with a plugin-based architecture for future service integrations. Think [Requestrr](https://github.com/darkalfx/requestrr) but for IRC.

## Features

- **Media Requests** - Search and request movies/TV shows via Overseerr directly from IRC
- **Rich Formatting** - Search results with TMDB links, synopsis, year, and mIRC color formatting
- **Plugin Architecture** - Modular design for adding new service integrations
- **Role-Based Auth** - Admin/user roles via IRC hostmask pattern matching
- **Web Config UI** - Dark-themed browser interface for managing all bot settings
- **Docker Ready** - Single container with one data volume

## Quick Start

### Docker (Recommended)

1. Copy the example config:
   ```bash
   mkdir bot-data
   cp config/config.example.yaml bot-data/config.yaml
   ```

2. Edit `bot-data/config.yaml` with your IRC server and Overseerr details.

3. Create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your API key and web password
   ```

4. Start the container:
   ```bash
   docker compose up -d
   ```

5. Access the web UI at `http://localhost:9090` (if `WEB_PASSWORD` is set).

### Manual

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py path/to/config.yaml
```

## IRC Commands

| Command | Description |
|---------|-------------|
| `!request movie <query>` | Search for a movie |
| `!request tv <query>` | Search for a TV show |
| `!select <number>` | Request a title from search results |
| `!status` | Check your pending requests |
| `!help` | List all available commands |

The command prefix (default `!`) is configurable.

## Configuration

Configuration is managed via `config.yaml` (or through the web UI):

```yaml
irc:
  server: "irc.example.com"
  port: 6697
  ssl: true
  nickname: "Relayarr"
  channels:
    - "#requests"
  command_prefix: "!"

auth:
  admins:
    - "*!*@admin.host.mask"
  users:
    - "*!*@*.trusted.network"
  default_role: "none"

overseerr:
  url: "http://overseerr:5055"
  api_key: "${OVERSEERR_API_KEY}"

plugins:
  enabled:
    - overseerr

database:
  path: "/data/bot.db"

session:
  timeout_seconds: 300

formatting:
  irc_colors: true

web:
  port: 9090
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OVERSEERR_API_KEY` | Overseerr API key (referenced in config via `${OVERSEERR_API_KEY}`) |
| `WEB_PASSWORD` | Password for the web config UI (required to enable it) |

Config values can also be overridden with env vars using `SECTION__KEY` format (e.g., `IRC__SERVER=irc.example.com`).

## Web UI

Set the `WEB_PASSWORD` environment variable to enable the web configuration interface. It provides:

- Tabbed interface for IRC, Auth, Plugins, and Advanced settings
- Sensitive field masking (API keys displayed as `********`)
- Form validation with error messages
- Atomic config saves (no corruption on failure)

Changes are saved to disk. Restart the bot to apply them.

## Architecture

```
bot/
  core/
    config.py       # YAML config with env var substitution
    database.py     # Async SQLite wrapper
    auth.py         # Hostmask-based role authentication
    dispatcher.py   # Command prefix parsing and routing
    bot.py          # IRC connection and event handling
  plugins/
    base.py         # Plugin ABC, Command/CommandContext types
    overseerr/      # Overseerr integration plugin
  web/
    server.py       # aiohttp app factory
    routes.py       # Login, config, save, logout handlers
    auth.py         # Password hashing and session middleware
    config_form.py  # Form loading, validation, atomic save
    templates/      # Jinja2 HTML templates
    static/         # CSS
main.py             # Entry point
```

## Development

```bash
source .venv/bin/activate
python -m pytest tests/ -v    # 114 tests
```

## License

MIT

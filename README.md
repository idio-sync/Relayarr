# Relayarr

An IRC bot for requesting media through Overseerr, Lidarr, and RomM, with Plex server monitoring and a plugin-based architecture for service integrations. Think [Requestrr](https://github.com/darkalfx/requestrr) but for IRC.

## Features

- **Media Requests** - Search and request movies/TV shows via Overseerr, music via Lidarr
- **Plex Monitoring** - Now playing streams, library stats with growth, and auto-announced recently added items (optional Tautulli enrichment)
- **ROM Management** - Browse, search, and request ROMs via [RomM](https://github.com/rommapp/romm) with optional IGDB metadata enrichment
- **Rich Formatting** - Search results with TMDB/MusicBrainz/IGDB links, synopsis, and mIRC color formatting
- **Notifications** - Recently-added ROM and Plex announcements to configured IRC channels
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

2. Edit `bot-data/config.yaml` with your IRC server, Overseerr, Lidarr, Plex, and/or RomM details.

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

### Media Requests

| Command | Description |
|---------|-------------|
| `!request movie <title>` | Search for a movie |
| `!request tv <title>` | Search for a TV show |
| `!request music <artist>` | Search for a music artist |
| `!select <number>` | Select from search results |
| `!status` | Check your pending requests |

### Plex

| Command | Description |
|---------|-------------|
| `!plex playing` / `!np` | Show currently active streams (Tautulli-enriched if configured) |
| `!plex stats` / `!plexstats` | Library counts with 7-day growth |
| `!plex recent` / `!plexrecent` | Last 5 recently added items |

Recently added items are also auto-announced to a configured channel (if `announce_channel` is set).

### ROM Management

| Command | Description |
|---------|-------------|
| `!game <platform> <title>` | Search ROMs (falls back to IGDB for requests) |
| `!select <number>` | Select from ROM or IGDB results |
| `!platforms` | List available ROM platforms |
| `!gamestats` | Show collection statistics |
| `!random [platform]` | Get a random ROM |
| `!firmware <platform>` | List firmware files for a platform |
| `!myrequests` | View your ROM request history |

### General

| Command | Description |
|---------|-------------|
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

lidarr:
  url: "http://lidarr:8686"
  api_key: "${LIDARR_API_KEY}"
  quality_profile_id: 1
  metadata_profile_id: 1
  root_folder_path: "/music"

plex:
  url: "http://plex:32400"
  token: "${PLEX_TOKEN}"
  announce_channel: "#media"
  announce_interval: 300

# tautulli:
#   url: "http://tautulli:8181"
#   api_key: "${TAUTULLI_API_KEY}"

romm:
  url: "http://romm:8080"
  username: "admin"
  password: "${ROMM_PASSWORD}"
  domain: "https://romm.example.com"
  igdb_client_id: "${IGDB_CLIENT_ID}"
  igdb_client_secret: "${IGDB_CLIENT_SECRET}"
  notifications:
    enabled: false
    channel: "#romm"
    interval: 300

plugins:
  enabled:
    - overseerr
    # - lidarr
    # - plex
    # - romm

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
| `LIDARR_API_KEY` | Lidarr API key (referenced in config via `${LIDARR_API_KEY}`) |
| `PLEX_TOKEN` | Plex authentication token (referenced in config via `${PLEX_TOKEN}`) |
| `TAUTULLI_API_KEY` | Tautulli API key for enriched now-playing data (optional) |
| `ROMM_PASSWORD` | RomM password (referenced in config via `${ROMM_PASSWORD}`) |
| `IGDB_CLIENT_ID` | Twitch/IGDB client ID for game metadata enrichment (optional) |
| `IGDB_CLIENT_SECRET` | Twitch/IGDB client secret (optional) |
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
    media_coordinator.py  # Routes shared commands to backends
    overseerr/      # Overseerr integration (movies/TV)
    lidarr/         # Lidarr integration (music)
    plex/           # Plex monitoring (now playing, stats, recently added)
    romm/           # RomM integration (ROMs/retro games)
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
python -m pytest tests/ -v    # 381 tests
```

## License

MIT

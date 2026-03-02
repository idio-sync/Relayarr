import os
from pathlib import Path
from typing import Any

import yaml

MASK = "********"
SENSITIVE_FIELDS = {
    "overseerr.api_key", "lidarr.api_key", "plex.token", "tautulli.api_key",
    "shelfmark.password", "romm.password", "romm.igdb_client_id", "romm.igdb_client_secret",
}


def _get_nested(data: dict, dotted_key: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    keys = dotted_key.split(".")
    val = data
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return None
    return val


def _set_nested(data: dict, keys: list[str], value: Any) -> None:
    """Set a value in a nested dict."""
    for k in keys[:-1]:
        data = data.setdefault(k, {})
    data[keys[-1]] = value


def _lines_to_list(text: str) -> list[str]:
    """Convert newline-separated text to a list, stripping empty lines."""
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def load_config_for_form(config_path: Path) -> dict:
    """Read raw YAML from disk (no env var substitution) and mask sensitive fields."""
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    # Ensure all expected sections exist with defaults
    data.setdefault("irc", {})
    data["irc"].setdefault("server", "")
    data["irc"].setdefault("port", 6697)
    data["irc"].setdefault("ssl", False)
    data["irc"].setdefault("nickname", "")
    data["irc"].setdefault("channels", [])
    data["irc"].setdefault("command_prefix", "!")
    data.setdefault("auth", {})
    data["auth"].setdefault("admins", [])
    data["auth"].setdefault("users", [])
    data["auth"].setdefault("default_role", "none")
    data.setdefault("overseerr", {})
    data["overseerr"].setdefault("url", "")
    data["overseerr"].setdefault("api_key", "")
    data.setdefault("lidarr", {})
    data["lidarr"].setdefault("url", "")
    data["lidarr"].setdefault("api_key", "")
    data["lidarr"].setdefault("quality_profile_id", 1)
    data["lidarr"].setdefault("metadata_profile_id", 1)
    data["lidarr"].setdefault("root_folder_path", "/music")
    data.setdefault("plex", {})
    data["plex"].setdefault("url", "")
    data["plex"].setdefault("token", "")
    data["plex"].setdefault("announce_channel", "")
    data["plex"].setdefault("announce_interval", 300)
    data.setdefault("tautulli", {})
    data["tautulli"].setdefault("url", "")
    data["tautulli"].setdefault("api_key", "")
    data.setdefault("shelfmark", {})
    data["shelfmark"].setdefault("url", "")
    data["shelfmark"].setdefault("username", "")
    data["shelfmark"].setdefault("password", "")
    data.setdefault("romm", {})
    data["romm"].setdefault("url", "")
    data["romm"].setdefault("username", "")
    data["romm"].setdefault("password", "")
    data["romm"].setdefault("domain", "")
    data["romm"].setdefault("igdb_client_id", "")
    data["romm"].setdefault("igdb_client_secret", "")
    data["romm"].setdefault("notifications", {})
    data["romm"]["notifications"].setdefault("enabled", False)
    data["romm"]["notifications"].setdefault("channel", "")
    data["romm"]["notifications"].setdefault("interval", 300)
    data.setdefault("plugins", {})
    data["plugins"].setdefault("enabled", [])
    data.setdefault("database", {})
    data["database"].setdefault("path", "/data/bot.db")
    data.setdefault("session", {})
    data["session"].setdefault("timeout_seconds", 300)
    data.setdefault("formatting", {})
    data["formatting"].setdefault("irc_colors", True)
    data.setdefault("web", {})
    data["web"].setdefault("port", 9090)

    # Mask sensitive values
    for field in SENSITIVE_FIELDS:
        keys = field.split(".")
        current_val = _get_nested(data, field)
        if current_val and str(current_val).strip():
            _set_nested(data, keys, MASK)

    return data


def validate_config(form: dict) -> list[str]:
    """Validate form data. Returns list of error strings (empty if valid)."""
    errors = []

    # IRC validation
    server = form.get("irc.server", "").strip()
    if not server:
        errors.append("IRC server is required.")

    try:
        port = int(form.get("irc.port", 0))
        if port < 1 or port > 65535:
            errors.append("IRC port must be between 1 and 65535.")
    except (ValueError, TypeError):
        errors.append("IRC port must be a number.")

    nickname = form.get("irc.nickname", "").strip()
    if not nickname:
        errors.append("IRC nickname is required.")
    elif len(nickname) > 16:
        errors.append("IRC nickname must be 16 characters or fewer.")

    channels_text = form.get("irc.channels", "").strip()
    if not channels_text:
        errors.append("At least one IRC channel is required.")
    else:
        for ch in _lines_to_list(channels_text):
            if not ch.startswith("#") and not ch.startswith("&"):
                errors.append(f"Channel '{ch}' must start with # or &.")

    prefix = form.get("irc.command_prefix", "").strip()
    if not prefix:
        errors.append("Command prefix is required.")
    elif len(prefix) > 1:
        errors.append("Command prefix must be a single character.")

    # Auth validation
    default_role = form.get("auth.default_role", "")
    if default_role not in ("none", "user", "admin"):
        errors.append("Default role must be 'none', 'user', or 'admin'.")

    # Plugin validation
    if hasattr(form, "getall"):
        try:
            enabled_plugins = form.getall("plugins.enabled")
        except KeyError:
            enabled_plugins = []
    else:
        enabled_plugins = form.get("plugins.enabled", [])
    if isinstance(enabled_plugins, str):
        enabled_plugins = [enabled_plugins]

    if "overseerr" in enabled_plugins:
        overseerr_url = form.get("overseerr.url", "").strip()
        if not overseerr_url:
            errors.append("Overseerr URL is required when the plugin is enabled.")

    if "lidarr" in enabled_plugins:
        lidarr_url = form.get("lidarr.url", "").strip()
        if not lidarr_url:
            errors.append("Lidarr URL is required when the plugin is enabled.")

    if "plex" in enabled_plugins:
        plex_url = form.get("plex.url", "").strip()
        if not plex_url:
            errors.append("Plex URL is required when the plugin is enabled.")

    if "shelfmark" in enabled_plugins:
        shelfmark_url = form.get("shelfmark.url", "").strip()
        if not shelfmark_url:
            errors.append("Shelfmark URL is required when the plugin is enabled.")
        shelfmark_username = form.get("shelfmark.username", "").strip()
        if not shelfmark_username:
            errors.append("Shelfmark username is required when the plugin is enabled.")

    if "romm" in enabled_plugins:
        romm_url = form.get("romm.url", "").strip()
        if not romm_url:
            errors.append("RomM URL is required when the plugin is enabled.")

    # Session validation
    try:
        timeout = int(form.get("session.timeout_seconds", 0))
        if timeout < 30:
            errors.append("Session timeout must be at least 30 seconds.")
    except (ValueError, TypeError):
        errors.append("Session timeout must be a number.")

    # Web port validation
    try:
        web_port = int(form.get("web.port", 0))
        if web_port < 1024 or web_port > 65535:
            errors.append("Web UI port must be between 1024 and 65535.")
    except (ValueError, TypeError):
        errors.append("Web UI port must be a number.")

    return errors


def build_config_dict(form: dict, current: dict) -> dict:
    """Build a config dict from form data, preserving masked sensitive values."""
    config = {}

    # IRC section
    config["irc"] = {
        "server": form.get("irc.server", "").strip(),
        "port": int(form.get("irc.port", 6697)),
        "ssl": "irc.ssl" in form,
        "nickname": form.get("irc.nickname", "").strip(),
        "channels": _lines_to_list(form.get("irc.channels", "")),
        "command_prefix": form.get("irc.command_prefix", "!").strip(),
    }

    # Auth section
    config["auth"] = {
        "admins": _lines_to_list(form.get("auth.admins", "")),
        "users": _lines_to_list(form.get("auth.users", "")),
        "default_role": form.get("auth.default_role", "none"),
    }

    # Overseerr section
    api_key_value = form.get("overseerr.api_key", "")
    if api_key_value == MASK:
        api_key_value = _get_nested(current, "overseerr.api_key") or ""
    config["overseerr"] = {
        "url": form.get("overseerr.url", "").strip(),
        "api_key": api_key_value,
    }

    # Lidarr section
    lidarr_api_key = form.get("lidarr.api_key", "")
    if lidarr_api_key == MASK:
        lidarr_api_key = _get_nested(current, "lidarr.api_key") or ""
    config["lidarr"] = {
        "url": form.get("lidarr.url", "").strip(),
        "api_key": lidarr_api_key,
        "quality_profile_id": int(form.get("lidarr.quality_profile_id", 1)),
        "metadata_profile_id": int(form.get("lidarr.metadata_profile_id", 1)),
        "root_folder_path": form.get("lidarr.root_folder_path", "/music").strip(),
    }

    # Plex section
    plex_token = form.get("plex.token", "")
    if plex_token == MASK:
        plex_token = _get_nested(current, "plex.token") or ""
    config["plex"] = {
        "url": form.get("plex.url", "").strip(),
        "token": plex_token,
        "announce_channel": form.get("plex.announce_channel", "").strip(),
        "announce_interval": int(form.get("plex.announce_interval", 300)),
    }

    # Tautulli section (optional)
    tautulli_key = form.get("tautulli.api_key", "")
    if tautulli_key == MASK:
        tautulli_key = _get_nested(current, "tautulli.api_key") or ""
    tautulli_url = form.get("tautulli.url", "").strip()
    if tautulli_url:
        config["tautulli"] = {
            "url": tautulli_url,
            "api_key": tautulli_key,
        }

    # Shelfmark section
    shelfmark_password = form.get("shelfmark.password", "")
    if shelfmark_password == MASK:
        shelfmark_password = _get_nested(current, "shelfmark.password") or ""
    config["shelfmark"] = {
        "url": form.get("shelfmark.url", "").strip(),
        "username": form.get("shelfmark.username", "").strip(),
        "password": shelfmark_password,
    }

    # RomM section
    romm_password = form.get("romm.password", "")
    if romm_password == MASK:
        romm_password = _get_nested(current, "romm.password") or ""
    romm_igdb_id = form.get("romm.igdb_client_id", "")
    if romm_igdb_id == MASK:
        romm_igdb_id = _get_nested(current, "romm.igdb_client_id") or ""
    romm_igdb_secret = form.get("romm.igdb_client_secret", "")
    if romm_igdb_secret == MASK:
        romm_igdb_secret = _get_nested(current, "romm.igdb_client_secret") or ""
    config["romm"] = {
        "url": form.get("romm.url", "").strip(),
        "username": form.get("romm.username", "").strip(),
        "password": romm_password,
        "domain": form.get("romm.domain", "").strip(),
        "igdb_client_id": romm_igdb_id,
        "igdb_client_secret": romm_igdb_secret,
        "notifications": {
            "enabled": "romm.notifications.enabled" in form,
            "channel": form.get("romm.notifications.channel", "").strip(),
            "interval": int(form.get("romm.notifications.interval", 300)),
        },
    }

    # Plugins section
    if hasattr(form, "getall"):
        try:
            enabled = form.getall("plugins.enabled")
        except KeyError:
            enabled = []
    else:
        enabled = form.get("plugins.enabled", [])
    if isinstance(enabled, str):
        enabled = [enabled]
    config["plugins"] = {"enabled": enabled or []}

    # Database section
    config["database"] = {"path": form.get("database.path", "/data/bot.db").strip()}

    # Session section
    config["session"] = {"timeout_seconds": int(form.get("session.timeout_seconds", 300))}

    # Formatting section
    config["formatting"] = {"irc_colors": "formatting.irc_colors" in form}

    # Web section
    config["web"] = {"port": int(form.get("web.port", 9090))}

    return config


def save_config(form: dict, config_path: Path) -> None:
    """Validate, build, and atomically write config to disk."""
    with open(config_path) as f:
        current = yaml.safe_load(f) or {}

    new_config = build_config_dict(form, current)

    # Atomic write
    tmp_path = config_path.with_suffix(".yaml.tmp")
    with open(tmp_path, "w") as f:
        yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, config_path)

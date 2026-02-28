import os
import tempfile
from pathlib import Path

import pytest
import yaml

from bot.web.config_form import (
    MASK,
    load_config_for_form,
    validate_config,
    build_config_dict,
    save_config,
    _lines_to_list,
)

SAMPLE_YAML = """\
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
    - "*!*@admin.host"
  users:
    - "*!*@*.trusted"
  default_role: "none"
overseerr:
  url: "http://overseerr:5055"
  api_key: "real-secret-key"
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
"""


def write_config(tmp_path: Path, content: str = SAMPLE_YAML) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


class TestLoadConfigForForm:
    def test_loads_yaml(self, tmp_path):
        p = write_config(tmp_path)
        data = load_config_for_form(p)
        assert data["irc"]["server"] == "irc.example.com"
        assert data["irc"]["port"] == 6697

    def test_masks_api_key(self, tmp_path):
        p = write_config(tmp_path)
        data = load_config_for_form(p)
        assert data["overseerr"]["api_key"] == MASK

    def test_empty_api_key_not_masked(self, tmp_path):
        content = SAMPLE_YAML.replace('api_key: "real-secret-key"', 'api_key: ""')
        p = write_config(tmp_path, content)
        data = load_config_for_form(p)
        assert data["overseerr"]["api_key"] == ""

    def test_does_not_substitute_env_vars(self, tmp_path):
        content = SAMPLE_YAML.replace('"real-secret-key"', '"${SOME_VAR}"')
        os.environ["SOME_VAR"] = "resolved"
        p = write_config(tmp_path, content)
        data = load_config_for_form(p)
        # Should show raw ${SOME_VAR} masked, not "resolved"
        assert data["overseerr"]["api_key"] == MASK
        del os.environ["SOME_VAR"]

    def test_defaults_for_missing_sections(self, tmp_path):
        p = write_config(tmp_path, "irc:\n  server: test\n")
        data = load_config_for_form(p)
        assert data["auth"]["default_role"] == "none"
        assert data["web"]["port"] == 9090
        assert data["plugins"]["enabled"] == []


class TestValidation:
    def _valid_form(self):
        return {
            "irc.server": "irc.example.com",
            "irc.port": "6697",
            "irc.nickname": "TestBot",
            "irc.channels": "#test",
            "irc.command_prefix": "!",
            "auth.default_role": "none",
            "overseerr.url": "http://localhost:5055",
            "session.timeout_seconds": "300",
            "web.port": "9090",
        }

    def test_valid_config_no_errors(self):
        errors = validate_config(self._valid_form())
        assert errors == []

    def test_empty_server_returns_error(self):
        form = self._valid_form()
        form["irc.server"] = ""
        errors = validate_config(form)
        assert any("server" in e.lower() for e in errors)

    def test_port_out_of_range(self):
        form = self._valid_form()
        form["irc.port"] = "99999"
        errors = validate_config(form)
        assert any("port" in e.lower() for e in errors)

    def test_port_not_a_number(self):
        form = self._valid_form()
        form["irc.port"] = "abc"
        errors = validate_config(form)
        assert any("port" in e.lower() for e in errors)

    def test_nickname_too_long(self):
        form = self._valid_form()
        form["irc.nickname"] = "a" * 17
        errors = validate_config(form)
        assert any("nickname" in e.lower() for e in errors)

    def test_channel_without_hash(self):
        form = self._valid_form()
        form["irc.channels"] = "nochannel"
        errors = validate_config(form)
        assert any("channel" in e.lower() for e in errors)

    def test_prefix_too_long(self):
        form = self._valid_form()
        form["irc.command_prefix"] = "!!"
        errors = validate_config(form)
        assert any("prefix" in e.lower() for e in errors)

    def test_invalid_default_role(self):
        form = self._valid_form()
        form["auth.default_role"] = "superadmin"
        errors = validate_config(form)
        assert any("role" in e.lower() for e in errors)

    def test_overseerr_url_required_when_enabled(self):
        form = self._valid_form()
        form["plugins.enabled"] = "overseerr"
        form["overseerr.url"] = ""
        errors = validate_config(form)
        assert any("overseerr" in e.lower() for e in errors)

    def test_session_timeout_too_low(self):
        form = self._valid_form()
        form["session.timeout_seconds"] = "10"
        errors = validate_config(form)
        assert any("timeout" in e.lower() for e in errors)

    def test_web_port_too_low(self):
        form = self._valid_form()
        form["web.port"] = "80"
        errors = validate_config(form)
        assert any("port" in e.lower() for e in errors)


class TestBuildConfigDict:
    def test_builds_complete_config(self):
        form = {
            "irc.server": "irc.test.com",
            "irc.port": "6667",
            "irc.ssl": "on",
            "irc.nickname": "Bot",
            "irc.channels": "#a\n#b",
            "irc.command_prefix": ".",
            "auth.admins": "*!*@admin\n*!*@mod",
            "auth.users": "*!*@user",
            "auth.default_role": "user",
            "overseerr.url": "http://seerr:5055",
            "overseerr.api_key": "new-key",
            "plugins.enabled": "overseerr",
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "600",
            "formatting.irc_colors": "on",
            "web.port": "8080",
        }
        result = build_config_dict(form, {})
        assert result["irc"]["server"] == "irc.test.com"
        assert result["irc"]["port"] == 6667
        assert result["irc"]["ssl"] is True
        assert result["irc"]["channels"] == ["#a", "#b"]
        assert result["auth"]["admins"] == ["*!*@admin", "*!*@mod"]
        assert result["overseerr"]["api_key"] == "new-key"
        assert result["formatting"]["irc_colors"] is True

    def test_preserves_masked_api_key(self):
        form = {
            "irc.server": "test", "irc.port": "6697", "irc.nickname": "Bot",
            "irc.channels": "#a", "irc.command_prefix": "!",
            "auth.admins": "", "auth.users": "", "auth.default_role": "none",
            "overseerr.url": "http://seerr:5055",
            "overseerr.api_key": MASK,
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "300",
            "web.port": "9090",
        }
        current = {"overseerr": {"api_key": "original-secret"}}
        result = build_config_dict(form, current)
        assert result["overseerr"]["api_key"] == "original-secret"

    def test_checkbox_false_when_absent(self):
        form = {
            "irc.server": "test", "irc.port": "6697", "irc.nickname": "Bot",
            "irc.channels": "#a", "irc.command_prefix": "!",
            "auth.admins": "", "auth.users": "", "auth.default_role": "none",
            "overseerr.url": "", "overseerr.api_key": "",
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "300",
            "web.port": "9090",
        }
        # irc.ssl and formatting.irc_colors not in form = False
        result = build_config_dict(form, {})
        assert result["irc"]["ssl"] is False
        assert result["formatting"]["irc_colors"] is False

    def test_empty_lines_stripped(self):
        form = {
            "irc.server": "test", "irc.port": "6697", "irc.nickname": "Bot",
            "irc.channels": "#a\n\n#b\n", "irc.command_prefix": "!",
            "auth.admins": "", "auth.users": "", "auth.default_role": "none",
            "overseerr.url": "", "overseerr.api_key": "",
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "300",
            "web.port": "9090",
        }
        result = build_config_dict(form, {})
        assert result["irc"]["channels"] == ["#a", "#b"]


class TestSaveConfig:
    def test_save_writes_valid_yaml(self, tmp_path):
        p = write_config(tmp_path)
        form = {
            "irc.server": "new.server.com", "irc.port": "6667",
            "irc.ssl": "on", "irc.nickname": "NewBot",
            "irc.channels": "#new", "irc.command_prefix": ".",
            "auth.admins": "*!*@admin", "auth.users": "", "auth.default_role": "user",
            "overseerr.url": "http://new:5055", "overseerr.api_key": MASK,
            "plugins.enabled": "overseerr",
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "600",
            "formatting.irc_colors": "on",
            "web.port": "8080",
        }
        save_config(form, p)
        # Read back and verify
        with open(p) as f:
            saved = yaml.safe_load(f)
        assert saved["irc"]["server"] == "new.server.com"
        assert saved["irc"]["port"] == 6667
        # Masked key should be preserved from original
        assert saved["overseerr"]["api_key"] == "real-secret-key"

    def test_save_atomic_no_tmp_leftover(self, tmp_path):
        p = write_config(tmp_path)
        form = {
            "irc.server": "test", "irc.port": "6697", "irc.nickname": "Bot",
            "irc.channels": "#a", "irc.command_prefix": "!",
            "auth.admins": "", "auth.users": "", "auth.default_role": "none",
            "overseerr.url": "", "overseerr.api_key": "",
            "database.path": "/data/bot.db",
            "session.timeout_seconds": "300",
            "web.port": "9090",
        }
        save_config(form, p)
        # No .tmp file should remain
        assert not (tmp_path / "config.yaml.tmp").exists()


class TestLinesToList:
    def test_basic(self):
        assert _lines_to_list("#a\n#b\n#c") == ["#a", "#b", "#c"]

    def test_empty_lines_stripped(self):
        assert _lines_to_list("#a\n\n#b\n") == ["#a", "#b"]

    def test_whitespace_stripped(self):
        assert _lines_to_list("  #a  \n  #b  ") == ["#a", "#b"]

    def test_empty_string(self):
        assert _lines_to_list("") == []

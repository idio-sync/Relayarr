import os
import tempfile
from pathlib import Path
from bot.core.config import Config


def make_config_file(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


BASIC_YAML = """
irc:
  server: "irc.example.com"
  port: 6697
  ssl: true
  nickname: "MediaBot"
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
"""


class TestConfigLoading:
    def test_load_from_yaml(self):
        path = make_config_file(BASIC_YAML)
        config = Config.load(path)
        assert config["irc"]["server"] == "irc.example.com"
        assert config["irc"]["port"] == 6697
        assert config["irc"]["ssl"] is True
        assert config["irc"]["channels"] == ["#requests"]
        os.unlink(path)

    def test_env_var_substitution(self):
        os.environ["OVERSEERR_API_KEY"] = "test-key-123"
        path = make_config_file(BASIC_YAML)
        config = Config.load(path)
        assert config["overseerr"]["api_key"] == "test-key-123"
        os.unlink(path)
        del os.environ["OVERSEERR_API_KEY"]

    def test_env_var_override_flat(self):
        os.environ["IRC__NICKNAME"] = "OverrideBot"
        path = make_config_file(BASIC_YAML)
        config = Config.load(path)
        assert config["irc"]["nickname"] == "OverrideBot"
        os.unlink(path)
        del os.environ["IRC__NICKNAME"]

    def test_get_nested(self):
        path = make_config_file(BASIC_YAML)
        config = Config.load(path)
        assert config.get("irc.server") == "irc.example.com"
        assert config.get("irc.nonexistent", "default") == "default"
        os.unlink(path)

    def test_missing_file_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            Config.load(Path("/nonexistent/config.yaml"))

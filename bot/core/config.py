import os
import re
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Load YAML config with env var substitution and override support."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            raw = f.read()

        # Substitute ${VAR} with environment variables
        raw = re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            raw,
        )

        data = yaml.safe_load(raw)

        # Apply environment variable overrides (IRC__NICKNAME -> irc.nickname)
        for key, value in os.environ.items():
            parts = key.split("__")
            if len(parts) >= 2:
                section = parts[0].lower()
                option = "__".join(parts[1:]).lower()
                if section in data and isinstance(data[section], dict):
                    existing = data[section].get(option)
                    if isinstance(existing, bool):
                        value = value.lower() in ("true", "1", "yes")
                    elif isinstance(existing, int):
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    data[section][option] = value

        return cls(data)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Get a value using dot notation: 'irc.server'."""
        keys = dotted_key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

"""Persisted preferences for Lashon Studio.

Preferences live in ``$XDG_CONFIG_HOME/lashon/studio.json`` (or
``~/.config/lashon/studio.json``). ``LASHON_CONFIG_DIR`` overrides the
directory, which keeps tests off the user's real configuration.

Unknown keys are preserved, so a newer Studio can read an older file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

FILENAME = "studio.json"


def config_dir() -> Path:
    """Directory that holds Studio preferences."""
    override = os.environ.get("LASHON_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "lashon"


def settings_path() -> Path:
    """Full path of the preferences file."""
    return config_dir() / FILENAME


def load() -> Dict[str, Any]:
    """Read the preferences file; an unreadable file reads as empty."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(**values: Any) -> Dict[str, Any]:
    """Merge ``values`` into the preferences file and return the result."""
    data = {**load(), **values}
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError:  # pragma: no cover - read-only or missing home
        return data
    return data


def get(key: str, default: Any = None) -> Any:
    """A single preference."""
    return load().get(key, default)

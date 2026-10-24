"""``lashon config get|set`` — inspect and edit nested config values."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lashon.config import LanguageConfig
from lashon.tooling.commands.common import CONFIG_LOAD_ERRORS


def _walk(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(key)
        current = current[part]
    return current


def _assign(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _parse_value(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def cmd_config_get(args) -> int:
    """Print a nested configuration value."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1
    try:
        config = LanguageConfig.load(path)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

    try:
        value = _walk(config.to_dict(), args.key)
    except KeyError:
        print(f"Error: Key not found: {args.key}", file=sys.stderr)
        return 1

    if args.json or not isinstance(value, str):
        json.dump(value, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(value)
    return 0


def cmd_config_set(args) -> int:
    """Set a nested configuration value and save the file."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1
    try:
        config = LanguageConfig.load(path)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

    data = config.to_dict()
    before = repr(_walk(data, args.key)) if _has_key(data, args.key) else None
    _assign(data, args.key, _parse_value(args.value))
    try:
        updated = LanguageConfig.from_dict(data)
    except (ValueError, TypeError) as error:
        print(f"Error: Invalid value: {error}", file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else path
    updated.save(output)
    after = _walk(updated.to_dict(), args.key)
    print(f"✓ {args.key}: {before} -> {after!r}")
    print(f"Saved: {output}")
    return 0


def _has_key(data: dict[str, Any], key: str) -> bool:
    try:
        _walk(data, key)
    except KeyError:
        return False
    return True


def cmd_config(args) -> int:
    """Dispatch ``config get`` and ``config set``."""
    if args.config_command == "get":
        return cmd_config_get(args)
    if args.config_command == "set":
        return cmd_config_set(args)
    print("Error: expected 'config get' or 'config set'", file=sys.stderr)
    return 2

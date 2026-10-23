"""Shared helpers for CLI commands that need a compiled grammar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

try:
    from yaml import safe_load
except ImportError:  # pragma: no cover - PyYAML is a runtime dependency
    safe_load = None  # type: ignore[assignment]


def load_raw_config(config_path: str | Path) -> dict[str, Any]:
    """Load a language configuration file as a raw mapping."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if safe_load is None:
            raise ImportError(
                "PyYAML is required to read YAML configuration files"
            )
        try:
            data = safe_load(content) or {}
        except Exception as error:  # yaml.YAMLError without a hard dependency
            raise ValueError(
                f"Invalid YAML in {path}: {error}"
            ) from error
    else:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON in {path}: {error}"
            ) from error

    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping")
    return data


def load_grammar(
    config_path: Optional[str] = None,
    grammar_path: Optional[str] = None,
    require_rules: bool = True,
):
    """Build a ``Grammar`` from a PEG file or a config's ``grammar`` section.

    ``grammar_path`` wins when both are provided. With neither, the default
    grammar is returned unless ``require_rules`` is true.
    """
    from parsercraft.parser.grammar import GrammarParser, grammar_from_config

    if grammar_path:
        path = Path(grammar_path)
        if not path.exists():
            raise FileNotFoundError(f"Grammar file not found: {path}")
        return GrammarParser().parse(path.read_text(encoding="utf-8"))

    if not config_path:
        if require_rules:
            raise ValueError(
                "A grammar is required: pass --grammar or --config"
            )
        return grammar_from_config({})

    data = load_raw_config(config_path)
    grammar_data = data.get("grammar") or {}
    if not grammar_data.get("rules"):
        if require_rules:
            raise ValueError(
                f"Configuration {config_path} has no 'grammar.rules' section; "
                "pass --grammar or add a PEG grammar"
            )
        return grammar_from_config({})
    return grammar_from_config(data)

"""Optional native PEG engine.

The reference engine is pure Python. This module loads an experimental Rust
implementation (``native/lashon-native``) that implements the same
algorithm and returns the same JSON AST, so the two can be swapped and
compared.

Usage::

    from lashon.parser import PEGInterpreter
    PEGInterpreter(grammar, backend="auto")     # native when it is built
    PEGInterpreter(grammar, backend="native")   # require it

Build it with ``scripts/build_native.sh``. Nothing in the package depends on
the extension being present: :func:`available` returns ``False`` and callers
fall back to Python.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Optional

from lashon.ast import SourceAST

__all__ = [
    "NativeParseError",
    "NativeUnsupported",
    "available",
    "backend",
    "parse",
    "supports",
    "version",
]

_MODULE_NAME = "lashon_native"
_ENV_VAR = "LASHON_NATIVE_LIB"
_state: dict[str, Any] = {"checked": False, "module": None}

#: PEG node kinds the native engine implements.
_SUPPORTED_KINDS = {
    "seq",
    "choice",
    "star",
    "plus",
    "opt",
    "and",
    "not",
    "lit",
    "cls",
    "any",
    "ref",
    "tok",
}

#: The native scanner understands ``//`` line comments and ``/* */`` blocks.
_SUPPORTED_COMMENT_PREFIXES = ("//", "/\\*")


class NativeParseError(SyntaxError):
    """The native engine rejected the input."""


class NativeUnsupported(RuntimeError):
    """The grammar uses a feature the native engine does not implement."""


def _candidates() -> list[Path]:
    package_dir = Path(__file__).resolve().parent
    found = sorted(package_dir.glob(f"{_MODULE_NAME}*.so"))
    found += sorted(package_dir.glob(f"{_MODULE_NAME}*.pyd"))
    explicit = os.environ.get(_ENV_VAR)
    if explicit:
        found.insert(0, Path(explicit).expanduser())
    repo_root = package_dir.parents[2]
    found.append(
        repo_root / "native" / "lashon-native" / "target" / "release"
        / f"lib{_MODULE_NAME}.so"
    )
    return [path for path in found if path.is_file()]


def _load():
    if _state["checked"]:
        return _state["module"]
    _state["checked"] = True
    for path in _candidates():
        try:
            spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except (ImportError, OSError):  # pragma: no cover - platform dependent
            continue
        _state["module"] = module
        return module
    return None


def available() -> bool:
    """Return ``True`` when the native extension can be loaded."""
    return _load() is not None


def backend() -> str:
    """Return ``"native"`` or ``"python"`` for the engine that would be used."""
    return "native" if available() else "python"


def version() -> Optional[str]:
    module = _load()
    return module.version() if module is not None else None


#: PEGNodeType names → the compact kinds the Rust engine understands.
_KIND_MAP = {
    "SEQUENCE": "seq",
    "ORDERED_CHOICE": "choice",
    "ZERO_OR_MORE": "star",
    "ONE_OR_MORE": "plus",
    "OPTIONAL": "opt",
    "AND_PREDICATE": "and",
    "NOT_PREDICATE": "not",
    "LITERAL": "lit",
    "CHAR_CLASS": "cls",
    "ANY_CHAR": "any",
    "RULE_REF": "ref",
    "TOKEN_REF": "tok",
}


def _node_to_json(node: Any) -> dict[str, Any]:
    """Serialize a :class:`PEGNode` into the native engine's JSON shape."""
    kind = _KIND_MAP.get(node.node_type.name)
    if kind is None:
        raise NativeUnsupported(
            f"pattern kind '{node.node_type.name}' is not supported"
        )
    entry: dict[str, Any] = {"k": kind}
    if kind in {"lit", "cls", "ref", "tok"}:
        entry["v"] = node.value
    elif kind in {"seq", "choice"}:
        entry["c"] = [_node_to_json(child) for child in node.children]
    elif kind in {"star", "plus", "opt", "and", "not"}:
        entry["c"] = [_node_to_json(node.children[0])]
    else:
        raise NativeUnsupported(f"pattern kind '{kind}' is not supported")
    return entry


def grammar_to_json(grammar: Any) -> str:
    """Serialize a grammar for the native engine.

    Raises:
        NativeUnsupported: when the grammar uses an unimplemented feature.
    """
    comments = list(getattr(grammar, "comment_patterns", []) or [])
    unsupported = [
        pattern
        for pattern in comments
        if not pattern.startswith(_SUPPORTED_COMMENT_PREFIXES)
    ]
    if unsupported:
        raise NativeUnsupported(f"comment patterns not supported: {unsupported}")

    rules = []
    for rule in grammar.rules.values():
        rules.append(
            {
                "name": rule.name,
                "node_type": rule.node_type,
                "fragment": bool(rule.is_fragment),
                "pattern": _node_to_json(rule.pattern),
            }
        )
    return json.dumps(
        {
            "start": grammar.start_rule,
            "skip_ws": bool(grammar.skip_whitespace),
            "comments": comments,
            "rules": rules,
        }
    )


def supports(grammar: Any) -> bool:
    """Return ``True`` when the native engine can handle ``grammar``."""
    try:
        grammar_to_json(grammar)
    except NativeUnsupported:
        return False
    return True


def _from_json(data: dict[str, Any]) -> SourceAST:
    node = SourceAST(
        node_type=data.get("type", ""),
        value=data.get("value"),
        line=int(data.get("line") or 0),
        column=int(data.get("column") or 0),
    )
    node.children = [_from_json(child) for child in data.get("children") or []]
    return node


def parse(grammar: Any, source: str) -> SourceAST:
    """Parse ``source`` with the native engine.

    Raises:
        NativeUnsupported: the extension is missing or the grammar is out of
            scope — callers should fall back to the Python engine.
        NativeParseError: the input does not match the grammar.
    """
    module = _load()
    if module is None:
        raise NativeUnsupported("native engine is not built")

    grammar_json = grammar_to_json(grammar)
    payload = json.loads(module.parse(grammar_json, source))
    if not payload.get("ok"):
        raise NativeParseError(payload.get("error") or "parse error")
    return _from_json(payload["ast"])

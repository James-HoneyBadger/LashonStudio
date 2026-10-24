"""Lightweight PEG grammar text intelligence.

Powers hover, go-to-definition, references, rename, and completion when the
edited document is a Lashon grammar. It works on the raw text so it can
be used before (or without) a grammar being parseable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_DEFINITION = re.compile(r"^(?P<indent>\s*)(?P<name>[A-Za-z_][\w-]*)\s*<-")
_IDENTIFIER = re.compile(r"[A-Za-z_][\w-]*")

BUILTIN_TOKENS: Tuple[str, ...] = ("IDENT", "NUMBER", "STRING", "NEWLINE", "EOF")


@dataclass(frozen=True)
class RuleLocation:
    """Where a rule is defined in the grammar text."""

    name: str
    line: int  # 1-based
    column: int  # 1-based, points at the rule name
    pattern: str

    @property
    def end_column(self) -> int:
        return self.column + len(self.name)


def _strip_comment(line: str) -> str:
    """Remove a trailing ``//`` comment that is not inside a literal."""
    quote: Optional[str] = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            continue
        if char == "/" and line[index:index + 2] == "//":
            return line[:index]
    return line


class GrammarIndex:
    """Index of rule definitions and references in PEG text."""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.splitlines()
        self.rules: Dict[str, RuleLocation] = {}
        self._index_rules()

    def _index_rules(self) -> None:
        for number, raw in enumerate(self.lines, start=1):
            line = _strip_comment(raw)
            match = _DEFINITION.match(line)
            if not match:
                continue
            name = match.group("name")
            column = line.index(name) + 1
            pattern = line[match.end():].strip()
            self.rules[name] = RuleLocation(
                name=name, line=number, column=column, pattern=pattern
            )

    # -- queries ---------------------------------------------------------

    def word_at(self, line: int, character: int) -> Optional[str]:
        """Return the identifier under a zero-based LSP position."""
        if not (0 <= line < len(self.lines)):
            return None
        text = _strip_comment(self.lines[line])
        for match in _IDENTIFIER.finditer(text):
            if match.start() <= character < match.end():
                return match.group(0)
        return None

    def definition(self, name: str) -> Optional[RuleLocation]:
        return self.rules.get(name)

    def references(self, name: str) -> List[Tuple[int, int]]:
        """Return 1-based (line, column) of every occurrence of ``name``."""
        pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        found: List[Tuple[int, int]] = []
        for number, raw in enumerate(self.lines, start=1):
            for match in pattern.finditer(_strip_comment(raw)):
                found.append((number, match.start() + 1))
        return found

    def symbols(self) -> List[dict]:
        """Return LSP ``DocumentSymbol`` entries for every rule."""
        return [
            {
                "name": location.name,
                "kind": 12,  # Function
                "range": _range(location.line, location.column, len(location.name)),
                "selectionRange": _range(
                    location.line, location.column, len(location.name)
                ),
                "detail": location.pattern,
            }
            for location in self.rules.values()
        ]

    def hover(self, name: str) -> Optional[str]:
        location = self.rules.get(name)
        if location is None:
            if name in BUILTIN_TOKENS:
                return f"`{name}` — built-in token supplied by the interpreter"
            return None
        return (
            f"**{name}**\n\n"
            f"```\n{name} <- {location.pattern}\n```\n\n"
            f"Defined on line {location.line}."
        )

    def completion_items(self, prefix: str = "") -> List[str]:
        names = sorted(self.rules) + list(BUILTIN_TOKENS)
        return [name for name in names if name.startswith(prefix)]

    def rename(self, old: str, new: str) -> str:
        """Return the grammar text with all references renamed."""
        if not new.isidentifier():
            raise ValueError(f"'{new}' is not a valid rule name")
        pattern = re.compile(rf"(?<![\w-]){re.escape(old)}(?![\w-])")
        return "\n".join(
            pattern.sub(new, line) for line in self.lines
        ) + ("\n" if self.text.endswith("\n") else "")

    def validation_problems(self) -> List[str]:
        """Report undefined rule references (cheap structural check)."""
        problems: List[str] = []
        for location in self.rules.values():
            body = _strip_comment(location.pattern)
            body = re.sub(r"'(?:[^']*)'|\"(?:[^\"]*)\"", "", body)
            for reference in _IDENTIFIER.findall(body):
                if reference in self.rules or reference in BUILTIN_TOKENS:
                    continue
                if reference in {"true", "false"}:
                    continue
                problems.append(
                    f"line {location.line}: rule '{location.name}' references "
                    f"undefined rule '{reference}'"
                )
        return problems


def _range(line: int, column: int, length: int) -> dict:
    """Build a zero-based LSP range."""
    return {
        "start": {"line": line - 1, "character": column - 1},
        "end": {"line": line - 1, "character": column - 1 + length},
    }

"""Parses PEG text notation into a :class:`~.model.Grammar`."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .model import (
    SUPPORTED_TOKENS,
    Grammar,
    PEGNode,
    PEGNodeType,
)

__all__ = ["GrammarParser"]

# ---------------------------------------------------------------------------

class GrammarParser:
    """Parses PEG grammar notation into a Grammar object.

    Grammar syntax:
        rule <- pattern          # Rule definition
        a b c                    # Sequence
        a / b / c                # Ordered choice
        a*  a+  a?               # Repetition
        &a  !a                   # Predicates
        'literal'  "literal"     # Literal string
        [a-z0-9]                 # Character class
        .                        # Any character
        RULE_NAME                # Rule reference
        @label:pattern           # Named capture
        { action_name }          # Semantic action
    """

    def __init__(self):
        self.pos = 0
        self.text = ""

    def parse(self, grammar_text: str, grammar_name: str = "custom") -> Grammar:
        """Parse a PEG grammar string into a Grammar object."""
        grammar = Grammar(name=grammar_name)
        lines = grammar_text.strip().split("\n")

        rule_lines: List[str] = []
        current_line = ""

        for line in lines:
            stripped = line.strip()
            if (not stripped or stripped.startswith("#")
                    or stripped.startswith("//")):
                continue
            # Continuation lines start with whitespace and don't contain <-
            if current_line and (line[0].isspace() or line[0] == '|') and "<-" not in stripped:
                current_line += " " + stripped
            else:
                if current_line:
                    rule_lines.append(current_line)
                current_line = stripped

        if current_line:
            rule_lines.append(current_line)

        for rule_text in rule_lines:
            name, pattern = self._parse_rule(rule_text)
            if name is None:
                raise ValueError(
                    f"Invalid grammar line (expected 'rule <- pattern'): {rule_text!r}"
                )
            grammar.add_rule(name, pattern)
            if not grammar.start_rule or grammar.start_rule == "program":
                if not grammar.rules or name == "program":
                    grammar.start_rule = name

        # Default start rule to the first defined rule
        if grammar.start_rule not in grammar.rules and grammar.rules:
            grammar.start_rule = next(iter(grammar.rules))

        return grammar

    def _parse_rule(self, text: str) -> Tuple[Optional[str], Optional[PEGNode]]:
        """Parse a single rule definition: name <- pattern"""
        match = re.match(r'(\w+)\s*<-\s*(.*)', text)
        if not match:
            return None, None

        name = match.group(1)
        pattern_text = match.group(2).strip()

        self.pos = 0
        self.text = pattern_text
        pattern = self._parse_choice()
        self._skip_ws()
        if self.pos < len(self.text):
            raise ValueError(
                f"Invalid grammar rule '{name}': unexpected "
                f"{self.text[self.pos:]!r} in pattern {pattern_text!r}"
            )
        return name, pattern

    def _parse_choice(self) -> PEGNode:
        """Parse ordered choice: a / b / c (``|`` is accepted as an alias)."""
        alternatives = [self._parse_sequence()]

        while self._peek_str("/") or self._peek_str("|"):
            separator = "/" if self._peek_str("/") else "|"
            self._consume(separator)
            alternatives.append(self._parse_sequence())

        if len(alternatives) == 1:
            return alternatives[0]
        return PEGNode(PEGNodeType.ORDERED_CHOICE, children=alternatives)

    def _parse_sequence(self) -> PEGNode:
        """Parse sequence: a b c"""
        items = []

        while self.pos < len(self.text):
            self._skip_ws()
            if self.pos >= len(self.text):
                break
            ch = self.text[self.pos]
            if ch in "/)" or (ch == '{' and self._look_ahead_is_action()):
                break

            item = self._parse_suffix()
            if item:
                items.append(item)
            else:
                break

        if len(items) == 0:
            return PEGNode(PEGNodeType.LITERAL, "")
        if len(items) == 1:
            return items[0]
        return PEGNode(PEGNodeType.SEQUENCE, children=items)

    def _parse_suffix(self) -> Optional[PEGNode]:
        """Parse suffix operators: a* a+ a?"""
        node = self._parse_prefix()
        if not node:
            return None

        self._skip_ws()
        if self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == '*':
                self.pos += 1
                return PEGNode(PEGNodeType.ZERO_OR_MORE, children=[node])
            elif ch == '+':
                self.pos += 1
                return PEGNode(PEGNodeType.ONE_OR_MORE, children=[node])
            elif ch == '?':
                self.pos += 1
                return PEGNode(PEGNodeType.OPTIONAL, children=[node])

        return node

    def _parse_prefix(self) -> Optional[PEGNode]:
        """Parse prefix operators: &a  !a  @label:a"""
        self._skip_ws()
        if self.pos >= len(self.text):
            return None

        ch = self.text[self.pos]

        if ch == '&':
            self.pos += 1
            child = self._parse_primary()
            return PEGNode(PEGNodeType.AND_PREDICATE, children=[child]) if child else None

        if ch == '!':
            self.pos += 1
            child = self._parse_primary()
            return PEGNode(PEGNodeType.NOT_PREDICATE, children=[child]) if child else None

        # Named capture: @label:pattern
        if ch == '@':
            self.pos += 1
            label_match = re.match(r'(\w+):', self.text[self.pos:])
            if label_match:
                label = label_match.group(1)
                self.pos += label_match.end()
                child = self._parse_primary()
                if child:
                    child.label = label
                return child

        return self._parse_primary()

    def _parse_primary(self) -> Optional[PEGNode]:
        """Parse primary expressions: literals, char classes, rule refs, groups."""
        self._skip_ws()
        if self.pos >= len(self.text):
            return None

        ch = self.text[self.pos]

        # Literal string
        if ch in "'\"":
            return self._parse_literal()

        # Character class [a-z]
        if ch == '[':
            return self._parse_char_class()

        # Any character
        if ch == '.':
            self.pos += 1
            return PEGNode(PEGNodeType.ANY_CHAR)

        # Grouped expression (...)
        if ch == '(':
            self.pos += 1
            node = self._parse_choice()
            self._skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] != ')':
                raise ValueError(
                    f"Unclosed group in grammar pattern: {self.text!r}"
                )
            self.pos += 1
            return node

        # Rule/token reference
        if ch.isalpha() or ch == '_':
            return self._parse_identifier()

        return None

    def _parse_literal(self) -> PEGNode:
        """Parse a quoted string literal."""
        quote = self.text[self.pos]
        self.pos += 1
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] != quote:
            if self.text[self.pos] == '\\':
                self.pos += 1
            self.pos += 1
        if self.pos >= len(self.text):
            raise ValueError(
                f"Unterminated string literal in grammar pattern: {self.text!r}"
            )
        value = self.text[start:self.pos]
        self.pos += 1  # skip closing quote
        return PEGNode(PEGNodeType.LITERAL, value)

    def _parse_char_class(self) -> PEGNode:
        """Parse a character class [a-z0-9_]."""
        self.pos += 1  # skip [
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] != ']':
            if self.text[self.pos] == '\\':
                self.pos += 1
            self.pos += 1
        if self.pos >= len(self.text):
            raise ValueError(
                f"Unterminated character class in grammar pattern: {self.text!r}"
            )
        value = self.text[start:self.pos]
        self.pos += 1  # skip ]
        return PEGNode(PEGNodeType.CHAR_CLASS, value)

    def _parse_identifier(self) -> PEGNode:
        """Parse an identifier (rule reference or built-in token)."""
        start = self.pos
        while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
            self.pos += 1
        name = self.text[start:self.pos]

        # Built-in token types (INDENT/DEDENT are recognised so that
        # validation can report them as unsupported, not as unknown rules)
        if name in SUPPORTED_TOKENS or name in ("INDENT", "DEDENT"):
            return PEGNode(PEGNodeType.TOKEN_REF, name)

        return PEGNode(PEGNodeType.RULE_REF, name)

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in ' \t':
            self.pos += 1

    def _peek_str(self, s: str) -> bool:
        self._skip_ws()
        return self.text[self.pos:self.pos + len(s)] == s if self.pos < len(self.text) else False

    def _consume(self, s: str) -> None:
        self._skip_ws()
        if self.text[self.pos:self.pos + len(s)] == s:
            self.pos += len(s)

    def _look_ahead_is_action(self) -> bool:
        """Check if { starts a semantic action (has matching })."""
        i = self.pos + 1
        while i < len(self.text):
            if self.text[i] == '}':
                return True
            i += 1
        return False



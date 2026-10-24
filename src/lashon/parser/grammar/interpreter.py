"""Packrat PEG interpreter: source text to :class:`~lashon.ast.SourceAST`."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lashon.ast import SourceAST

from .model import (
    SUPPORTED_TOKENS,
    Grammar,
    PEGNode,
    PEGNodeType,
)

__all__ = ["ParseResult", "PEGInterpreter"]

# ---------------------------------------------------------------------------
# PEG Interpreter — executes a Grammar against source text to produce AST
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Result of parsing a grammar rule against source text."""
    success: bool
    pos: int                                    # Position after match
    node: Optional[Any] = None                  # Produced AST node
    children: List[Any] = field(default_factory=list)


@dataclass
class PEGInterpreter:
    """Executes a PEG grammar against source text to produce an AST.

    This is the core of the grammar engine — it takes a Grammar object
    and source code, and produces a SourceAST.
    """

    def __init__(self, grammar: Grammar, backend: str = "python"):
        """Create an interpreter.

        Args:
            grammar: the grammar to interpret.
            backend: ``"python"`` (default, reference engine), ``"native"``
                (require the optional Rust engine) or ``"auto"`` (use it when
                it is built and the grammar is in scope). The
                ``LASHON_PARSER`` environment variable sets the default.
        """
        self.grammar = grammar
        self.backend = backend
        self.source = ""
        self.line_starts: List[int] = []
        self.memo: Dict[Tuple[str, int], ParseResult] = {}  # Packrat memoization
        self.max_pos = 0        # Furthest position reached (for error reporting)
        self.max_rule = ""      # Rule being tried at max_pos
        self._rule_stack: List[str] = []

    def _native_engine(self):
        """Return the native engine module when it should be used."""
        if self.backend == "python":
            return None
        from lashon.parser import native as native_engine

        if not native_engine.available():
            if self.backend == "native":
                raise RuntimeError(
                    "the native parser is not built; run scripts/build_native.sh"
                )
            return None
        if self.backend == "auto" and not native_engine.supports(self.grammar):
            return None
        return native_engine

    def parse(self, source: str) -> SourceAST:
        """Parse source code using the grammar.

        Returns a SourceAST tree, or raises SyntaxError on failure.
        """
        engine = self._native_engine()
        if engine is not None:
            self.source = source
            try:
                return engine.parse(self.grammar, source)
            except engine.NativeUnsupported:
                pass  # grammar feature not covered natively; use Python
        return self._parse_from_rule(self.grammar.start_rule, source)

    def parse_rule(self, rule_name: str, source: str) -> SourceAST:
        """Parse ``source`` as a single instance of ``rule_name``.

        Used by :class:`IncrementalParser` to re-parse only the edited
        region. Raises ``ValueError`` for unknown rules and ``SyntaxError``
        when the text does not match the rule.
        """
        if rule_name not in self.grammar.rules and rule_name not in SUPPORTED_TOKENS:
            raise ValueError(f"Unknown rule '{rule_name}'")
        return self._parse_from_rule(rule_name, source)

    def _parse_from_rule(self, rule_name: str, source: str) -> SourceAST:
        self.source = source
        self.memo.clear()
        self.max_pos = 0
        self.max_rule = rule_name
        self._rule_stack = []
        self._compute_line_starts()
        self._prepare_comment_patterns()

        result = self._match_rule(rule_name, 0)

        if not result.success:
            line, col = self._pos_to_line_col(self.max_pos)
            ctx = self.source[self.max_pos:self.max_pos + 30].split("\n")[0]
            raise SyntaxError(
                f"Parse error at line {line}, column {col} "
                f"(in rule '{self.max_rule}'): unexpected '{ctx}'"
                + self._snippet(line, col)
            )

        # Check we consumed all input (ignoring whitespace and comments)
        trailing_pos = self._skip_ignored(result.pos)
        remaining = self.source[trailing_pos:].strip()
        if remaining:
            line, col = self._pos_to_line_col(trailing_pos)
            raise SyntaxError(
                f"Unexpected input at line {line}, column {col}: "
                f"'{remaining[:30]}'" + self._snippet(line, col)
            )

        return result.node if result.node else SourceAST(rule_name)

    def _snippet(self, line: int, column: int) -> str:
        """Render a source line with a caret for error messages."""
        lines = self.source.splitlines()
        if line < 1 or line > len(lines):
            return ""
        text = lines[line - 1]
        if not text:
            return ""
        caret = " " * max(column - 1, 0) + "^"
        gutter = " " * len(str(line))
        return f"\n  {line} | {text}\n  {gutter} | {caret}"

    def _match_rule(self, rule_name: str, pos: int) -> ParseResult:
        """Match a named grammar rule at the given position."""
        memo_key = (rule_name, pos)
        if memo_key in self.memo:
            return self.memo[memo_key]

        # Track furthest position for error reporting
        if pos > self.max_pos or not self.max_rule:
            self.max_pos = max(pos, self.max_pos)
            self.max_rule = rule_name

        # Handle built-in token types
        if rule_name in SUPPORTED_TOKENS:
            result = self._match_token(rule_name, pos)
            self.memo[memo_key] = result
            return result

        rule = self.grammar.get_rule(rule_name)
        if not rule:
            result = ParseResult(False, pos)
            self.memo[memo_key] = result
            return result

        pos = self._skip_ignored(pos)
        self._rule_stack.append(rule_name)
        try:
            result = self._match_node(rule.pattern, pos)
        finally:
            self._rule_stack.pop()

        if result.success and not rule.is_fragment:
            # Build AST node for this rule
            line, column = self._pos_to_line_col(pos)
            node = SourceAST(
                node_type=rule.node_type,
                line=line,
                column=column,
                source_text=self.source[pos:result.pos],
            )

            if result.node:
                if isinstance(result.node, list):
                    node.children = result.node
                elif isinstance(result.node, SourceAST):
                    node.children = [result.node]
                else:
                    node.value = result.node
            elif result.children:
                # Wrap raw strings (operators/literals) into SourceAST nodes
                # so they are preserved in the tree
                wrapped = []
                for c in result.children:
                    if isinstance(c, SourceAST):
                        wrapped.append(c)
                    elif isinstance(c, str) and c.strip():
                        wrapped.append(SourceAST(
                            node_type="Operator",
                            value=c,
                            line=line,
                            column=column,
                        ))
                node.children = wrapped

            result = ParseResult(True, result.pos, node)

        self.memo[memo_key] = result
        return result

    def _note_failure(self, pos: int) -> None:
        """Record the furthest failing position for error reporting."""
        if pos > self.max_pos:
            self.max_pos = pos
            if self._rule_stack:
                self.max_rule = self._rule_stack[-1]

    def _match_node(self, node: PEGNode, pos: int) -> ParseResult:
        """Match a PEG node at the given position."""
        if node.node_type == PEGNodeType.LITERAL:
            return self._match_literal(node.value, pos)

        elif node.node_type == PEGNodeType.CHAR_CLASS:
            return self._match_char_class(node.value, pos)

        elif node.node_type == PEGNodeType.ANY_CHAR:
            if pos < len(self.source):
                return ParseResult(True, pos + 1, self.source[pos])
            self._note_failure(pos)
            return ParseResult(False, pos)

        elif node.node_type == PEGNodeType.RULE_REF:
            return self._match_rule(node.value, pos)

        elif node.node_type == PEGNodeType.TOKEN_REF:
            return self._match_token(node.value, pos)

        elif node.node_type == PEGNodeType.SEQUENCE:
            return self._match_sequence(node.children, pos)

        elif node.node_type == PEGNodeType.ORDERED_CHOICE:
            return self._match_choice(node.children, pos)

        elif node.node_type == PEGNodeType.ZERO_OR_MORE:
            return self._match_repeat(node.children[0], pos, min_count=0)

        elif node.node_type == PEGNodeType.ONE_OR_MORE:
            return self._match_repeat(node.children[0], pos, min_count=1)

        elif node.node_type == PEGNodeType.OPTIONAL:
            result = self._match_node(node.children[0], pos)
            if result.success:
                return result
            return ParseResult(True, pos)

        elif node.node_type == PEGNodeType.AND_PREDICATE:
            result = self._match_node(node.children[0], pos)
            return ParseResult(result.success, pos)  # Don't consume

        elif node.node_type == PEGNodeType.NOT_PREDICATE:
            result = self._match_node(node.children[0], pos)
            return ParseResult(not result.success, pos)  # Don't consume

        return ParseResult(False, pos)

    def _match_literal(self, text: str, pos: int) -> ParseResult:
        """Match a literal string.

        For purely-alphabetic literals (keywords) a word-boundary check
        is enforced: the matched text must NOT be immediately followed by
        an alphanumeric character or underscore.  This prevents 'END'
        from matching inside 'ENDIF', 'IF' inside 'IFFY', etc.
        """
        pos = self._skip_ignored(pos)
        end = pos + len(text)
        if self.source[pos:end] == text:
            # Word-boundary: alphabetic literals must not be a prefix of
            # a longer identifier.
            if text.isalpha() and end < len(self.source) and (
                    self.source[end].isalnum() or self.source[end] == '_'):
                self._note_failure(pos)
                return ParseResult(False, pos)
            return ParseResult(True, end, text)
        self._note_failure(pos)
        return ParseResult(False, pos)

    def _match_char_class(self, pattern: str, pos: int) -> ParseResult:
        """Match a character class like [a-zA-Z0-9_]."""
        if pos >= len(self.source):
            self._note_failure(pos)
            return ParseResult(False, pos)

        regex = f"[{pattern}]"
        m = re.match(regex, self.source[pos:])
        if m:
            return ParseResult(True, pos + 1, self.source[pos])
        self._note_failure(pos)
        return ParseResult(False, pos)

    def _match_sequence(self, children: List[PEGNode], pos: int) -> ParseResult:
        """Match a sequence of patterns."""
        collected = []
        current_pos = pos

        for child in children:
            result = self._match_node(child, current_pos)
            if not result.success:
                return ParseResult(False, pos)
            current_pos = result.pos
            if result.node is not None:
                collected.append(result.node)
            collected.extend(result.children)

        return ParseResult(True, current_pos, children=collected)

    def _match_choice(self, alternatives: List[PEGNode], pos: int) -> ParseResult:
        """Match the first successful alternative (ordered choice)."""
        for alt in alternatives:
            result = self._match_node(alt, pos)
            if result.success:
                return result
        return ParseResult(False, pos)

    def _match_repeat(self, pattern: PEGNode, pos: int, min_count: int = 0) -> ParseResult:
        """Match a pattern repeatedly."""
        collected = []
        current_pos = pos
        count = 0

        while True:
            result = self._match_node(pattern, current_pos)
            if not result.success or result.pos == current_pos:
                break
            current_pos = result.pos
            count += 1
            if result.node is not None:
                collected.append(result.node)
            collected.extend(result.children)

        if count < min_count:
            return ParseResult(False, pos)

        return ParseResult(True, current_pos, children=collected)

    def _match_token(self, token_type: str, pos: int) -> ParseResult:
        """Match a built-in token type."""
        pos = self._skip_ignored(pos)

        if token_type == "NUMBER":
            m = re.match(r'[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?', self.source[pos:])
            if m:
                val = m.group(0)
                line, column = self._pos_to_line_col(pos)
                node = SourceAST("Number", value=float(val) if '.' in val or 'e' in val.lower() else int(val),
                                 line=line,
                                 column=column)
                return ParseResult(True, pos + len(val), node)

        elif token_type == "STRING":
            if pos < len(self.source) and self.source[pos] in '"\'':
                quote = self.source[pos]
                i = pos + 1
                while i < len(self.source):
                    if self.source[i] == '\\' and i + 1 < len(self.source):
                        i += 2
                    elif self.source[i] == quote:
                        val = self.source[pos + 1:i]
                        line, column = self._pos_to_line_col(pos)
                        node = SourceAST("String", value=val,
                                         line=line,
                                         column=column)
                        return ParseResult(True, i + 1, node)
                    else:
                        i += 1

        elif token_type == "IDENT":
            m = re.match(r'[a-zA-Z_]\w*', self.source[pos:])
            if m:
                val = m.group(0)
                line, column = self._pos_to_line_col(pos)
                node = SourceAST("Identifier", value=val,
                                 line=line,
                                 column=column)
                return ParseResult(True, pos + len(val), node)

        elif token_type == "NEWLINE":
            if pos < len(self.source) and self.source[pos] == '\n':
                return ParseResult(True, pos + 1)
            if self.source[pos:pos + 2] == '\r\n':
                return ParseResult(True, pos + 2)

        elif token_type == "EOF":
            remaining = self.source[pos:].strip()
            if not remaining:
                return ParseResult(True, pos)

        self._note_failure(pos)
        return ParseResult(False, pos)

    def _prepare_comment_patterns(self) -> None:
        """Compile comment patterns once per parse.

        Matching with ``pattern.match(text, pos)`` instead of slicing the
        remaining input removes an O(n) copy from every whitespace skip, which
        dominated parse time on large inputs.
        """
        self._comments: List[Tuple[Any, Optional[str]]] = []
        for pattern in self.grammar.comment_patterns:
            try:
                compiled = re.compile(pattern)
            except re.error as error:
                raise ValueError(
                    f"Invalid comment pattern {pattern!r}: {error}"
                ) from error
            first = pattern[0] if pattern else ""
            literal = (
                first
                if first and first not in "\\^$.*+?()[]{}|" and len(first) == 1
                else None
            )
            self._comments.append((compiled, literal))

    def _skip_ignored(self, pos: int) -> int:
        """Skip whitespace and comments."""
        if not self.grammar.skip_whitespace:
            return pos

        source = self.source
        length = len(source)
        while True:
            start = pos
            while pos < length and source[pos] in " \t\r\n":
                pos += 1
            for compiled, literal in self._comments:
                if literal is not None and (
                    pos >= length or source[pos] != literal
                ):
                    continue
                match = compiled.match(source, pos)
                if match and match.end() > pos:
                    pos = match.end()
                    break
            if pos == start:
                return pos

    def _compute_line_starts(self) -> None:
        """Compute line start positions for error reporting."""
        self.line_starts = [0]
        for i, ch in enumerate(self.source):
            if ch == '\n':
                self.line_starts.append(i + 1)

    def _pos_to_line_col(self, pos: int) -> Tuple[int, int]:
        """Convert byte offset to (line, column) — both 1-based."""
        line = bisect.bisect_right(self.line_starts, pos)
        col = pos - self.line_starts[line - 1] + 1
        return line, col



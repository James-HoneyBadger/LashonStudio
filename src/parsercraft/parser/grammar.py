"""
PEG (Parsing Expression Grammar) Engine for ParserCraft

Allows language designers to define custom syntax using PEG notation
in their language configuration files. This enables creating truly new
language structures, not just keyword renaming.

Grammar Syntax:
    rule_name <- pattern1 / pattern2    # Ordered choice
    rule_name <- a b c                  # Sequence
    rule_name <- a*                     # Zero or more
    rule_name <- a+                     # One or more
    rule_name <- a?                     # Optional
    rule_name <- &a                     # And-predicate (lookahead)
    rule_name <- !a                     # Not-predicate (negative lookahead)
    rule_name <- 'literal'              # Literal string match
    rule_name <- [a-z]                  # Character class
    rule_name <- .                      # Any character

Example grammar for a simple expression language:
    program    <- statement*
    statement  <- assignment / expr_stmt
    assignment <- IDENT '=' expr ';'
    expr_stmt  <- expr ';'
    expr       <- term (('+' / '-') term)*
    term       <- factor (('*' / '/') factor)*
    factor     <- NUMBER / IDENT / '(' expr ')'
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_TOKENS = frozenset({"NUMBER", "STRING", "IDENT", "NEWLINE", "EOF"})


# ---------------------------------------------------------------------------
# PEG AST node types (grammar definition tree, not source-code tree)
# ---------------------------------------------------------------------------

class PEGNodeType(Enum):
    """Types of nodes in a PEG grammar definition."""
    SEQUENCE = auto()
    ORDERED_CHOICE = auto()
    ZERO_OR_MORE = auto()
    ONE_OR_MORE = auto()
    OPTIONAL = auto()
    AND_PREDICATE = auto()
    NOT_PREDICATE = auto()
    LITERAL = auto()
    CHAR_CLASS = auto()
    ANY_CHAR = auto()
    RULE_REF = auto()
    TOKEN_REF = auto()      # References a built-in token type (NUMBER, STRING, etc.)
    ACTION = auto()          # Semantic action attached to a rule


@dataclass
class PEGNode:
    """A node in the PEG grammar definition tree."""
    node_type: PEGNodeType
    value: Any = None
    children: List[PEGNode] = field(default_factory=list)
    action: Optional[str] = None       # Semantic action name
    label: Optional[str] = None        # Capture label for named captures

    def __repr__(self) -> str:
        if self.value is not None:
            return f"PEGNode({self.node_type.name}, {self.value!r})"
        return f"PEGNode({self.node_type.name}, children={len(self.children)})"


@dataclass
class GrammarRule:
    """A single named rule in the grammar."""
    name: str
    pattern: PEGNode
    description: str = ""
    is_fragment: bool = False   # Fragment rules don't produce AST nodes
    node_type: str = ""         # AST node type to produce (defaults to rule name)

    def __post_init__(self):
        if not self.node_type:
            self.node_type = self.name


@dataclass
class Grammar:
    """Complete grammar definition."""
    name: str = "custom"
    rules: Dict[str, GrammarRule] = field(default_factory=dict)
    start_rule: str = "program"
    skip_whitespace: bool = True
    comment_patterns: List[str] = field(default_factory=lambda: ["//.*", r"/\*[\s\S]*?\*/"])

    def add_rule(self, name: str, pattern: PEGNode, **kwargs) -> None:
        """Add a rule to the grammar."""
        self.rules[name] = GrammarRule(name=name, pattern=pattern, **kwargs)

    def get_rule(self, name: str) -> Optional[GrammarRule]:
        return self.rules.get(name)

    def validate(self) -> List[str]:
        """Validate grammar for undefined rule references and left recursion."""
        errors = []
        defined = set(self.rules.keys()) | SUPPORTED_TOKENS

        for name, rule in self.rules.items():
            self._check_refs(rule.pattern, defined, name, errors)

        # Check start rule exists
        if self.start_rule not in self.rules:
            errors.append(f"Start rule '{self.start_rule}' is not defined")

        # Check left recursion
        for name in self.rules:
            if self._is_left_recursive(name, set()):
                errors.append(f"Rule '{name}' is left-recursive (not allowed in PEG)")

        return errors

    def _check_refs(self, node: PEGNode, defined: set, rule_name: str, errors: list) -> None:
        if node.node_type == PEGNodeType.RULE_REF:
            if node.value not in defined:
                errors.append(f"Rule '{rule_name}' references undefined rule '{node.value}'")
        elif node.node_type == PEGNodeType.TOKEN_REF:
            if node.value not in SUPPORTED_TOKENS:
                errors.append(
                    f"Rule '{rule_name}' references unsupported token '{node.value}' "
                    f"(supported: {', '.join(sorted(SUPPORTED_TOKENS))})"
                )
        for child in node.children:
            self._check_refs(child, defined, rule_name, errors)

    def _is_left_recursive(self, rule_name: str, visited: set) -> bool:
        if rule_name in visited:
            return True
        if rule_name not in self.rules:
            return False
        visited = visited | {rule_name}
        pattern = self.rules[rule_name].pattern
        return self._first_can_be(pattern, rule_name, visited)

    def _first_can_be(self, node: PEGNode, target: str, visited: set) -> bool:
        if node.node_type == PEGNodeType.RULE_REF:
            if node.value == target:
                return True
            return self._is_left_recursive(node.value, visited)
        if node.node_type == PEGNodeType.SEQUENCE and node.children:
            return self._first_can_be(node.children[0], target, visited)
        if node.node_type == PEGNodeType.ORDERED_CHOICE:
            return any(self._first_can_be(c, target, visited) for c in node.children)
        if node.node_type in (PEGNodeType.ZERO_OR_MORE, PEGNodeType.ONE_OR_MORE,
                               PEGNodeType.OPTIONAL):
            return self._first_can_be(node.children[0], target, visited) if node.children else False
        return False


# ---------------------------------------------------------------------------
# Grammar DSL Parser — parses PEG grammar text into Grammar objects
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
class SourceAST:
    """AST node produced by the grammar engine from source code."""
    node_type: str
    value: Any = None
    children: List[SourceAST] = field(default_factory=list)
    line: int = 0
    column: int = 0
    source_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.node_type,
            "value": self.value,
            "children": [c.to_dict() for c in self.children],
            "line": self.line,
            "column": self.column,
        }

    def __repr__(self) -> str:
        if self.value is not None:
            return f"{self.node_type}({self.value!r})"
        if self.children:
            return f"{self.node_type}[{len(self.children)}]"
        return self.node_type

    def pretty(self, indent: int = 0) -> str:
        """Pretty-print the AST tree."""
        prefix = "  " * indent
        parts = [f"{prefix}{self!r}"]
        for child in self.children:
            parts.append(child.pretty(indent + 1))
        return "\n".join(parts)


class PEGInterpreter:
    """Executes a PEG grammar against source text to produce an AST.

    This is the core of the grammar engine — it takes a Grammar object
    and source code, and produces a SourceAST.
    """

    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self.source = ""
        self.line_starts: List[int] = []
        self.memo: Dict[Tuple[str, int], ParseResult] = {}  # Packrat memoization
        self.max_pos = 0        # Furthest position reached (for error reporting)
        self.max_rule = ""      # Rule being tried at max_pos
        self._rule_stack: List[str] = []

    def parse(self, source: str) -> SourceAST:
        """Parse source code using the grammar.

        Returns a SourceAST tree, or raises SyntaxError on failure.
        """
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

    def _skip_ignored(self, pos: int) -> int:
        """Skip whitespace and comments."""
        if not self.grammar.skip_whitespace:
            return pos

        changed = True
        while changed:
            changed = False
            # Skip whitespace
            while pos < len(self.source) and self.source[pos] in ' \t\r\n':
                pos += 1
                changed = True
            # Skip comments
            for pattern in self.grammar.comment_patterns:
                try:
                    m = re.match(pattern, self.source[pos:])
                except re.error as error:
                    raise ValueError(
                        f"Invalid comment pattern {pattern!r}: {error}"
                    ) from error
                if m and m.end() > 0:
                    pos += m.end()
                    changed = True
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


# ---------------------------------------------------------------------------
# Grammar Builder — fluent API for programmatic grammar construction
# ---------------------------------------------------------------------------

class GrammarBuilder:
    """Fluent API for building grammars programmatically.

    Example:
        g = GrammarBuilder("MyLang")
        g.rule("program").seq(g.ref("statement").star())
        g.rule("statement").choice(g.ref("assignment"), g.ref("expr_stmt"))
        g.rule("assignment").seq(g.ident(), g.lit("="), g.ref("expr"), g.lit(";"))
        grammar = g.build()
    """

    def __init__(self, name: str = "custom"):
        self.grammar = Grammar(name=name)
        self._current_rule: Optional[str] = None

    def rule(self, name: str, description: str = "") -> GrammarBuilder:
        """Start defining a new rule."""
        self._current_rule = name
        self.grammar.rules[name] = GrammarRule(name=name, pattern=PEGNode(PEGNodeType.SEQUENCE),
                                                description=description)
        return self

    def start(self, rule_name: str) -> GrammarBuilder:
        """Set the start rule."""
        self.grammar.start_rule = rule_name
        return self

    def set_pattern(self, pattern: PEGNode) -> GrammarBuilder:
        """Set the pattern for the current rule."""
        if self._current_rule and self._current_rule in self.grammar.rules:
            self.grammar.rules[self._current_rule].pattern = pattern
        return self

    # Pattern constructors
    @staticmethod
    def seq(*items: PEGNode) -> PEGNode:
        if len(items) == 1:
            return items[0]
        return PEGNode(PEGNodeType.SEQUENCE, children=list(items))

    @staticmethod
    def choice(*items: PEGNode) -> PEGNode:
        if len(items) == 1:
            return items[0]
        return PEGNode(PEGNodeType.ORDERED_CHOICE, children=list(items))

    @staticmethod
    def star(item: PEGNode) -> PEGNode:
        return PEGNode(PEGNodeType.ZERO_OR_MORE, children=[item])

    @staticmethod
    def plus(item: PEGNode) -> PEGNode:
        return PEGNode(PEGNodeType.ONE_OR_MORE, children=[item])

    @staticmethod
    def opt(item: PEGNode) -> PEGNode:
        return PEGNode(PEGNodeType.OPTIONAL, children=[item])

    @staticmethod
    def lit(text: str) -> PEGNode:
        return PEGNode(PEGNodeType.LITERAL, text)

    @staticmethod
    def ref(rule_name: str) -> PEGNode:
        return PEGNode(PEGNodeType.RULE_REF, rule_name)

    @staticmethod
    def token(token_type: str) -> PEGNode:
        return PEGNode(PEGNodeType.TOKEN_REF, token_type)

    @staticmethod
    def ident() -> PEGNode:
        return PEGNode(PEGNodeType.TOKEN_REF, "IDENT")

    @staticmethod
    def number() -> PEGNode:
        return PEGNode(PEGNodeType.TOKEN_REF, "NUMBER")

    @staticmethod
    def string() -> PEGNode:
        return PEGNode(PEGNodeType.TOKEN_REF, "STRING")

    @staticmethod
    def char_class(pattern: str) -> PEGNode:
        return PEGNode(PEGNodeType.CHAR_CLASS, pattern)

    @staticmethod
    def any_char() -> PEGNode:
        return PEGNode(PEGNodeType.ANY_CHAR)

    @staticmethod
    def not_pred(item: PEGNode) -> PEGNode:
        return PEGNode(PEGNodeType.NOT_PREDICATE, children=[item])

    @staticmethod
    def and_pred(item: PEGNode) -> PEGNode:
        return PEGNode(PEGNodeType.AND_PREDICATE, children=[item])

    def build(self) -> Grammar:
        """Build and validate the grammar."""
        errors = self.grammar.validate()
        if errors:
            raise ValueError(f"Grammar validation errors: {'; '.join(errors)}")
        return self.grammar


# ---------------------------------------------------------------------------
# Config Integration — load grammars from YAML/JSON language config
# ---------------------------------------------------------------------------

def grammar_from_config(config_dict: Dict[str, Any]) -> Grammar:
    """Create a Grammar from a language config dictionary.

    Expected config format:
        grammar:
          start: program
          skip_whitespace: true
          comments:
            - "//.*"
            - "/\\*[\\s\\S]*?\\*/"
          rules:
            program: "statement*"
            statement: "assignment / if_stmt / expr_stmt"
            assignment: "IDENT '=' expr ';'"
            if_stmt: "'if' '(' expr ')' block ('else' block)?"
            block: "'{' statement* '}'"
            expr: "term (('+' / '-') term)*"
            term: "factor (('*' / '/') factor)*"
            factor: "NUMBER / IDENT / '(' expr ')' / STRING"
            expr_stmt: "expr ';'"
    """
    grammar_config = config_dict.get("grammar", {})
    if not grammar_config:
        return _default_grammar()

    rules_dict = grammar_config.get("rules", {})
    if not rules_dict:
        return _default_grammar()

    # Build PEG text from config
    peg_lines = []
    for name, pattern in rules_dict.items():
        peg_lines.append(f"{name} <- {pattern}")

    peg_text = "\n".join(peg_lines)
    parser = GrammarParser()
    grammar = parser.parse(peg_text, grammar_config.get("name", "custom"))

    grammar.start_rule = grammar_config.get("start", "program")
    grammar.skip_whitespace = grammar_config.get("skip_whitespace", True)
    grammar.comment_patterns = grammar_config.get("comments", ["//.*"])

    return grammar


def _default_grammar() -> Grammar:
    """Create a default grammar suitable for Python-like languages."""
    peg_text = """
program     <- statement*
statement   <- function_def / if_stmt / while_stmt / for_stmt / return_stmt / assignment / expr_stmt
function_def <- 'def' IDENT '(' param_list? ')' ':' block
param_list  <- IDENT (',' IDENT)*
if_stmt     <- 'if' expr ':' block ('elif' expr ':' block)* ('else' ':' block)?
while_stmt  <- 'while' expr ':' block
for_stmt    <- 'for' IDENT 'in' expr ':' block
return_stmt <- 'return' expr?
assignment  <- IDENT '=' expr
expr_stmt   <- expr
block       <- statement+
expr        <- comparison
comparison  <- addition (('==' / '!=' / '<=' / '>=' / '<' / '>') addition)*
addition    <- multiplication (('+' / '-') multiplication)*
multiplication <- unary (('*' / '/' / '%') unary)*
unary       <- ('-' / '!') unary / call
call        <- primary ('(' arg_list? ')')*
arg_list    <- expr (',' expr)*
primary     <- NUMBER / STRING / IDENT / '(' expr ')' / list_literal
list_literal <- '[' (expr (',' expr)*)? ']'
"""
    parser = GrammarParser()
    return parser.parse(peg_text.strip(), "default")

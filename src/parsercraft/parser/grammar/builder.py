"""Fluent grammar construction and config-to-grammar conversion."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .defaults import _default_grammar
from .model import Grammar, GrammarRule, PEGNode, PEGNodeType
from .peg_parser import GrammarParser

__all__ = ["GrammarBuilder", "grammar_from_config"]

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



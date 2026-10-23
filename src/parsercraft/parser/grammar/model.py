"""PEG grammar model: rules and the grammar definition tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

__all__ = ["SUPPORTED_TOKENS", "PEGNode", "PEGNodeType", "Grammar", "GrammarRule"]

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



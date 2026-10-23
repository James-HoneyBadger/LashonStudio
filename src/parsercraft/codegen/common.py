"""Shared AST traversal helpers for code generators."""

from __future__ import annotations

from typing import Any, Iterable

#: Tokens that carry structure rather than meaning for expression rendering.
STRUCTURAL_OPERATORS = frozenset(
    {"=", ";", ":", ",", "(", ")", "{", "}", "[", "]"}
)

COMPARISON_OPERATORS = frozenset({"==", "!=", "<", ">", "<=", ">="})


def meaningful_children(
    node: Any,
    exclude: Iterable[str] = (),
) -> list[Any]:
    """Return children that are not structural operators."""
    blocked = STRUCTURAL_OPERATORS | frozenset(exclude)
    return [
        child
        for child in node.children
        if not (child.node_type == "Operator" and child.value in blocked)
    ]


def split_chain(
    node: Any,
    structural: Iterable[str] = STRUCTURAL_OPERATORS,
) -> tuple[list[Any], list[Any]]:
    """Split an expression chain into ``(operands, operators)``."""
    blocked = frozenset(structural)
    children = [
        child
        for child in node.children
        if not (child.node_type == "Operator" and child.value in blocked)
    ]
    operands = [child for child in children if child.node_type != "Operator"]
    operators = [child for child in children if child.node_type == "Operator"]
    return operands, operators


def inline_assignment(node: Any) -> tuple[Any, Any] | None:
    """Return ``(target, value)`` for an inline ``IDENT = expr ;`` statement."""
    if node.node_type not in ("statement", "Statement"):
        return None
    if not any(
        child.node_type == "Operator" and child.value == "="
        for child in node.children
    ):
        return None
    meaningful = meaningful_children(node)
    if len(meaningful) < 2:
        return None
    return meaningful[0], meaningful[1]

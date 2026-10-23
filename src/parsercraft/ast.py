"""Core AST contract.

``SourceAST`` is the node type every parser produces and every backend
consumes. It lives outside :mod:`parsercraft.parser` so backends can depend on
the contract without importing the parser (which would create a cycle).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

__all__ = ["SourceAST"]


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

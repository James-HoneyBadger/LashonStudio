"""Python backend: AST → Python source.

The emitter is composed from focused mixins so expression, statement, and
control-flow rules can be read and tested in isolation.
"""

from __future__ import annotations

from .control_flow import ControlFlowEmitter
from .expressions import ExpressionEmitter
from .statements import StatementEmitter
from .transpiler import PythonTranspiler, TranspileOptions

__all__ = [
    "ControlFlowEmitter",
    "ExpressionEmitter",
    "PythonTranspiler",
    "StatementEmitter",
    "TranspileOptions",
]

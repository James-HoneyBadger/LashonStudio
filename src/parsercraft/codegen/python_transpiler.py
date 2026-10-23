"""Deprecated import path — the implementation lives in :mod:`parsercraft.codegen.python`.

Kept as a thin re-export so existing imports
(``from parsercraft.codegen.python_transpiler import PythonTranspiler``) keep
working.
"""

from __future__ import annotations

from parsercraft.codegen.python import (
    ControlFlowEmitter,
    ExpressionEmitter,
    PythonTranspiler,
    StatementEmitter,
    TranspileOptions,
)
from parsercraft.codegen.python.transpiler import (
    transpile_and_exec,
    transpile_to_python,
)

__all__ = [
    "ControlFlowEmitter",
    "ExpressionEmitter",
    "PythonTranspiler",
    "StatementEmitter",
    "TranspileOptions",
    "transpile_and_exec",
    "transpile_to_python",
]

"""Deprecated import path — the implementation lives in :mod:`lashon.codegen.python`.

Kept as a thin re-export so existing imports
(``from lashon.codegen.python_transpiler import PythonTranspiler``) keep
working.
"""

from __future__ import annotations

from lashon.codegen.python import (
    ControlFlowEmitter,
    ExpressionEmitter,
    PythonTranspiler,
    StatementEmitter,
    TranspileOptions,
)
from lashon.codegen.python.transpiler import (
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

"""
parsercraft.codegen — Multi-backend code generation from SourceAST.

This subpackage provides four production-grade backends that each translate
a SourceAST (produced by PEGInterpreter) into target-language source code.
All backends implement the same interface::

    backend = SomeGenerator()
    output_string = backend.translate_source_ast(ast)

Backends
--------
PythonTranspiler
    Emits Python source code.  Supports keyword/function/operator remapping
    via TranspileOptions.  Use ``transpile_and_exec()`` for immediate
    execution without writing to disk.

CCodeGenerator
    Emits ANSI C with ``#include`` preamble and a ``main()`` function.

WasmGenerator
    Emits WebAssembly Text Format (WAT).  Returns a ``WasmModule`` object;
    call ``module.to_wat()`` to get the string.

LLVMIRGenerator
    Emits LLVM IR in SSA form, compatible with ``llc`` and ``lli``.

Convenience functions
---------------------
transpile_and_exec(ast, keyword_map=None, function_map=None, globals_dict=None)
    Transpile and immediately execute; returns the program namespace
    (dunder keys such as ``__builtins__`` are omitted).

transpile_to_python(ast, keyword_map=None, function_map=None, wrap_main=False)
    Transpile to a Python source string without executing.

Custom backends
---------------
To add a fifth backend, create a class with::

    def translate_source_ast(self, ast: SourceAST) -> str: ...

See docs/TUTORIAL.md — Tutorial 5 for a full worked example.
"""

from .codegen_c import CCodeGenerator, CType
from .codegen_wasm import WasmGenerator, WasmModule, WasmOp, WasmType
from .llvm_ir import LLVMIRGenerator
from .python_transpiler import (
    PythonTranspiler,
    TranspileOptions,
    transpile_and_exec,
    transpile_to_python,
)

__all__ = [
    "CCodeGenerator",
    "CType",
    "WasmGenerator",
    "WasmModule",
    "WasmType",
    "WasmOp",
    "PythonTranspiler",
    "TranspileOptions",
    "transpile_to_python",
    "transpile_and_exec",
    "LLVMIRGenerator",
]

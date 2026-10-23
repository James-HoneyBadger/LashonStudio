"""CLI command implementations."""

from .codegen import cmd_codegen_c, cmd_codegen_llvm, cmd_codegen_wasm
from .generics import cmd_generics
from .init import cmd_init
from .run import cmd_run
from .typecheck import cmd_type_check

__all__ = [
    "cmd_codegen_c",
    "cmd_codegen_llvm",
    "cmd_codegen_wasm",
    "cmd_generics",
    "cmd_init",
    "cmd_run",
    "cmd_type_check",
]

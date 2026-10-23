"""
parsercraft.runtime — Execution environment for custom languages.

This subpackage provides the runtime components that sit between a parsed
and transpiled program and actual execution:  an interactive REPL,
a standard library, a foreign-function interface, multi-file module
imports, and a config-driven language runtime.

Primary classes
---------------
REPL
    Interactive read-eval-print loop.  Supports `:ast`, `:py`, `:vars`,
    `:load`, `:reset`, and other meta-commands::

        from parsercraft.runtime import REPL
        REPL(config=my_config).run()

StdLib
    Provides six injectable standard-library modules::

        stdlib = StdLib()
        stdlib.inject(namespace)           # inject all modules
        stdlib.inject_module(namespace, "math")  # inject one module

    Available modules:  io · math · string · collections · system · random

FFIBridge
    Foreign-function interface for calling C shared libraries and
    arbitrary Python callables from custom languages::

        ffi = FFIBridge()
        ffi.register_python("double", lambda x: x * 2)
        ffi.load_c_library("libm", "/usr/lib/libm.so.6")
        ffi.register_c_function("libm", "sqrt", [...], ctypes.c_double)

LanguageRuntime
    Config-driven execution environment.  Loads a LanguageConfig and runs
    source programs with keyword remapping applied transparently.

ModuleManager
    Multi-file import system with topological dependency ordering and
    circular-dependency detection.  Raises ``CircularDependencyError``
    before executing any code if a cycle is found.
"""

from .ffi import FFIBinding, FFIBridge
from .language_runtime import LanguageRuntime
from .module_system import ModuleLoader, ModuleManager
from .repl import REPL
from .stdlib import StdConstant, StdFunction, StdLib, StdModule

__all__ = [
    "LanguageRuntime",
    "ModuleManager",
    "ModuleLoader",
    "REPL",
    "StdLib",
    "StdModule",
    "StdFunction",
    "StdConstant",
    "FFIBridge",
    "FFIBinding",
]

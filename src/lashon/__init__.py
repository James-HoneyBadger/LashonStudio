"""
Lashon v4.0.0 — Custom Programming Language Construction Framework
=======================================================================

Lashon provides a complete stack for designing, implementing, and
distributing programming languages — from grammar definition through
multi-target code generation.

Core pipeline::

    Grammar (PEG text or GrammarBuilder API)
        │
        ▼
    PEGInterpreter  ──►  SourceAST  ──►  Backend
                                         ├── PythonTranspiler → Python / exec()
                                         ├── CCodeGenerator    → ANSI C
                                         ├── WasmGenerator     → WAT
                                         └── LLVMIRGenerator   → LLVM IR

Quick start::

    from lashon.parser import GrammarParser, PEGInterpreter
    from lashon.codegen import transpile_and_exec

    grammar = GrammarParser().parse(
        'program <- statement+\\n'
        'statement <- IDENT "=" expr ";\"\\n'
        'expr <- NUMBER'
    )
    ast = PEGInterpreter(grammar).parse('x = 42 ;')
    result = transpile_and_exec(ast)   # {'x': 42}

Config-driven usage::

    from lashon import LanguageConfig, LanguageRuntime

    config = LanguageConfig.from_preset("python_like")
    config.rename_keyword("if", "cuando")
    config.save("spanish.yaml")

Entry points
------------
- ``lashon``       — CLI (30+ subcommands)
- ``lashon-ide``   — Tkinter IDE
- ``lashon-repl``  — Interactive REPL

Documentation
-------------
- README.md              — Project overview and Quick Start
- docs/INSTALL.md        — Installation and setup
- docs/USER_GUIDE.md     — End-user guide (CLI, REPL, configs, IDE)
- docs/TECHNICAL_REFERENCE.md — Full API reference
- docs/TUTORIAL.md       — Step-by-step tutorials
"""

__version__ = "4.0.0"
__author__ = "James-HoneyBadger"

__all__ = ["LanguageConfig", "LanguageRuntime"]


def __getattr__(name: str):
    """Import compatibility shims lazily so ``import lashon`` stays cheap."""
    if name == "LanguageConfig":
        from lashon.config.language_config import LanguageConfig

        return LanguageConfig
    if name == "LanguageRuntime":
        from lashon.runtime.language_runtime import LanguageRuntime

        return LanguageRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)

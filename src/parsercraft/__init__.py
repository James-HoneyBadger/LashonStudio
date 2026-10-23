"""
ParserCraft v4.0.0 — Custom Programming Language Construction Framework
=======================================================================

ParserCraft provides a complete stack for designing, implementing, and
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

    from parsercraft.parser import GrammarParser, PEGInterpreter
    from parsercraft.codegen import transpile_and_exec

    grammar = GrammarParser().parse(
        'program <- statement+\\n'
        'statement <- IDENT "=" expr ";\"\\n'
        'expr <- NUMBER'
    )
    ast = PEGInterpreter(grammar).parse('x = 42 ;')
    result = transpile_and_exec(ast)   # {'x': 42}

Config-driven usage::

    from parsercraft import LanguageConfig, LanguageRuntime

    config = LanguageConfig.from_preset("python_like")
    config.rename_keyword("if", "cuando")
    config.save("spanish.yaml")

Entry points
------------
- ``parsercraft``       — CLI (30+ subcommands)
- ``parsercraft-ide``   — Tkinter IDE
- ``parsercraft-repl``  — Interactive REPL

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
    """Import compatibility shims lazily so ``import parsercraft`` stays cheap."""
    if name == "LanguageConfig":
        from parsercraft.config.language_config import LanguageConfig

        return LanguageConfig
    if name == "LanguageRuntime":
        from parsercraft.runtime.language_runtime import LanguageRuntime

        return LanguageRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)

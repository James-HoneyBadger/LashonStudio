# Lashon Studio Documentation

> Version 5.0.0 · Python 3.10+ · [Project README](https://github.com/James-HoneyBadger/LashonStudio/blob/main/README.md)

Lashon is a programming-language construction framework. You define a PEG
grammar, Lashon builds a packrat parser and AST, and code generators emit
Python, C, WebAssembly, or LLVM IR. A headless Studio controller, a Tkinter
workbench, a REPL, an LSP analyzer, a DAP debugger, and packaging tools complete
the lifecycle.

This directory is the full documentation set. Executable examples were run
against the repository (or the installed package where noted); API signature
blocks in the [technical reference](TECHNICAL_REFERENCE.md) are declarations,
not runnable programs.

---

## Start here

| If you want to… | Read |
|---|---|
| Install Lashon | [INSTALL.md](INSTALL.md) |
| Build a working language in ten minutes | [QUICKSTART.md](QUICKSTART.md) |
| Follow a task-by-task guide | [USER_GUIDE.md](USER_GUIDE.md) |
| Learn the platform progressively | [TUTORIAL.md](TUTORIAL.md) |
| Design a non-trivial language | [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) |
| Look up a PEG construct | [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) |
| Use the GUI | [STUDIO_GUIDE.md](STUDIO_GUIDE.md) |
| Look up a CLI command | [CLI_REFERENCE.md](CLI_REFERENCE.md) |
| Understand a backend | [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) |
| Use the REPL, stdlib, FFI, or modules | [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md) |
| Give a language a drawing canvas | [GRAPHICS.md](GRAPHICS.md) |
| Understand types, generics, protocols | [TYPE_SYSTEM.md](TYPE_SYSTEM.md) |
| Integrate an editor or debugger | [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) |
| Ship a language or extension | [PACKAGING.md](PACKAGING.md) |
| Read the API | [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) |
| Understand internals | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Use or extend the Rust core | [RUST_CORE.md](RUST_CORE.md) |
| Fix a problem | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

---

## Learning paths

### Path 1 — “I want to see it work” (15 minutes)

1. [QUICKSTART.md](QUICKSTART.md) — grammar → parse → execute.
2. [TUTORIAL.md § Tutorial 1](TUTORIAL.md).
3. Launch the Studio: `lashon-ide projects/aurora`.

### Path 2 — “I want to design a language” (a weekend)

1. [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — design worksheet and method.
2. [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) — the notation, precisely.
3. [TUTORIAL.md § Tutorial 5](TUTORIAL.md) — build Aurora.
4. [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — map the AST to backends.
5. [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md) — give the language a runtime.
6. [PACKAGING.md](PACKAGING.md) — ship it.

### Path 3 — “I want to integrate Lashon” (an afternoon)

1. [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) — public API.
2. [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) — editor and debugger hooks.
3. [ARCHITECTURE.md](ARCHITECTURE.md) — where to extend safely.

### Path 4 — “I want to contribute”

1. [CONTRIBUTING.md](https://github.com/James-HoneyBadger/LashonStudio/blob/main/CONTRIBUTING.md) — setup, tests, style, PRs.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — module boundaries.
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — known failure modes.

---

## Reference map

```
Language definition
  language.yaml ──────────────► LanguageConfig
  grammar.peg  ──────────────► GrammarParser ─► Grammar
                                                   │
Source text ─────────────────► PEGInterpreter ─► SourceAST
                                                   │
                     ┌─────────────────────────────┼────────────────────┐
                     ▼                             ▼                    ▼
              PythonTranspiler             CCodeGenerator        WasmGenerator
                     │                             │                    │
                     ▼                             ▼                    ▼
               Python / exec()                 ANSI C                 WAT
                                                   │
                                                   ▼
                                            LLVMIRGenerator
                                                   │
                                                   ▼
                                               LLVM IR
```

| Concept | Primary class | Documentation |
|---|---|---|
| Grammar text | `GrammarParser` | [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) |
| Fluent grammar construction | `GrammarBuilder` | [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md#grammarbuilder) |
| Source parsing | `PEGInterpreter` | [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md#peginterpreter) |
| Incremental reparse | `IncrementalParser` | [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md#incrementalparser) |
| Language metadata | `LanguageConfig` | [USER_GUIDE.md](USER_GUIDE.md#create-a-language-configuration) |
| Code generation | `PythonTranspiler`, `CCodeGenerator`, `WasmGenerator`, `LLVMIRGenerator` | [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) |
| Studio controller | `LanguageStudio` | [STUDIO_GUIDE.md](STUDIO_GUIDE.md) |
| Runtime services | `StdLib`, `FFIBridge`, `ModuleManager` | [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md) |
| Types | `TypeChecker`, `GenericChecker`, `ProtocolChecker` | [TYPE_SYSTEM.md](TYPE_SYSTEM.md) |
| Tooling | `ErrorLocalizer`, LSP, DAP | [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) |
| Packaging | `PackageRegistry`, extension generator | [PACKAGING.md](PACKAGING.md) |

---

## Conventions used in these documents

- **`lashon …`** — the installed console entry point. From a source checkout
  without installation, prefix with `python -m lashon.tooling.cli`.
- **`python`** code blocks assume `lashon` is importable (`pip install -e .`).
- **File paths** are relative to the repository root unless stated otherwise.
- **“Verified”** examples are exercised by the test suite or were executed while
  writing these documents against v5.0.0.
- Output shown after `# →` is illustrative; timings vary.

---

## Documentation source of truth

The code is authoritative. If a document and the implementation disagree, the
implementation wins — please open an issue or a PR with the correction. The
suite is intentionally explicit about **limitations** (for example, the stdio
LSP only handles a subset of requests); see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) and
[PROJECT_ANALYSIS.md](https://github.com/James-HoneyBadger/LashonStudio/blob/main/PROJECT_ANALYSIS.md).

---

## Versioning

Documents track the `4.x` line. Breaking API changes are recorded in
[CHANGELOG.md](https://github.com/James-HoneyBadger/LashonStudio/blob/main/CHANGELOG.md). The `4.0.0` documentation set was regenerated
alongside the Studio release.

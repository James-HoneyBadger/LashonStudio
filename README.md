# ParserCraft

> **Build real programming languages in Python — PEG grammars, packrat parsing, four production code-generation backends.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-371%20passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/version-4.0.0-informational.svg)](pyproject.toml)

ParserCraft is a full-stack programming language construction framework. Define a PEG grammar — either in text notation or via a fluent Python API — and immediately get a working parser, an abstract syntax tree, and code generators targeting Python, C, WebAssembly, and LLVM IR. Add a config-driven REPL, a Language Server Protocol implementation, a DAP debugger, and a Tkinter IDE, and you have everything needed to design, implement, and ship a custom language from a single Python package.

---

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Feature Highlights](#feature-highlights)
- [Quick Start](#quick-start)
- [Language Presets](#language-presets)
- [Code Generation Backends](#code-generation-backends)
- [ParserCraft Studio](#parsercraft-studio)
- [Sample Language Project](#sample-language-project)
- [CLI Reference](#cli-reference)
- [REPL](#repl)
- [Standard Library &amp; FFI](#standard-library--ffi)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Testing](#testing)
- [Requirements](#requirements)
- [License](#license)

---

## Pipeline Overview

```
PEG Grammar
    │
    ▼
GrammarParser / GrammarBuilder
    │
    ▼  packrat memoization
PEGInterpreter  ──►  SourceAST
    │
    ├──► PythonTranspiler   →  Python source / exec()
    ├──► CCodeGenerator     →  ANSI C with main()
    ├──► WasmGenerator      →  WebAssembly Text (WAT)
    └──► LLVMIRGenerator    →  LLVM IR (SSA form)
```

Start with a grammar. Get a working language. Ship it anywhere.

---

## Feature Highlights

| Category | Capability |
|---|---|
| **Grammar** | PEG with ordered choice, sequences, quantifiers (`*`,`+`,`?`), and predicate operators |
| **Parsing** | Packrat memoization for O(n) guaranteed parse time; built-in `NUMBER`, `IDENT`, `STRING` tokens |
| **Architecture** | Enforced layering (core → app → adapters) with import contracts, no cycles, lazy package imports, `parsercraft.ast` as the single AST contract |
| **Rust core** | Grammar model, PEG text parser, and packrat engine also exist in Rust (`crates/`), conformance-checked against the Python engine and usable standalone via `parsercraft-rs` (`validate`, `rules`, `ast`, `parse`, `codegen-c --run`, `codegen-py --run`) |
| **Incremental** | `IncrementalParser` re-parses only changed regions — suitable for real-time IDE use |
| **Backends** | Python transpiler, ANSI C (with `main()`), WebAssembly Text (WAT), LLVM IR (SSA) |
| **Config** | YAML/JSON language definitions with keyword remapping, custom functions, syntax toggles |
| **Presets** | 10 built-in language archetypes (Python-like, JS-like, Pascal-like, Lisp-like, and more) |
| **REPL** | Config-driven interactive loop with AST inspection, variable table, and history |
| **StdLib** | Six injectable modules: `io`, `math`, `string`, `collections`, `system`, `random` |
| **FFI** | ctypes C bridge + Python module imports — call native code from custom languages |
| **Modules** | Multi-file imports with circular dependency detection |
| **Types** | Generic type parameters, protocol-based structural typing |
| **LSP** | Language Server Protocol server for IDE syntax highlighting and completion |
| **DAP** | Debug Adapter Protocol for step-through debugging |
| **Studio** | Tabbed language workbench: project tree, source/grammar/config editors, AST inspector, console, variables, four backend panes, Problems panel, command palette (`Ctrl+Shift+P`), and quick open (`Ctrl+P`) |
| **Playground** | `parsercraft play` serves a browser editor that runs programs and shows every backend |
| **Diagnostics** | `doctor`, `lint`, JSON `validate`, and grammar-aware LSP diagnostics with real error positions |
| **VS Code** | Generates a buildable VS Code extension for any language config (TS scaffold, `language.yaml`, launch integration) |
| **CLI** | 40+ subcommands covering the full language lifecycle |
| **Verification** | Conformance corpus pinning grammars, programs, ASTs, and error positions for every engine |

---

## Quick Start

### Installation

```bash
git clone https://github.com/James-HoneyBadger/ParserCraft.git
cd ParserCraft
pip install -e .
```

See [docs/INSTALL.md](docs/INSTALL.md) for virtual-environment setup and production install options.

### Step 1 — Define a Grammar

Use PEG text notation (recommended for readability):

```python
from parsercraft.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse("""
    program   <- statement+
    statement <- IDENT "=" expr ";"
    expr      <- term (("+" / "-") term)*
    term      <- factor (("*" / "/") factor)*
    factor    <- NUMBER / IDENT / "(" expr ")"
""")
```

Or build grammars programmatically with `GrammarBuilder`:

```python
from parsercraft.parser import GrammarBuilder

g = GrammarBuilder()
g.rule("program").set_pattern(GrammarBuilder.plus(GrammarBuilder.ref("statement")))
g.rule("statement").set_pattern(GrammarBuilder.seq(
    GrammarBuilder.ref("IDENT"),
    GrammarBuilder.lit("="),
    GrammarBuilder.ref("expr"),
    GrammarBuilder.lit(";"),
))
# ... add expr, term, factor rules ...
grammar = g.build()
```

### Step 2 — Parse Source Code

```python
interp = PEGInterpreter(grammar)
ast = interp.parse("x = 2 + 3 * 4 ; y = ( x - 1 ) * 2 ;")
print(ast)  # SourceAST tree
```

### Step 3 — Generate Output

**Execute as Python:**
```python
from parsercraft.codegen import transpile_and_exec

result = transpile_and_exec(ast)
print(result["x"])  # 14
print(result["y"])  # 26
```

**Emit ANSI C:**
```python
from parsercraft.codegen.codegen_c import CCodeGenerator
print(CCodeGenerator().translate_source_ast(ast))
```

**Emit WebAssembly (WAT):**
```python
from parsercraft.codegen.codegen_wasm import WasmGenerator
module = WasmGenerator().translate_source_ast(ast)
print(module.to_wat())
```

**Emit LLVM IR:**
```python
from parsercraft.codegen import LLVMIRGenerator
print(LLVMIRGenerator().translate_source_ast(ast))
```

---

## Language Presets

Load a ready-made language archetype with a single call:

```python
from parsercraft.config import LanguageConfig

config = LanguageConfig.from_preset("python_like")
config.rename_keyword("if", "si")         # localise a keyword
config.save("my_lang.yaml")               # persist
```

| Preset | Style |
|---|---|
| `python_like` | Indentation-sensitive, `def`/`if`/`for` |
| `js_like` | Brace-block, `function`/`let`/`const` |
| `ruby_like` | `do`…`end` blocks, `def`/`while` |
| `golang_like` | Brace-block, short variable declarations |
| `rust_like` | `fn`/`let mut`/`match` |
| `clike` | `int`/`float` declarations, C-style control |
| `functional` | Lambda/`let-in`/`where` functional style |
| `lisp_like` | S-expression syntax |
| `basic_like` | Line-numbered BASIC style |
| `minimal` | Small teaching subset |

---

## Code Generation Backends

| Backend | Class | Output |
|---|---|---|
| Python | `PythonTranspiler` | Runnable Python source; `transpile_and_exec()` for immediate execution |
| C | `CCodeGenerator` | ANSI C with `#include` preamble and `main()` |
| WebAssembly | `WasmGenerator` | WAT text format, importable into any WASM runtime |
| LLVM IR | `LLVMIRGenerator` | SSA-form IR compatible with `llc` / `lli` |

All backends share the same `translate_source_ast(ast) -> str` contract. Adding a fifth backend requires only implementing that one method.

---

## ParserCraft Studio

`parsercraft-ide` opens a complete language-design workbench rather than a
single text pane.

```bash
parsercraft-ide                     # opens the Aurora reference project
parsercraft-ide projects/aurora     # open a project directory or config
```

**Layout**

| Pane | What it does |
|---|---|
| Project tree | Language config, grammar, and sample programs |
| Source editor | Syntax-highlighted programs in your language |
| Grammar editor | Editable PEG grammar with debounced validation |
| Language editor | Metadata, keywords, operators, and syntax options (YAML) |
| Console | Run output, timings, and diagnostics |
| Variables | Live namespace after a run |
| Python / C / WASM / LLVM IR | Generated output for the current program |
| AST | Expandable syntax tree |

**Workflow**

1. Pick a sample or start a new project.
2. Edit `grammar.peg`; validation runs automatically as you type.
3. Write a program in the source pane.
4. Press **F5** to parse, transpile, and execute it.
5. Press **F6** to inspect the AST, **F7** to emit all four backends.
6. **Ctrl+S** syncs the grammar back into `language.yaml` and saves.

The Studio is a thin Tkinter shell over the headless
[`LanguageStudio`](src/parsercraft/ide/studio.py) controller, so the whole
pipeline is testable without a display.

---

## Sample Language Project

[`projects/aurora`](projects/aurora) is a complete reference language:

| File | Purpose |
|---|---|
| [`language.yaml`](projects/aurora/language.yaml) | Metadata, keywords, syntax options, and 18 PEG rules |
| [`grammar.peg`](projects/aurora/grammar.peg) | Canonical editable grammar |
| [`samples/hello.aur`](projects/aurora/samples/hello.aur) | Strings and printing |
| [`samples/fibonacci.aur`](projects/aurora/samples/fibonacci.aur) | Functions, recursion, conditionals |
| [`samples/fizzbuzz.aur`](projects/aurora/samples/fizzbuzz.aur) | Loops and nested conditionals |

```
fn fib(n) {
  if n <= 1 { return n ; }
  return fib(n - 1) + fib(n - 2) ;
}
print fib(10) ;        // 55
```

A copy ships inside the package (`parsercraft.ide.samples.aurora`) so the
sample is available after a wheel install too.

---

## CLI Reference

```
parsercraft <command> [options]
```

| Command | Purpose |
|---|---|
| `init <name>` | Scaffold a language project (`--template aurora\|calculator\|minimal`, `--with-vscode`, `--with-ci`) |
| `doctor` | Check Python, PyYAML, entry points, Tk, compilers, wasmtime, writable dirs |
| `lint <cfg>` | Validate config + grammar (+ optional source) in one CI-friendly pass |
| `demo` | Guided parse → AST → Python → C → WASM → LLVM tour |
| `play [project]` | Serve a browser playground for a language project |
| `config get\|set <cfg> KEY` | Read or change one dotted config key |
| `run <src>` | Parse and execute a program |
| `create` | Interactive language creation wizard |
| `edit <file>` | Open a language config in the visual editor |
| `validate <file>` | Validate a YAML/JSON language config |
| `info <file>` | Display full language config summary |
| `export <file>` | Export config in alternate format (YAML ↔ JSON) |
| `import <file>` | Import and normalise a foreign config |
| `convert <file>` | Convert config format in-place |
| `diff <a> <b>` | Diff two language configs |
| `update <file>` | Apply structured updates to a config |
| `list-presets` | List all built-in language presets |
| `repl [config]` | Launch an interactive REPL |
| `batch <config> [--input-dir DIR]` | Batch-process a directory of source files |
| `test --config <cfg> --tests <file>` | Run the built-in test harness |
| `translate --input <src> --config <cfg>` | Translate source using a config |
| `delete <file>` | Remove a language config safely |
| `lsp --config <cfg> [--stdio]` | Start the Language Server Protocol server |
| `extension --config <cfg>` | Generate a VS Code extension |
| `type-check --config <cfg> --input <src>` | Run the type checker on source |
| `module-info <module>` | Display module dependency information |
| `module-deps <module>` | List all module dependencies |
| `module-cycles [--module-dir DIR]` | Detect circular dependencies |
| `codegen-c <src> [--config <cfg>]` | Emit C code from source |
| `codegen-wasm <src> [--config <cfg>]` | Emit WAT from source |
| `codegen-llvm <src> [--config <cfg>]` | Emit LLVM IR from source |
| `refactor-rename <src> <old> <new>` | Rename a symbol across source files |
| `format <src>` | Auto-format a source file |
| `debug-launch <src>` | Start a DAP server (breakpoints, stepping, variables) |
| `test-run [path]` | Run a project's pytest suite (optional coverage) |
| `generics <src>` | Check generic declarations and instantiations |
| `check-protocol <src>` | Not implemented (exit 2); use `ProtocolChecker` |
| `package-search <query>` | Not implemented (exit 2) |
| `package-install <pkg>` | Not implemented (exit 2) |

```bash
parsercraft init "My Lang" --directory ./languages
parsercraft run languages/my-lang/samples/hello.aur \
  --config languages/my-lang/language.yaml
```

```bash
parsercraft-ide    # Open the Tkinter IDE
parsercraft-repl   # Launch the standalone REPL
```

---

## REPL

```bash
parsercraft-repl
# or with a language config
parsercraft repl my_lang.yaml
```

| Command | Effect |
|---|---|
| `:help` | Show all REPL commands |
| `:ast` | Print the AST of the last expression |
| `:py` | Show the generated Python for the last input |
| `:vars` | List all variables in the current namespace |
| `:reset` | Clear the namespace |
| `:load <file>` | Load a source file into the session |
| `:grammar` | Print the current grammar rules |
| `:quit` | Exit the REPL |

---

## Standard Library & FFI

### Standard Library

```python
from parsercraft.runtime import StdLib

stdlib = StdLib()
ns = {}
stdlib.inject(ns)
# ns now contains: print_val, sqrt, abs_val, len_val,
#                  concat, to_upper, to_lower, range_list, ...
```

Six injectable modules: `io`, `math`, `string`, `collections`, `system`, `random`.

### FFI Bridge

```python
import ctypes
from parsercraft.runtime import FFIBridge

ffi = FFIBridge()

# Register a Python callable
ffi.register_python("double_it", lambda x: x * 2)

# Import a full Python module
ffi.import_python_module("json")

# Load and bind a C shared library
ffi.load_c_library("libm", "/usr/lib/libm.so.6")
ffi.register_c_function("libm", "sqrt", [ctypes.c_double], ctypes.c_double)
```

---

## Architecture

```
src/parsercraft/
├── config/       LanguageConfig, LanguageValidator, IdentifierValidator
├── parser/       GrammarParser, GrammarBuilder, PEGInterpreter, IncrementalParser
├── codegen/      PythonTranspiler, CCodeGenerator, WasmGenerator, LLVMIRGenerator
├── runtime/      REPL, StdLib, FFIBridge, LanguageRuntime, ModuleManager
├── tooling/      CLI, ErrorLocalizer, LSP server, DAP debug adapter
├── ide/          ParserCraftIDE, CodeEditor, ProjectManager
├── types/        TypeChecker, generics, protocols
└── packaging/    VS Code extension generator, package registry
```

See [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) for the full API reference.

---

## Documentation

Start at [docs/index.md](docs/index.md) for learning paths and the full index.

| Document | Description |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Grammar → parse → run in ten minutes |
| [docs/TUTORIAL.md](docs/TUTORIAL.md) | Eight progressive tutorials, from first language to packaging |
| [docs/LANGUAGE_DEVELOPMENT.md](docs/LANGUAGE_DEVELOPMENT.md) | Designing and evolving a real language |
| [docs/GRAMMAR_REFERENCE.md](docs/GRAMMAR_REFERENCE.md) | PEG notation, semantics, and AST production rules |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Task-oriented guide — configs, parsing, execution, Studio |
| [docs/STUDIO_GUIDE.md](docs/STUDIO_GUIDE.md) | ParserCraft Studio manual |
| [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md) | Every command and flag, including placeholders |
| [docs/CODEGEN_GUIDE.md](docs/CODEGEN_GUIDE.md) | Python/C/WASM/LLVM backends, fidelity, custom backends |
| [docs/RUNTIME_GUIDE.md](docs/RUNTIME_GUIDE.md) | REPL, stdlib, FFI, language runtime, modules |
| [docs/TYPE_SYSTEM.md](docs/TYPE_SYSTEM.md) | Types, checker, generics, protocols, narrowing |
| [docs/LSP_AND_DEBUGGING.md](docs/LSP_AND_DEBUGGING.md) | Language server, debug adapter, error localization |
| [docs/PACKAGING.md](docs/PACKAGING.md) | Wheels, VS Code extension, package registry |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Internals: parser, AST, backends, Studio split |
| [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) | API reference for every public class |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptom → cause → fix, plus FAQ |
| [configs/examples/README.md](configs/examples/README.md) | Config file gallery and format reference |

---

## Testing

```bash
python -m pytest tests/ -v
python -m pytest -q --cov --cov-fail-under=43
```

371 tests covering grammar parsing, all four code-generation backends (with
compile-and-run checks for C and LLVM), REPL, stdlib, FFI, error localization,
incremental parsing, types, modules, LSP, packaging, the debug adapter, and the
Studio controller/GUI.

---

## Requirements

- **Python 3.10+**
- **PyYAML 6.0+** (runtime dependency)
- `tkinter` — bundled with most Python distributions (required for the IDE)
- `pytest` and `ruff` — development only

---

## License

MIT — see [LICENSE](LICENSE).

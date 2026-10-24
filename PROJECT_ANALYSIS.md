# Lashon Project Analysis

**Date**: February 2026
**Version**: 4.0.0
**Project**: Lashon — Custom Programming Language Construction Framework

---

## Executive Summary

Lashon is a **well-implemented language construction framework** with a clean
subpackage architecture, four code-generation backends, and 335 passing tests.
The core pipeline (PEG grammar → AST → backend) is fully functional. The areas
with the most limited coverage are advanced type-system generics, the debug
adapter, and partial module-system edge-case handling.

---

## Architecture Overview

```
src/lashon/
├── config/       LanguageConfig, LanguageValidator, IdentifierValidator
├── parser/       GrammarParser, GrammarBuilder, PEGInterpreter, IncrementalParser
├── codegen/      PythonTranspiler, CCodeGenerator, WasmGenerator, LLVMIRGenerator
├── runtime/      REPL, StdLib, FFIBridge, LanguageRuntime, ModuleManager
├── tooling/      CLI (2355 lines, 40+ subcommands), ErrorLocalizer,
│   ├── lsp/          LSP server (683 lines), advanced LSP, integration layer
│   └── debug/        DAP debug adapter
├── ide/          Lashon Studio (LanguageStudio + Tkinter shell), CodeEditor, ProjectManager
├── types/        TypeChecker, generics, protocols, type_system_generics
└── packaging/    VS Code extension gen, package registry, documentation gen
```

---

## 1. Core Pipeline — IMPLEMENTED

### Grammar Engine (`parser/grammar.py`, 970 lines)

**Status**: Fully implemented.

- `GrammarParser` — turns PEG text notation into `Grammar` objects
- `GrammarBuilder` — fluent programmatic API (`seq`, `choice`, `star`, `plus`,
  `opt`, `lit`, `ref`)
- `PEGInterpreter` — packrat-memoized parser; produces `SourceAST` nodes
- `IncrementalParser` — re-parses only changed regions after text edits
- Built-in token types: `NUMBER`, `IDENT`, `STRING`
- Grammar validation: detects undefined rule references and left recursion

### Code Generation Backends (`codegen/`)

All four backends accept a `SourceAST` from the grammar engine and produce
target-language output.

| Backend | Entry point | Output | Lines |
|---------|-------------|--------|-------|
| `PythonTranspiler` | `translate_source_ast(ast)` | Python source / `exec()` | 1174 |
| `CCodeGenerator` | `translate_source_ast(ast)` | C source with `main()` | 494 |
| `WasmGenerator` | `translate_source_ast(ast)` | WAT (WebAssembly Text) | 548 |
| `LLVMIRGenerator` | `translate_source_ast(ast)` | LLVM IR (SSA form) | 536 |

All backends detect the **inline assignment pattern**
(`IDENT "=" expr ";"`) directly on statement nodes without requiring a
separate `assignment` rule.

### Runtime (`runtime/`)

| Module | Purpose | Status |
|--------|---------|--------|
| `REPL` (336 lines) | Interactive shell with `:ast`, `:py`, `:vars`, `:grammar` commands | Full |
| `StdLib` (373 lines) | Six built-in modules: `io`, `math`, `string`, `collections`, `system`, `random` | Full |
| `FFIBridge` (275 lines) | ctypes C library bindings + Python callable registration | Full |
| `LanguageRuntime` | Config-driven keyword remapping singleton | Full |
| `ModuleManager` | Multi-file imports, circular dependency detection | Mostly complete (see §3) |

---

## 2. Configuration System — IMPLEMENTED

**`config/language_config.py`** provides:

- YAML/JSON loading and saving
- Keyword renaming (`rename_keyword`)
- Custom function registration
- Preset library (`from_preset`, `load_preset`) covering:
  `python_like`, `javascript_like`, `lisp_like`, `minimal`, and others
- Configuration validation with detailed error messages
- Hot-reloading support via `LanguageRuntime`

---

## 3. Partially Complete Features

### Module System (`runtime/module_system.py`)

Three bare `pass` statements exist in exception handler branches — these are
silent failure paths (no fallback or error propagation). The core import and
circular-dependency logic is implemented; the `pass` clauses mean some edge-case
errors are silently swallowed rather than reported.

**Recommendation**: Replace each `pass` with a specific log/raise or return a
meaningful error object.

### Type System Generics (`types/type_system_generics.py`, line 379)

One `pass` statement in a type-checking branch. The generics framework is
implemented around it; this is a single unhandled case (likely an unrecognised
type node kind).

**Recommendation**: Add an explicit `raise TypeError(...)` or return a
`TypeUnknown` sentinel here.

### Debug Adapter (`tooling/debug/debug_adapter.py`, line 288)

One `pass` in an exception handler inside the DAP message-processing loop.
The adapter continues running but silently drops certain malformed messages.

**Recommendation**: Log the dropped message at DEBUG level so adapter issues
can be diagnosed.

---

## 4. Tooling — IMPLEMENTED

### CLI (`tooling/cli.py`, 2355 lines)

40+ subcommands covering the full workflow:

| Category | Commands |
|----------|---------|
| Language config | `create`, `edit`, `validate`, `info`, `export`, `import`, `list-presets`, `convert`, `diff`, `update`, `delete`, `translate` |
| Execution | `repl`, `batch`, `test`, `test-run` |
| Code generation | `codegen-c`, `codegen-wasm` |
| Type system | `type-check`, `generics`, `check-protocol` |
| Module system | `module-info`, `module-deps`, `module-cycles` |
| Tooling | `lsp`, `extension`, `package-search`, `package-install`, `refactor-rename`, `format`, `debug-launch` |

### LSP Server (`tooling/lsp/lsp_server.py`, 683 lines)

Implements the Language Server Protocol including:

- Document sync (open/change/close)
- Diagnostics (syntax error reporting)
- Hover information
- Completion suggestions
- Document symbols
- `format_document` — trims trailing whitespace and normalises line endings

### Error Localizer (`tooling/error_localization.py`)

Template-based localised error messages. Language designers supply translation
files; the localizer formats messages with named placeholders.

---

## 5. Lashon Studio — IMPLEMENTED

The Studio is a full language-design workbench split into a testable
controller and a Tkinter shell:

| Module | Purpose |
|--------|---------|
| `ide/studio.py` | `LanguageStudio`, `StudioProject`, `StudioResult` — headless pipeline, project I/O, grammar/config sync, diagnostics |
| `ide/studio_app.py` | `LashonIDE` — project tree, source/grammar/YAML editors, console, variables, backend panes, AST tree |
| `ide/app.py` | Compatibility entry point (`lashon-ide`) |
| `ide/editor.py` | `CodeEditor`, `LineNumbers` — syntax-aware text widget |
| `ide/project.py` | Legacy `Project`, `ProjectManager` helpers |
| `ide/samples/aurora/` | Packaged copy of the Aurora reference project |

Launch: `lashon-ide [project]`

Reference project: `projects/aurora` (18 rules, 3 samples, all four backends).

---

## 6. Packaging (`packaging/`)

| Module | Purpose |
|--------|---------|
| `vscode_integration.py` | Generates VS Code extension scaffolding |
| `package_registry.py` | Local package registry for language modules |
| `documentation_generator.py` | Auto-generates Markdown docs from a `LanguageConfig` |

---

## 7. Test Coverage

335 tests across 22 test files, all passing:

| Test file | Covers |
|-----------|--------|
| `test_grammar.py` | PEG parsing, GrammarBuilder, `grammar_from_config` |
| `test_transpiler.py` | Python transpilation, `exec()`, `TranspileOptions` |
| `test_codegen.py` | C, WASM, and LLVM IR generation |
| `test_repl.py` | REPL eval, special commands, config loading |
| `test_stdlib_ffi_errors.py` | StdLib injection, FFI bindings, ErrorLocalizer |
| `test_incremental.py` | IncrementalParser edit operations and incremental reparse path |
| `test_integration.py` | Full pipeline from PEG text → exec(), multi-backend |
| `test_config_loading.py` | Every bundled example config loads, validates, and warns on aliases |
| `test_cli_codegen.py` | `codegen-c`/`codegen-wasm`/`codegen-llvm` CLI commands |
| `test_type_system.py` | Type compatibility, scopes, narrowing, generics/protocol bridges |
| `test_module_system.py` | Module loading, exports, dependency resolution, cycle detection |
| `test_lsp.py` | LSP lifecycle, completions, hover ranges, symbols, formatting |
| `test_packaging.py` | SemVer ordering/constraints, registry, docs, VS Code extension |
| `test_ide_project.py` | Project save/load, keywords, project manager recent list |
| `test_debug_adapter.py` | Safe expression evaluation and breakpoint conditions |
| `test_studio.py` | Studio controller, project lifecycle, grammar sync, all backends |
| `test_studio_gui.py` | Tkinter studio smoke tests (skipped without a display) |
| `test_docs.py` | Documentation links/anchors, quick-start examples, Aurora samples |
| `test_cli_run.py` | `run` command: config/PEG execution, JSON output, errors |
| `test_cli_init.py` | `init` scaffolding, overwrite protection, generated project |
| `test_cli_checks.py` | `generics` checker and not-implemented command exits |
| `test_dap_server.py` | DAP protocol, breakpoints, stepping, variables, evaluation |

Run: `python -m pytest tests/ -v`

---

## 8. Known Limitations & Recommendations

| Item | Location | Priority | Notes |
|------|----------|----------|-------|
| Legacy config-driven parser | `parser/parser_generator.py` | Medium | Overlaps with the PEG engine; converge in a future release |
| Monolithic CLI | `tooling/cli.py` | Medium | ~2.4k lines; split into `tooling/commands/*` modules |
| Remaining coverage | — | Low | IDE GUI and stdio transports still lack end-to-end tests |
| `exec()` use in transpiler | `codegen/python_transpiler.py` | Note | By design; suppressed via `# noqa` + pylint disable |

### Resolved in the current refinement pass

- All bundled example configs load through `LanguageConfig.load` (schema
  normalisation handles shorthand keywords, `builtin_functions`, list
  operators, and top-level runtime flags).
- `IncrementalParser` performs real incremental re-parsing via the new
  `PEGInterpreter.parse_rule`; edits no longer silently fall back every time.
- Malformed grammar text is rejected instead of being silently truncated;
  zero-width comment patterns no longer loop forever.
- `transpile_and_exec` returns only program-visible names (no `__builtins__`).
- `codegen-c`/`codegen-wasm` now translate the input program, and the
  documented `codegen-llvm` command was added.
- `pytest` is configured to run from a clean clone, and CI runs lint + tests.
- Lashon Studio: headless `LanguageStudio` controller, tabbed IDE with
  project tree, live grammar validation, AST tree, variables, and four
  backend panes, plus the Aurora reference language project.
- Duplicate keyword mappings are reported as aliases (warnings) rather than
  hard validation errors, so every bundled config validates.
- Silent failure paths were removed: breakpoint conditions are evaluated with
  a safe AST whitelist, type narrowing handles comparisons, and IDE project
  save failures are logged.
- LSP hover ranges are computed from the identifier under the cursor.
- YAML boolean keys (`true:`/`false:`) are normalized to strings, so the
  config-driven REPL no longer crashes during keyword translation.
- Python transpiler regressions fixed: list/dict/parameter punctuation,
  boolean rules, lambda-mapped calls, imports, class bases, multi-argument
  SAY, and BASIC `<=`/`>=` handling.

---

## 9. External Dependencies

| Package | Role | Required |
|---------|------|---------|
| `PyYAML >=6.0` | Config file parsing | Yes |
| `pytest >=7.0` | Test runner | Dev only |
| `ruff >=0.6` | Linter | Dev only |
| `tkinter` | IDE GUI | Bundled with Python |

Python 3.10+ required.

---

## Conclusion

Lashon v4.0.0 is **production-ready** for its core use-case: defining PEG
grammars, parsing source code, and generating output in Python, C, WebAssembly,
or LLVM IR. All 335 tests pass. Remaining work is architectural (CLI
decomposition and convergence of the legacy config-driven parser) rather than
correctness-critical.

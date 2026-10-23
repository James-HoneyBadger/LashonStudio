# Changelog

All notable changes to ParserCraft. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Modular core**: `parser/grammar.py` split into `model` / `peg_parser` /
  `interpreter` / `builder` / `defaults`; `python_transpiler.py` split into
  `codegen/python/{transpiler,statements,control_flow,expressions}`;
  `tooling/cli.py` split into `cli/{parser,dispatch}`; presets extracted to
  `config/presets.py`. Every historical import path still works.
- **`parsercraft.ast`** now owns `SourceAST`, removing the
  `parser` ⇄ `codegen` import cycle; `ast_integration` moved to
  `codegen/ast_integration.py` (shim kept).
- **Layering is enforced** by `tests/test_architecture.py`: core may not import
  runtime/adapters, adapters may not import Tk from `tooling`, no package
  cycles, `__all__` required.
- **Wheel contents fixed**: package discovery is restricted to
  `parsercraft*`, so the stray top-level `codex` package (1,090 LOC) is no
  longer shipped. It is deleted, along with the dead
  `runtime/interpreter_generator.py` and `tooling/lsp/lsp_integration.py`.
- **`import parsercraft`** is lazy: ~70-115 ms → ~5 ms.
- **Parser performance**: comment patterns are compiled once and matched
  in place; whitespace skipping no longer slices the source. ~146 → ~315 KB/s
  on the 2,000-line benchmark.

### Added

- **Rust core crate** (`crates/parsercraft-core`): the PEG grammar model, PEG
  text-notation parser, packrat engine, and AST JSON writer, plus PyO3
  bindings behind an optional `python` feature.
- **`parsercraft-rs` binary** (`crates/parsercraft-cli`): `validate`, `rules`,
  `ast`, `parse`, and `version`, running with no Python installed. Built from
  an enforced Cargo workspace (`cargo build --workspace --release`).
- **Conformance corpus** (`tests/conformance/cases.json`) pinning grammars,
  programs, and exact ASTs/error positions, plus `benchmarks/parse_bench.py`.
- **Optional native PEG engine** (`native/parsercraft-native`, Rust + PyO3),
  built with `scripts/build_native.sh` and selected via
  `PEGInterpreter(grammar, backend="auto"|"native")`. Measured ~5x the Python
  engine for matching and ~1.8x end to end; falls back automatically for
  unsupported grammars.

- **`parsercraft doctor`** — environment diagnostics (Python, PyYAML, entry
  points, Tk/display, gcc/clang, wasmtime, writable directories) with `--json`
  and `--strict`.
- **`parsercraft lint`** — config + grammar + optional source validation in one
  CI-friendly command with `--json` output.
- **`parsercraft demo`** — guided grammar → AST → Python/C/WASM/LLVM →
  execution tour.
- **`parsercraft play`** — local browser playground (`POST /api/run`,
  `GET /api/health`) showing program output and every backend.
- **`config get|set`** — read and change dotted config keys from the CLI.
- **`validate --json`**, **`diff --exit-code`**, **`format --check`**, and
  **`run --watch`** for scripting and CI pipelines.
- **`init` templates** — `--template aurora|calculator|minimal`, plus
  `--with-vscode` (launch/settings) and `--with-ci` (GitHub Actions workflow).
- **Real parser error positions** — failures report the furthest reached
  position with a source snippet, including trailing-input errors after
  whitespace and comments.
- **LSP grammar diagnostics** — `--grammar` parses documents on
  open/change and publishes exact syntax errors; grammar files get hover,
  definition, references, rename, rule completion, and undefined-rule warnings.
- **Studio UX** — Problems panel with click-to-jump and inline squiggles,
  command palette (`Ctrl+Shift+P`), quick open (`Ctrl+P`), and an `F1`
  shortcut cheat sheet.
- **REPL upgrades** — persisted history for both REPLs, tab completion in the
  grammar REPL, `:doc`, `:backends`, `:save`, and timing toggles.
- **DAP extras** — conditional and hit-count breakpoints, `Watch` scope,
  expandable variables, and `terminate`.
- **Distribution** — PyPI trusted-publishing release workflow, devcontainer,
  and a buildable generated VS Code extension (`tsconfig`, npm scripts,
  bundled `language.yaml`).

- **Documentation site**: MkDocs Material configuration, a landing page, and a
  GitHub Pages workflow (`docs.yml`).
- **`parsercraft init`** — scaffold a runnable language project (config, PEG
  grammar, sample, README, and tests that validate grammar, execution, and all
  backends).
- **`parsercraft run`** — parse and execute a source file against a config or
  PEG grammar, with `--json` variables and `--show-python`.
- **Real LSP stdio protocol** — document open/change/close with published
  diagnostics, hover, document symbols, formatting, signature help, and
  JSON-RPC `-32601` for unknown requests.
- **`generics` checker** — validates generic declarations, duplicates, variance
  markers, instantiation arity, and `--infer` bindings.
- **pytest-backed `test-run`** — runs a project's suite with optional coverage.
- **ParserCraft Studio**: headless `LanguageStudio` controller plus a dark,
  tabbed Tkinter workbench with project tree, source/grammar/language editors,
  console, variables, Python, C, WASM, LLVM IR, and AST panes.
- **Aurora sample language** (`projects/aurora`) with grammar, config, three
  sample programs, README, and a packaged copy for installed wheels.
- **Documentation suite**: quick start, tutorials, language-development guide,
  grammar reference, Studio guide, CLI reference, codegen guide, runtime guide,
  type system, LSP/debugging, packaging, architecture, troubleshooting, and a
  rewritten technical reference.
- `codegen-llvm` CLI command; codegen commands extracted to
  `tooling/commands/codegen.py`.
- `PEGInterpreter.parse_rule` and a working `IncrementalParser` fast path.
- Tests for the Studio (headless + GUI), types, modules, LSP, packaging, debug
  adapter, and config validation.

### Changed

- **Packaging is fully PEP 621**: metadata, entry points, extras (`dev`,
  `release`), and package data live in `pyproject.toml`; the version is
  single-sourced from `parsercraft.__version__`; `setup.py` was removed.
- CI now runs lint, a docs check, Python 3.10–3.14 tests, a coverage gate
  (43%), Windows/macOS smoke tests, and a build + `twine check` packaging job.
- WASM generation now emits functions, locals, calls, `if`/`else`, `while`,
  returns, and integer/string prints, with data-segment strings and a host
  contract (`console.__log_i32`, `console.__log_str`, exported memory).
- `debug-launch` now starts a real TCP DAP server with source-mapped execution,
  line breakpoints, stepping, variables, and evaluation.
- `check-protocol`, `package-search`, and `package-install` now exit 2 with
  guidance instead of printing success.
- `tooling/cli.py` is now a thin parser/registry; command implementations live
  in `tooling/commands/` (`config`, `execution`, `modules`, `tooling`, and the
  single-purpose modules).
- C and LLVM backends share `codegen/common.py` for AST traversal and
  operator-chain splitting (removes duplicated structural-operator logic).
- `run --sandbox` executes in an isolated child process with POSIX resource
  limits and a wall-clock timeout.
- `type-check --json` emits structured diagnostics for editors.
- `PythonTranspiler.translate_source_ast` is the canonical entry point (`transpile`
  remains an alias).
- `transpile_and_exec` filters dunder keys from the returned namespace.
- C backend now emits `else` branches, loop bodies, string format specifiers, and
  avoids re-declaring variables on reassignment.
- LLVM backend now emits function calls, block bodies, `printf` calls, correct
  `i1` comparison typing, and zero-extension on boolean returns.
- WASM backend documentation describes the integer subset and host imports.
- Grammar parser is strict: trailing junk, unclosed groups, and unterminated
  literals/classes raise instead of truncating; zero-width comment patterns can
  no longer loop.
- Configuration loader normalises metadata/top-level keys, boolean-like YAML
  keys, string-or-dict keywords, list-or-dict operator tables, and
  `builtin_functions` aliases; all bundled example configs validate.
- `TypeChecker` recognises numeric literals as literals, reports real line
  numbers, and accepts `True`/`False` as booleans.
- Test suite is runnable without installation (`pythonpath = ["src"]`).

### Fixed

- Duplicate keyword alias validation no longer rejects otherwise valid configs;
  it reports warnings.
- Type narrowing comparisons, DAP breakpoint condition evaluation, IDE project
  save failures, and incremental fallback paths no longer fail silently.
- LSP hover resolves the word at the cursor and rejects negative ranges.
- `Type.is_compatible_with` no longer crashes on empty optionals;
  `TypeChecker(None)` works; SemVer prerelease ordering is correct.
- Transpiler punctuation bugs in parameter/argument/list/dict/print output,
  boolean rules, lambda-mapped calls, imports, class bases, SAY multi-argument
  statement, BASIC `<=`/`>=`, and bare expression statements.

### Removed

- `.backups/ide_backup.py` and the invalid `tkinter` extra in `setup.py`.

## [4.0.0]

- Subpackage layout (`config`, `parser`, `codegen`, `runtime`, `tooling`, `ide`,
  `types`, `packaging`).
- PEG interpreter with packrat memoisation and built-in tokens.
- Python, C, WASM, and LLVM IR generators.
- Config-driven keyword/function/operator translation and presets.
- REPL, stdlib, FFI bridge, module system, error localization.
- LSP analyzer, DAP controller, type system, packaging helpers.

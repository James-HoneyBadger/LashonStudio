# Changelog

All notable changes to ParserCraft. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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

# Changelog

All notable changes to Lashon. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Drawing canvas.** Turtle-style statements (`turtle_move`, `turtle_turn`,
  `turtle_pen`, `turtle_pos`, `cls_stmt`) now record into
  `lashon.runtime.graphics.Graphics` instead of opening Python's `turtle`
  window, so a language can draw anywhere — a display is optional:
  - **Studio**: new **Canvas** tab that repaints after every run and opens
    itself when the program drew something, plus an embedded **REPL** tab
    (Ctrl+R) that evaluates statements against the project grammar and paints
    the canvas after each one.
  - **REPL**: `:canvas`, `:canvas ascii|save FILE|show|clear`, and
    `lashon-repl --canvas` for a live window beside the prompt.
  - **CLI**: `lashon run --canvas out.svg`, `--ascii-canvas`, and a `canvas`
    object in `--json` output.
  - **New project** `projects/logo`: a Logo dialect with four drawing samples,
    wired to the canvas through a declared `source_extension: ".logo"`.
- **Per-project `source_extension`**, so the Studio and `sample_files()` pick up
  samples named `.logo`, `.bas`, or anything else instead of only the built-in
  extension list.
- **CRT-styled Studio** with three palettes (green phosphor, amber, neutral
  dark) selected with `--theme` or `LASHON_THEME`, modelled on the retro
  workbench look of Time Warp Studio but scaled to a language workbench.
  The palette now reaches every surface: editors and gutter, syntax colours,
  menus, tree selections, and the tool bar.
- **Pipeline panel** in the sidebar tracking Grammar → Parse → Run →
  Python/C/WASM/LLVM with live `○ / ✓ / ✗` state.
- **Power-on banner** in the console (`LASHON STUDIO 5.0.0 · CRT SERIES`,
  phosphor, engine, backend list, `READY.`) and a live clock in the status bar.
- **Phosphor page furniture**: box-drawn section rules (`── PIPELINE ───`),
  a shadowed uppercase banner, and monospace subtitles.
- **View → Theme** menu and a persisted `studio.json` preference, so the chosen
  phosphor survives restarts.

### Changed

- **The PyPI distribution is `ParserCraft`; the package is `lashon`.** The
  project keeps its original distribution name for continuity with the
  registry, while imports, commands, and docs stay on `lashon`:

  ```bash
  pip install ParserCraft      # provides `import lashon`, lashon-ide, lashon-repl
  ```

  `parsercraft` remains as the deprecated compatibility shim.

### Fixed

- **Line-numbered programs now run on the Python pipeline.** `lashon run`,
  the Studio, and the REPL emitted each BASIC line number as a bare statement
  and produced `if X > 0:` with no body, so `projects/basic` only worked
  through the Rust core. The Python backend compiles a numbered program into a
  program-counter loop, and `IF … THEN GOTO` becomes a branch that sets it.
  All three BASIC samples now print identical output from the interpreter,
  compiled C, and compiled LLVM IR.
- Rename leftovers in the runtime output: the config-driven REPL banner,
  `ParserGenerator` output, and several module docstrings still said
  "HB Language Construction Set". They now say Lashon Studio, and
  `from lashon.runtime import REPL` is a lazy export so
  `python -m lashon.runtime.repl` no longer trips a re-execution warning.
- Documentation catches up with the rename: INSTALL/PACKAGING no longer mention
  a `codex` entry point, `cd Lashon` became `cd LashonStudio`, and the version
  headers on INSTALL, QUICKSTART, USER_GUIDE, CLI_REFERENCE,
  TECHNICAL_REFERENCE, and the docs index read 5.0.0. A docs test now fails if
  a release bump leaves them behind.
- Added `projects/basic/language.yaml` (grammar + `.bas` samples) so the BASIC
  project opens in the Studio like the others, and the REPL now supplies a
  line number for line-oriented grammars, so `LET X = 1` works in a BASIC
  session instead of demanding `10 LET X = 1`.
- The Rust evaluator implements `break` and `continue` (loops already handled
  them, but nothing ever produced the flow), which also clears the last
  compiler warning.
- **`--theme` now takes effect.** The palette used to be resolved at import
  time, so the flag set the environment variable but the window still opened in
  green. Palettes are resolved per window now, and the choice can also be made
  from **View → Theme** (persisted in `~/.config/lashon/studio.json`).
- The Studio window now sizes itself to the display (capped at 1440×900) and
  keeps a 150 px minimum output pane, so the console and status bar stay
  visible on smaller screens.
- `lashon-ide` on a machine without a display exits with a clear message and
  headless alternatives instead of a Tcl traceback.

## [5.0.0] - renamed to Lashon Studio

### Changed

- **The project is now Lashon Studio** (`lashon` for short). The Python
  package, console scripts, Rust crates, binary, PyO3 module, environment
  variables, docs, and GitHub repository all follow the new name:
  `lashon`, `lashon-ide`, `lashon-repl`, `lashon-rs`, `lashon-core`,
  `lashon-cli`, `LASHON_*`, `James-HoneyBadger/LashonStudio`.
- `pip install lashon`; `import lashon`; `lashon run grammar.peg prog.bas`.

### Added

- **`parsercraft` compatibility shim**: importing the old package emits a
  `DeprecationWarning` and aliases every submodule (`from
  parsercraft.parser import GrammarParser` still works). It is planned to be
  removed in the release after next.

### Removed

- Dead `codex` console script and coverage path, left over from the package
  deleted in 4.0.0.

### Changed — engineering pass

- **Modular core**: `parser/grammar.py` split into `model` / `peg_parser` /
  `interpreter` / `builder` / `defaults`; `python_transpiler.py` split into
  `codegen/python/{transpiler,statements,control_flow,expressions}`;
  `tooling/cli.py` split into `cli/{parser,dispatch}`; presets extracted to
  `config/presets.py`. Every historical import path still works.
- **`lashon.ast`** now owns `SourceAST`, removing the
  `parser` ⇄ `codegen` import cycle; `ast_integration` moved to
  `codegen/ast_integration.py` (shim kept).
- **Layering is enforced** by `tests/test_architecture.py`: core may not import
  runtime/adapters, adapters may not import Tk from `tooling`, no package
  cycles, `__all__` required.
- **Wheel contents fixed**: package discovery is restricted to
  `lashon*`, so the stray top-level `codex` package (1,090 LOC) is no
  longer shipped. It is deleted, along with the dead
  `runtime/interpreter_generator.py` and `tooling/lsp/lsp_integration.py`.
- **`import lashon`** is lazy: ~70-115 ms → ~5 ms.
- **Parser performance**: comment patterns are compiled once and matched
  in place; whitespace skipping no longer slices the source. ~146 → ~315 KB/s
  on the 2,000-line benchmark.

### Added — engineering pass

- **BASIC sample project** (`projects/basic`): a line-numbered dialect defined
  only by a grammar — `LET`, `PRINT`, `IF/THEN/ELSE`, `GOTO`, `WHILE/WEND`,
  `REM`, `END`. The Rust evaluator gained a program counter for numbered
  programs, `GOTO`, single-statement `IF` branches, and the `= <>` comparison
  operators, so the dialect actually runs.

- **Python backend in Rust** (`backends/python.rs`): emit-only Python source
  for assignments, prints, functions, `if`/`else`, `while`, returns, and
  arithmetic; `lashon-rs codegen-py ... [--run]`. Generated code executes
  with the same output as the Python transpiler on every Aurora sample.
- **C backend in Rust** (`crates/lashon-core/src/backends/c.rs`): emits
  assignments, prints, functions, `if`/`else`, `while`, returns, and arithmetic;
  `lashon-rs codegen-c ... [--compile] [--run]` builds and runs a program
  with no Python installed. All three Aurora samples produce byte-identical
  program output to the Python backend.
- **Rust core crate** (`crates/lashon-core`): the PEG grammar model, PEG
  text-notation parser, packrat engine, and AST JSON writer, plus PyO3
  bindings behind an optional `python` feature.
- **`lashon-rs` binary** (`crates/lashon-cli`): `validate`, `rules`,
  `ast`, `parse`, and `version`, running with no Python installed. Built from
  an enforced Cargo workspace (`cargo build --workspace --release`).
- **Conformance corpus** (`tests/conformance/cases.json`) pinning grammars,
  programs, and exact ASTs/error positions, plus `benchmarks/parse_bench.py`.
- **Optional native PEG engine** (`native/lashon-native`, Rust + PyO3),
  built with `scripts/build_native.sh` and selected via
  `PEGInterpreter(grammar, backend="auto"|"native")`. Measured ~5x the Python
  engine for matching and ~1.8x end to end; falls back automatically for
  unsupported grammars.

- **`lashon doctor`** — environment diagnostics (Python, PyYAML, entry
  points, Tk/display, gcc/clang, wasmtime, writable directories) with `--json`
  and `--strict`.
- **`lashon lint`** — config + grammar + optional source validation in one
  CI-friendly command with `--json` output.
- **`lashon demo`** — guided grammar → AST → Python/C/WASM/LLVM →
  execution tour.
- **`lashon play`** — local browser playground (`POST /api/run`,
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
- **`lashon init`** — scaffold a runnable language project (config, PEG
  grammar, sample, README, and tests that validate grammar, execution, and all
  backends).
- **`lashon run`** — parse and execute a source file against a config or
  PEG grammar, with `--json` variables and `--show-python`.
- **Real LSP stdio protocol** — document open/change/close with published
  diagnostics, hover, document symbols, formatting, signature help, and
  JSON-RPC `-32601` for unknown requests.
- **`generics` checker** — validates generic declarations, duplicates, variance
  markers, instantiation arity, and `--infer` bindings.
- **pytest-backed `test-run`** — runs a project's suite with optional coverage.
- **Lashon Studio**: headless `LanguageStudio` controller plus a dark,
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
  single-sourced from `lashon.__version__`; `setup.py` was removed.
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

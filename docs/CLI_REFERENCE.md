# CLI Reference

The `parsercraft` command covers language configuration, execution, code
generation, modules, types, editor tooling, and packaging helpers.

```bash
parsercraft <command> [options]
parsercraft --version        # parsercraft 4.0.0
parsercraft --help
```

Without installation, run the module form:

```bash
python -m parsercraft.tooling.cli <command> [options]
```

Exit codes: `0` success, `1` failure (the message is printed to stdout/stderr).
Commands do not raise tracebacks unless `--debug` is requested.

---

## Maturity at a glance

Some commands are complete; some are scaffolding. This table is deliberately
explicit.

| Status | Commands |
|---|---|
| **Stable** | `init`, `create`, `edit`, `validate`, `config`, `lint`, `doctor`, `demo`, `play`, `info`, `export`, `import`, `convert`, `diff`, `update`, `delete`, `list-presets`, `run`, `repl`, `batch`, `translate`, `extension`, `codegen-c`, `codegen-wasm`, `codegen-llvm`, `module-info`, `module-deps`, `module-cycles`, `generics`, `test-run`, `refactor-rename`, `format` |
| **Functional, heuristic** | `type-check` (pattern-based), `lsp` (stdio protocol with real grammar diagnostics), `test` (config-driven harness), `debug-launch` (DAP: breakpoints, conditions, stepping, watches) |
| **Not implemented (exit 2)** | `check-protocol`, `package-search`, `package-install` |

Placeholders print a clear message and exit 0; they do not silently corrupt
anything. Use the Python APIs documented in
[TYPE_SYSTEM.md](TYPE_SYSTEM.md) and [PACKAGING.md](PACKAGING.md) for those
features today.

---

## Global options

| Option | Meaning |
|---|---|
| `-h`, `--help` | command help |
| `--version` | print version and exit |

Many commands accept `--debug` (`-d`) to print tracebacks.

---

## Language configuration

### `init`

```bash
parsercraft init NAME [--directory DIR] [--force]
                     [--template aurora|calculator|minimal]
                     [--with-vscode] [--with-ci]
```

Scaffolds a runnable language project:

```
<slug>/
├── language.yaml     # metadata, keywords, grammar.rules
├── grammar.peg       # editable PEG grammar
├── samples/*.aur     # runnable examples
├── README.md
└── tests/test_<slug>.py
```

| Option | Meaning |
|---|---|
| `--directory`, `-d` | parent directory (default: current directory) |
| `--force` | replace a non-empty target directory |
| `--template`, `-t` | starting grammar: `aurora` (default, full language), `calculator` (arithmetic), `minimal` (assignments + print) |
| `--with-vscode` | add `.vscode/launch.json` and `settings.json` |
| `--with-ci` | add a GitHub Actions workflow that lints, validates, and runs the sample |

```bash
parsercraft init "Pocket Calc" -t calculator --with-vscode --with-ci
```

The generated test file validates the grammar, runs the sample, and generates
every backend, so `python -m pytest tests -q` is the first thing to run.

```bash
parsercraft init "Tiny Lang" --directory ./languages
cd languages/tiny-lang && python -m pytest tests -q
```

### `create`

```bash
parsercraft create [--preset PRESET] [--interactive] [--output FILE]
```

| Option | Description |
|---|---|
| `--preset PRESET` | start from a preset (see `list-presets`) |
| `--interactive`, `-i` | prompt for name, preset, options |
| `--output`, `-o` | output file (default `language_config.yaml`) |

```bash
parsercraft create --preset python_like --output my_lang.yaml
parsercraft create --interactive
```

### `edit`

```bash
parsercraft edit FILE
```

Opens the config in `$EDITOR`/platform default.

### `validate`

```bash
parsercraft validate FILE [--grammar] [--json]
```

Loads the config, runs `LanguageConfig.validate()`, prints errors and alias
warnings, and exits non-zero on hard errors. `--grammar` also parses the PEG
rules. `--json` emits a machine-readable report for CI:

```bash
parsercraft validate language.yaml --grammar --json | jq .ok
```

### `lint`

```bash
parsercraft lint FILE [--source FILE] [--json]
```

One command for CI: validates the config, parses every grammar rule, and
optionally type-checks a source file. Exits 1 when anything fails.

### `config`

```bash
parsercraft config get FILE KEY [--output FILE]
parsercraft config set FILE KEY VALUE [--output FILE]
```

Reads or changes a single dotted key without hand-editing YAML. Values are
parsed as JSON when possible, otherwise stored as strings.

```bash
parsercraft config get language.yaml grammar.start
parsercraft config set language.yaml syntax_options.require_semicolons false
```

### `doctor`

```bash
parsercraft doctor [--json] [--strict]
```

Checks the environment: Python version, PyYAML, console entry points,
Tkinter/display availability, `gcc`/`clang`, `wasmtime`, and writable config
directories. Each failure comes with an actionable fix. `--strict` makes
warnings fail the command, which is useful in CI.

### `demo`

```bash
parsercraft demo [--no-backends]
```

Runs a guided tour on a built-in grammar: parse → AST → Python → C → WASM →
LLVM IR → execution. Ideal for a first look without creating files.

```bash
parsercraft validate projects/aurora/language.yaml
```

### `info`

```bash
parsercraft info [FILE]
```

Without a file, shows the current runtime configuration. With a file, shows
metadata, counts, keywords, functions, and operators.

### `export`

```bash
parsercraft export FILE [--format {markdown,json,yaml}] [--output FILE]
```

```bash
parsercraft export my_lang.yaml --format markdown --output reference.md
```

### `import`

```bash
parsercraft import FILE [--scope {runtime,project,user}]
```

Applies a config to the runtime, a project `.langconfig`, or the user config at
`~/.langconfig`.

### `convert`

```bash
parsercraft convert FILE --to {json,yaml} [--from FORMAT] [--output FILE]
```

```bash
parsercraft convert my_lang.yaml --to json
```

### `diff`

```bash
parsercraft diff FILE1 FILE2 [--exit-code]
```

`--exit-code` exits 1 when the two configurations differ, so the command can
gate a pipeline. Output lists added, removed, and changed keys and mappings.

### `update`

```bash
parsercraft update FILE [--set KEY VALUE]... [--merge FILE] [--output FILE]
```

`KEY` is dotted (`metadata.author`, `syntax_options.single_line_comment`).
Values are parsed as JSON when possible, and `--set` may be repeated.

```bash
parsercraft update my_lang.yaml --set metadata.author "Your Name"
parsercraft update my_lang.yaml --merge overrides.yaml --output merged.yaml
```

### `delete`

```bash
parsercraft delete FILE [--keyword KW ...] [--function FN ...] [--operator OP ...] [--output FILE]
```

### `list-presets`

```bash
parsercraft list-presets
```

Current presets:

`python_like`, `js_like`, `minimal`, `ruby_like`, `golang_like`, `rust_like`,
`clike`, `functional`, `lisp_like`, `basic_like`.

---

## Execution

### `play`

```bash
parsercraft play [PROJECT] [--port 8000] [--host 127.0.0.1] [--open]
```

Serves a browser playground for a project: edit source on the left, press
Run, and inspect program output plus the generated Python, C, WASM, and LLVM
IR. The page talks to `POST /api/run`; `GET /api/health` is available for
readiness checks.

### `run`

```bash
parsercraft run FILE [--config CONFIG | --grammar GRAMMAR]
                     [--json] [--show-python] [--watch]
```

Parses `FILE` with the supplied grammar and executes the transpiled Python.

| Option | Meaning |
|---|---|
| `--config`, `-c` | language config whose `grammar.rules` defines the language |
| `--grammar`, `-g` | PEG file; overrides `--config` |
| `--json` | print `{"variables": {...}}` to stdout; program output goes to stderr |
| `--show-python` | print generated Python to stderr before running |
| `--sandbox` | run in an isolated subprocess with CPU/memory/file limits (POSIX) |
| `--sandbox-timeout` | wall-clock timeout for sandbox mode (default 10s) |
| `--watch` | re-run whenever the program, config, or grammar changes |

A grammar is required; without `--config`/`--grammar` the command exits 1.
Exit code is 1 for parse, IO, and runtime errors.

```bash
parsercraft run projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml

parsercraft run program.aur --grammar grammar.peg --json
# {"variables": {"x": 21, "y": 42}}

parsercraft run program.aur --config lang.yaml --sandbox
```

`--watch` polls file modification times every 0.5 s and re-runs on change;
press Ctrl+C to stop.

`--sandbox` launches a child `python -I` process in a temporary directory with
`RLIMIT_CPU` (5s), `RLIMIT_AS` (512 MB), `RLIMIT_NOFILE`, and `RLIMIT_FSIZE`.
It is process isolation, **not** a security sandbox: the child can still read
files and open sockets. `--json` is rejected in sandbox mode.

### `repl`

```bash
parsercraft repl [FILE] [--grammar GRAMMAR] [--debug]
```

| Mode | Behaviour |
|---|---|
| `repl` | default config, config-driven |
| `repl my_lang.yaml` | config-driven keyword translation |
| `repl --grammar my.peg` | PEG interpreter with AST inspection |

Command sets differ:

- **Config-driven REPL:** `.help`, `.info`, `.keywords`, `.functions`, `.vars`,
  `.clear`, `.debug`, `.time`, `.save FILE`, `.exit`.
- **Grammar REPL (`--grammar`):** `:help`, `:ast`, `:py`, `:vars`, `:grammar`,
  `:load`, `:save`, `:doc RULE`, `:backends`, `:time`, `:reset`, `:quit`.

Both REPLs persist history (`~/.parsercraft_repl_history`,
`~/.parsercraft_history`). The grammar REPL also offers tab completion for
commands, rule names, and common builtins. `:backends` prints C, WASM, and
LLVM IR for the last successful parse.

```bash
parsercraft repl --grammar mini.peg
parsercraft repl configs/examples/pascal_like.yaml
```

### `batch`

```bash
parsercraft batch CONFIG [--script FILE] [--input-dir DIR] [--output-dir DIR]
                 [--pattern GLOB] [--show-translation] [--show-vars] [--debug]
```

Runs a script or processes matching files through the config-driven translator.

```bash
parsercraft batch my_lang.yaml --input-dir ./programs --pattern "*.txt" \
  --output-dir ./out --show-vars
```

### `test`

```bash
parsercraft test --config CONFIG --tests CASES [--show-translation]
                 [--stop-on-fail] [--debug]
```

`CASES` is a YAML/JSON list of test cases consumed by the built-in harness.
See `parsercraft.tooling.test_framework.TestCase` for the schema.

### `translate`

```bash
parsercraft translate --config CONFIG --input SRC [--output FILE]
```

Translates custom keywords back to their originals (one pass).

```bash
parsercraft translate --config espanol.yaml --input program.txt
```

---

## Code generation

```bash
parsercraft codegen-c    FILE [--config CONFIG] [--output FILE]
parsercraft codegen-wasm  FILE [--config CONFIG] [--output FILE]
parsercraft codegen-llvm  FILE [--config CONFIG] [--output FILE]
```

- `--config` must point to a language config containing `grammar.rules`.
- Without `--config`, the built-in default grammar is used.
- Default outputs: `.c`, `.wat`, `.ll`.

```bash
parsercraft codegen-c projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fib.c
```

These commands emit source; they do not invoke a C/WASM/LLVM toolchain.

---

## Modules

```bash
parsercraft module-info   MODULE [--module-dir DIR]
parsercraft module-deps   MODULE [--module-dir DIR]
parsercraft module-cycles [--module-dir DIR]
```

Module files are discovered by name with extensions `.teach`, `.lang`,
`.script`, `.txt`, or no extension. Syntax supports `import module`,
`import module as alias`, `import {a, b} from module`, `import module version
"^1.0.0"`, and `export function|const|class name`.

```bash
parsercraft module-info utils --module-dir ./modules
parsercraft module-deps main --module-dir ./modules
parsercraft module-cycles --module-dir ./modules
```

Full semantics: [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#module-system).

---

## Type and protocol analysis

### `type-check`

```bash
parsercraft type-check --config CONFIG --input SRC
                       [--level {lenient,moderate,strict,very-strict}]
                       [--warnings-as-errors] [--json] [--debug]
```

Runs `TypeChecker.check_file`, a **heuristic** analyzer (see
[TYPE_SYSTEM.md](TYPE_SYSTEM.md)). It is useful for simple annotations, not a
full static type checker.

`--json` prints a machine-readable payload for editors:

```json
{"file": "program.src", "level": "strict",
 "diagnostics": [{"code": "E101", "message": "...", "line": 2,
                  "column": 0, "location": "program.src",
                  "suggestion": "..."}]}
```

Exit code is 1 when diagnostics are reported.

```bash
parsercraft type-check --config my_lang.yaml --input program.src --level strict
parsercraft type-check -c my_lang.yaml -i program.src --json
```

### `generics` and `check-protocol`

```bash
parsercraft generics FILE [--check-variance] [--infer]
parsercraft check-protocol FILE [--list-protocols] [--protocol NAME]
```

`generics` scans declarations (`class Box[T]`, `def identity[T]`) and
instantiations, checking parameter identifiers, duplicate parameters, and arity.
`--infer` prints the inferred parameter binding; `--check-variance` rejects
variance markers on functions. It is a source-text checker, not a full type
inference engine — see [TYPE_SYSTEM.md](TYPE_SYSTEM.md) for the underlying
`GenericChecker`/`GenericsTypeChecker` APIs.

`check-protocol` exits 2: protocol conformance needs a language-specific type
model. Use `ProtocolChecker` directly.

---

## Editor and developer tooling

### `lsp`

```bash
parsercraft lsp --config CONFIG [--grammar GRAMMAR] [--port PORT] [--stdio]
```

Starts the LSP server. `--stdio` is the supported transport; socket mode exits
with code 2. The stdio loop serves `initialize`, `initialized`, `shutdown`,
`exit`, `textDocument/didOpen|didChange|didClose` (publishing diagnostics),
`textDocument/completion|hover|definition|references|rename|documentSymbol|formatting|signatureHelp`,
and answers unknown requests with JSON-RPC `-32601`. See
[LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md).

`--grammar` (default: `grammar.peg` next to the config) enables real syntax
diagnostics: every `didOpen`/`didChange` parses the document with the PEG
grammar and publishes the exact error position. When the open document *is*
the grammar file, the server switches to grammar intelligence — rule hover,
go-to-definition, references, rename, rule completion, and undefined-rule
warnings.

```bash
parsercraft lsp --config my_lang.yaml --stdio
parsercraft lsp --config projects/aurora/language.yaml \
  --grammar projects/aurora/grammar.peg --stdio
```

### `extension`

```bash
parsercraft extension --config CONFIG [--output DIR]
                     [--publisher NAME] [--version VERSION]
```

Generates a buildable VS Code extension: `package.json` (with
`compile`/`watch` scripts and `vscode-languageclient`), `tsconfig.json`,
`extension.ts`, the TextMate grammar, `language-configuration.json`,
`language.yaml` (shipped so the server can start), README, and
`.vscodeignore`.

The generated client launches `parsercraft lsp --config language.yaml --stdio`,
so install ParserCraft wherever the extension runs. Build it with:

```bash
cd <output> && npm install && npm run compile && npx vsce package
```

```bash
parsercraft extension --config projects/aurora/language.yaml \
  --output ./aurora-vscode --publisher my-org --version 1.0.0
```

### `refactor-rename`

```bash
parsercraft refactor-rename FILE OLD NEW [--output FILE]
```

Renames identifiers using the refactoring engine; writes in place unless
`--output` is given.

### `format`

```bash
parsercraft format FILE [--output FILE] [--tab-size N] [--in-place] [--check]
```

Minimal formatter (indentation/whitespace). Without `--output` or `--in-place`,
prints to stdout. `--check` writes nothing and exits 1 when the file would
change, which makes it usable as a CI gate.

### `debug-launch`

```bash
parsercraft debug-launch FILE [--port PORT] [-b/--breakpoint LINE]...
                            [--config CONFIG | --grammar GRAMMAR]
```

Starts a DAP server over TCP (default port 5678) that compiles the program,
runs it, and honors line breakpoints, conditional and hit-count breakpoints,
stepping, expandable variables, watch expressions, and evaluation.
`--breakpoint` seeds breakpoints before a client connects. See
[LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md#debug-adapter-dap).

### `test-run`

```bash
parsercraft test-run [PATH] [--verbose] [--coverage]
```

Runs `pytest` on `PATH` (default `tests`). `--verbose` adds `-v`;
`--coverage` adds `--cov --cov-report=term-missing` and requires `pytest-cov`.
The command returns pytest's exit code.

```bash
parsercraft test-run tests -v
```

---

## Packaging helpers

### `package-search`

```bash
parsercraft package-search QUERY [--registry REGISTRY]
```

Exits 2: there is no remote registry backend. Use
`parsercraft.packaging.PackageRegistry` with locally registered packages.

### `package-install`

```bash
parsercraft package-install PACKAGE[@VERSION] [--registry REGISTRY] [--save]
```

Exits 2: packages are resolved from a local `PackageRegistry` only. Use
`PackageRegistry` (`resolve`, `resolve_dependencies`, `create_lock_file`)
directly; see [PACKAGING.md](PACKAGING.md).

---

## Rust front end (`parsercraft-rs`)

A second, dependency-free binary built from `crates/parsercraft-cli`. It runs
with no Python installed and covers the commands that only need the grammar
engine:

```bash
cargo build --workspace --release      # or: cargo install --path crates/parsercraft-cli

parsercraft-rs validate grammar.peg     # rules, start rule, undefined-rule warnings
parsercraft-rs rules grammar.peg        # one rule name per line
parsercraft-rs ast grammar.peg prog.aur # pretty JSON AST
parsercraft-rs parse grammar.peg prog.aur  # exit 0/1, prints the first error
parsercraft-rs run grammar.peg prog.aur    # executes natively, prints program output
parsercraft-rs codegen-c grammar.peg prog.aur -o prog.c [--compile] [--run]
parsercraft-rs codegen-py grammar.peg prog.aur -o prog.py [--run]
parsercraft-rs version
```

`codegen-c` is a full AST → C generator (assignments, prints, functions,
`if`/`else`, `while`, arithmetic). `--compile` invokes `cc -std=c99` and
`--run` executes the binary, so a project can be built with no Python:

```bash
parsercraft-rs codegen-c grammar.peg samples/fizzbuzz.aur -o fizzbuzz.c --run
```

`validate` exits 1 when the grammar cannot be parsed; `parse` exits 1 on a
syntax error and prints the same message shape as the Python engine
(`Parse error at line N, column M (in rule 'x'): ...`). `codegen-py` emits Python source for the same constructs; `--run` executes it
with `python3` (or `$PYTHON`). Both backends are checked against the Python
pipeline in `tests/test_rust_cli.py`.

The WASM and LLVM backends and the editor tooling are still Python-only.

---

## Examples by task

| Task | Command |
|---|---|
| Scaffold a language project | `parsercraft init "My Lang"` |
| Create a Spanish Python | `parsercraft create --preset python_like` then `rename_keyword` in Python or edit YAML |
| Check a config | `parsercraft validate my_lang.yaml` |
| Lint config + grammar + source | `parsercraft lint lang.yaml --source prog.aur` |
| Diagnose the environment | `parsercraft doctor` |
| See the whole pipeline | `parsercraft demo` |
| Open a browser playground | `parsercraft play . --open` |
| Change one setting | `parsercraft config set lang.yaml grammar.start program` |
| Explore presets | `parsercraft list-presets` |
| Run a program | `parsercraft run program.aur -g grammar.peg` |
| Run a grammar REPL | `parsercraft repl --grammar my.peg` |
| Run a config REPL | `parsercraft repl my_lang.yaml` |
| Emit C from a grammar config | `parsercraft codegen-c src.aur --config lang.yaml` |
| Generate a VS Code extension | `parsercraft extension --config lang.yaml` |
| Inspect module dependencies | `parsercraft module-deps main --module-dir ./lib` |
| Start the LSP (stdio) | `parsercraft lsp --config lang.yaml --stdio` |

---

## See also

- [USER_GUIDE.md](USER_GUIDE.md) — task-oriented usage.
- [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — backend details.
- [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md) — REPL, stdlib, FFI, modules.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — command failures.

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
| **Stable** | `init`, `create`, `edit`, `validate`, `info`, `export`, `import`, `convert`, `diff`, `update`, `delete`, `list-presets`, `run`, `repl`, `batch`, `translate`, `extension`, `codegen-c`, `codegen-wasm`, `codegen-llvm`, `module-info`, `module-deps`, `module-cycles`, `generics`, `test-run`, `refactor-rename`, `format` |
| **Functional, heuristic** | `type-check` (pattern-based), `lsp` (stdio protocol), `test` (config-driven harness), `debug-launch` (DAP subset) |
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
```

Scaffolds a runnable language project:

```
<slug>/
├── language.yaml     # metadata, keywords, grammar.rules
├── grammar.peg       # editable PEG grammar
├── samples/hello.aur # first program
├── README.md
└── tests/test_<slug>.py
```

`--force` replaces a non-empty target directory (default is to refuse).
`--directory` selects the parent (default: current directory).

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
parsercraft validate FILE
```

Loads the config, runs `LanguageConfig.validate()`, prints errors and alias
warnings, and exits non-zero on hard errors.

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
parsercraft diff FILE1 FILE2
```

Reports added/removed/changed keys and mappings.

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

### `run`

```bash
parsercraft run FILE [--config CONFIG | --grammar GRAMMAR]
                     [--json] [--show-python]
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

A grammar is required; without `--config`/`--grammar` the command exits 1.
Exit code is 1 for parse, IO, and runtime errors.

```bash
parsercraft run projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml

parsercraft run program.aur --grammar grammar.peg --json
# {"variables": {"x": 21, "y": 42}}

parsercraft run program.aur --config lang.yaml --sandbox
```

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
  `.clear`, `.debug`, `.exit`.
- **Grammar REPL (`--grammar`):** `:help`, `:ast`, `:py`, `:vars`, `:grammar`,
  `:load`, `:reset`, `:quit`.

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
parsercraft lsp --config CONFIG [--port PORT] [--stdio]
```

Starts the LSP server. `--stdio` is the supported transport; socket mode exits
with code 2. The stdio loop serves `initialize`, `initialized`, `shutdown`,
`exit`, `textDocument/didOpen|didChange|didClose` (publishing diagnostics),
`textDocument/completion|hover|documentSymbol|formatting|signatureHelp`, and
answers unknown requests with JSON-RPC `-32601`. See
[LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md).

```bash
parsercraft lsp --config my_lang.yaml --stdio
```

### `extension`

```bash
parsercraft extension --config CONFIG [--output DIR]
                     [--publisher NAME] [--version VERSION]
```

Generates a VS Code extension (`package.json`, TextMate grammar,
`language-configuration.json`, README).

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
parsercraft format FILE [--output FILE] [--tab-size N] [--in-place]
```

Minimal formatter (indentation/whitespace). Without `--output` or `--in-place`,
prints to stdout.

### `debug-launch`

```bash
parsercraft debug-launch FILE [--port PORT] [-b/--breakpoint LINE]...
                            [--config CONFIG | --grammar GRAMMAR]
```

Starts a DAP server over TCP (default port 5678) that compiles the program,
runs it, and honors line breakpoints, stepping, variables, and evaluation.
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

## Examples by task

| Task | Command |
|---|---|
| Scaffold a language project | `parsercraft init "My Lang"` |
| Create a Spanish Python | `parsercraft create --preset python_like` then `rename_keyword` in Python or edit YAML |
| Check a config | `parsercraft validate my_lang.yaml` |
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

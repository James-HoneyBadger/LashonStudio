# Architecture

ParserCraft is a Python framework for defining languages with PEG grammars,
parsing source into an AST, and generating output for several targets. This
page describes how the pieces fit together so you can extend them safely.

Version 4.0.0, ~20,800 lines of library code, 371 tests.

---

## Pipeline

```
language.yaml / grammar.peg
        │
        ├── LanguageConfig ──────────────► config-driven runtime
        │        (keywords, functions, operators, syntax options)
        │
        └── GrammarParser ──► Grammar (rules of PEGNode)
                                  │
source text ──────────────────────┤
                                  ▼
                          PEGInterpreter
                          (packrat matching, memoised)
                                  │
                                  ▼
                             SourceAST
                                  │
        ┌─────────────┬───────────┼───────────┬─────────────┐
        ▼             ▼           ▼           ▼             ▼
   PythonTranspiler  CCode      Wasm       LLVM IR      your backend
        │          Generator   Generator   Generator
        ▼
   exec() → namespace / stdout
```

Two paths share the AST: **PEG** (grammar → AST → backend) and **config**
(keyword translation → Python). The Studio and CLI use both; backends only need
the PEG path.

---

## Layering and contracts

The package is a layered hexagon: a parsing core that knows nothing about I/O,
an application layer, and adapters. Lower layers may be imported by higher
ones, never the reverse.

| Layer | Packages | May import |
|---|---|---|
| **core** | `ast`, `config`, `parser`, `codegen`, `types` | stdlib only (no Tk, sockets, HTTP, argparse; no YAML outside `config`) |
| **app** | `runtime` | core |
| **adapters** | `tooling`, `ide`, `packaging` | core, app, and the allow-listed headless modules of other adapters |

`tests/test_architecture.py` enforces this by parsing every module's imports:

- core → app/adapters is a failure, as is app → adapters;
- adapter-to-adapter edges are allow-listed (`tooling → ide.studio`,
  `tooling → packaging`);
- `tooling` may not import Tk modules, so the CLI and LSP stay headless;
- no import cycles between top-level packages (a cycle between `parser` and
  `codegen` is what motivated moving `SourceAST` into `parsercraft.ast`);
- every public package declares `__all__`.

`import parsercraft` is lazy: the root package exposes `LanguageConfig` and
`LanguageRuntime` through `__getattr__`, so a CLI start no longer pays for the
whole runtime and backend stack (~5 ms instead of ~70-115 ms).

---

## Package map

| Path | Responsibility |
|---|---|
| `config/language_config.py` | `LanguageConfig` model, YAML/JSON loading, normalization, `validate()`, `validation_warnings()` |
| `config/language_validator.py` | schema/identifier validation helpers |
| `config/identifier_validator.py` | identifier rules per language style |
| `config/presets.py` | named preset configurations (`apply_preset`) |
| `ast.py` | `SourceAST` — the core AST contract shared by parsers and backends |
| `parser/grammar/model.py` | `Grammar`, `GrammarRule`, `PEGNode`, `PEGNodeType`, `SUPPORTED_TOKENS` |
| `parser/grammar/peg_parser.py` | `GrammarParser` (PEG text notation → `Grammar`) |
| `parser/grammar/interpreter.py` | `PEGInterpreter` (packrat matching → `SourceAST`) |
| `parser/grammar/builder.py` | `GrammarBuilder`, `grammar_from_config` |
| `parser/grammar/defaults.py` | built-in fallback grammar |
| `parser/native.py` | loader/serializer for the optional Rust PEG engine |
| `parser/incremental.py` | `IncrementalParser` — region-based re-parse with full-parse fallback |
| `parser/parser_generator.py` | tokenizer/parser scaffolding generation |
| `codegen/common.py` | Shared AST traversal (`meaningful_children`, `split_chain`, `inline_assignment`, operator sets) |
| `codegen/python/transpiler.py` | `PythonTranspiler` (composes the emitters), `TranspileOptions`, module entry points |
| `codegen/python/statements.py` | statement emitters (`assignment`, `function_def`, …) |
| `codegen/python/control_flow.py` | `if` / `while` / `for` emitters |
| `codegen/python/expressions.py` | expression emitters and precedence handling |
| `codegen/ast_integration.py` | adapters that feed ASTs to the C/WASM generators |
| `codegen/codegen_c.py` | `CCodeGenerator` (AST → C) |
| `codegen/codegen_wasm.py` | `WasmGenerator`, `WasmModule`, WAT serialization |
| `codegen/llvm_ir.py` | `LLVMIRGenerator` (AST → SSA IR text) |
| `runtime/repl.py` | PEG REPL (`REPL`), `parsercraft-repl` entry point |
| `runtime/language_runtime.py` | `LanguageRuntime` singleton, keyword/function mapping, feature flags |
| `runtime/stdlib.py` | `StdLib`, `StdModule`, builtins and module tables |
| `runtime/ffi.py` | `FFIBridge` (ctypes + Python bindings) |
| `runtime/module_system.py` | `ModuleManager`, import/export parsing, dependency graph |
| `tooling/cli/parser.py` | argument parser construction |
| `tooling/cli/dispatch.py` | command table and `main()` |
| `tooling/commands/config.py` | create/validate/info/export/import/convert/diff/update/delete/list-presets |
| `tooling/commands/execution.py` | REPL, batch, test harness, translation helpers |
| `tooling/commands/codegen.py` | `codegen-c/wasm/llvm` implementations |
| `tooling/commands/run.py`, `init.py`, `generics.py`, `typecheck.py` | one-shot execution, scaffolding, generic and type checks |
| `tooling/commands/modules.py`, `tooling.py` | module graph commands; LSP/extension/format/debug/package commands |
| `tooling/commands/common.py` | config/grammar loading helpers |
| `tooling/commands/doctor.py`, `lint.py`, `demo.py`, `playground.py` | environment checks, CI lint, guided tour, browser playground |
| `tooling/commands/config_tools.py` | `config get/set` dotted-key access |
| `tooling/lsp/lsp_server.py` | `LSPServer`, `DocumentManager`, stdio loop, grammar-aware diagnostics |
| `tooling/lsp/grammar_index.py` | PEG rule index: hover, definition, references, rename, symbols |
| `tooling/lsp/lsp_advanced.py` | refactoring, formatting, semantic highlighting |
| `tooling/debug/debug_adapter.py` | `Debugger`, `DebugAdapter`, safe expression evaluator |
| `tooling/debug/dap_server.py` | TCP DAP server with source-mapped execution, breakpoints, stepping |
| `tooling/error_localization.py` | `ErrorLocalizer` and the English catalog |
| `tooling/test_framework.py` | `LanguageTestRunner` and test case model |
| `types/type_system.py` | `Type`, `TypeKind`, `TypeEnvironment`, `TypeChecker` |
| `types/type_system_generics.py` | `GenericChecker`, `GenericsTypeChecker`, `TypeNarrowingPass`, `Variance` |
| `types/generics.py` | generic type/parameter models |
| `types/protocols.py` | `Protocol`, `StructuralType`, `ProtocolChecker` |
| `types/protocol_type_integration.py` | protocol bridging into the checker |
| `packaging/vscode_integration.py` | VS Code extension generation |
| `packaging/documentation_generator.py` | Markdown/HTML language reference |
| `packaging/package_registry.py` | `Package`, `Version`, `VersionConstraint`, `PackageRegistry` |
| `ide/config_editor.py` | Tkinter keyword/function editor |
| `ide/studio.py` | headless `LanguageStudio`, `StudioProject` |
| `crates/parsercraft-core/` | Rust core: grammar model, PEG text parser, packrat engine, AST JSON, PyO3 bindings |
| `crates/parsercraft-cli/` | `parsercraft-rs` binary: `validate`, `rules`, `ast`, `parse`, `version` |
| `ide/studio_app.py` | Tkinter Studio UI |
| `ide/app.py` | compatibility shim (`ParserCraftIDE`) |
| `ide/editor.py`, `ide/project.py` | editor widget and project files |

---

## Grammar internals

### Grammar parsing

`GrammarParser.parse(text)` reads `rule <- pattern` definitions (also accepts
`=`), supports comments (`#`, `//`), and builds `PEGNode` trees with node types
`SEQUENCE`, `ORDERED_CHOICE`, `ZERO_OR_MORE`, `ONE_OR_MORE`, `OPTIONAL`,
`AND_PREDICATE`, `NOT_PREDICATE`, `LITERAL`, `CHAR_CLASS`, `ANY_CHAR`,
`RULE_REF`, `TOKEN_REF`, `ACTION`.

The parser is strict: trailing junk, unclosed groups, and unterminated literals
raise `ValueError`/`SyntaxError` rather than silently truncating. Semantic
actions (`{ ... }`) are rejected.

### Matching

`PEGInterpreter` holds:

- `source`, `line_starts` for position → line/column conversion
- `memo: {(rule_name, pos): ParseResult}` for packrat memoisation
- `max_pos`, `max_rule` to produce "furthest failure" messages

`_match_rule(name, pos)` skips ignored text (`skip_whitespace`, comment
patterns) unless the rule is a built-in token, consults the memo, matches the
pattern, and — for non-fragment rules — builds a `SourceAST`:

- a single child result becomes `children=[child]`
- a scalar becomes `value`
- raw strings become `Operator` child nodes
- fragments splice their children into the parent

`parse()` requires the whole input to be consumed (trailing whitespace aside) and
reports `Unexpected input at line L, column C`. `parse_rule()` parses a single
rule at offset 0; `IncrementalParser` uses it for region re-parsing and records
whether each edit was incremental or fell back.

### AST shape

`SourceAST` fields: `node_type`, `value`, `children`, `line`, `column`,
`source_text`. Rule nodes use `rule.node_type or rule.name`, which is why a rule
named `expr` yields `node_type == "expr"` unless overridden with
`node_type=...` in a fragment.

Positions are 1-based.

---

## Backend dispatch

All backends expose `translate_source_ast(ast)`. They dispatch on
`node.node_type` with aliases (`expression`/`Expr`, `function_def`/`FunctionDef`,
...). The practical contract:

1. Walk `children` in order.
2. Skip structural `Operator` tokens (`;`, `,`, braces, parens) unless the
   operator is meaningful.
3. Handle inline assignments in `statement` nodes.
4. Keep a notion of declaration/definition rather than re-declaring on every
   assignment.

C and LLVM share `codegen/common.py` for child filtering and operator-chain
splitting; new backends should use it instead of copying structural-operator
sets.

See [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) for per-backend node coverage and known
gaps (notably WASM).

---

## Studio architecture

The GUI is split so that everything except rendering is testable headlessly:

```
studio_app.py (Tkinter view)  ──calls──►  studio.py (LanguageStudio)
                                             │
                                             ├── GrammarParser / PEGInterpreter
                                             ├── PythonTranspiler / transpile_and_exec
                                             ├── CCodeGenerator / WasmGenerator / LLVMIRGenerator
                                             └── StudioProject (language.yaml + grammar.peg + samples/)
```

- `LanguageStudio.validate_grammar()`, `.parse()`, `.run()`, `.transpile()`,
  `.generate()`, and `.generate_all()` return `StudioResult` objects with
  `ok`, `text`, `error`, `diagnostics`, `elapsed_ms`, `value`, `supported`,
  and `warnings` (`generate_all()` returns a `{target: StudioResult}` dict).
  `supported=False` marks deliberately partial output.
- `StudioProject.from_path()` and `.save()` read and write the project.
  `save()` parses and validates the grammar first, then writes `grammar.peg` and
  syncs its rules into `language.yaml` (raising `ValueError` if the grammar is
  invalid).
- `LanguageStudio.sample_project_path()` resolves the bundled Aurora project;
  `open_sample_project()` loads a copy.

The view layer owns tabs, highlighting, and keyboard shortcuts only. Tests in
`tests/test_studio.py` exercise the controller; `tests/test_studio_gui.py` checks
the widgets when a display is available.

---

## Error handling strategy

| Layer | Behaviour |
|---|---|
| Grammar parse | `SyntaxError`/`ValueError` with line/column and rule context |
| Interpreter | raises `SyntaxError` with furthest-failure position; stale ASTs are kept by `IncrementalParser` during edits |
| Transpiler | emits Python; runtime failures surface from `exec` |
| C/LLVM | unknown identifiers become warnings/`0` (LLVM) or ints (C) rather than hard failures |
| CLI | catches config/IO errors, prints a message, returns exit code 1 |
| Studio | converts failures into `StudioResult` diagnostics instead of tracebacks |
| Type checker | returns `TypeError` records; never raises for mismatches |

---

## Extension points

| Want to… | Do this |
|---|---|
| Add a backend | new class in `codegen/`, `translate_source_ast`, export in `codegen/__init__.py`, add CLI command |
| Add a CLI command | implement `cmd_*` in `tooling/commands/`, export it from `commands/__init__.py`, add a subparser in `tooling/cli/parser.py` and a dispatch entry in `tooling/cli/dispatch.py` |
| Add a stdlib module | build a `StdModule`, `stdlib.add_module(...)` |
| Bind native code | `FFIBridge.bind` / `register_python` |
| Add diagnostics | extend `ErrorLocalizer` catalog or `TypeChecker` |
| Customize grammar nodes | use fragments with `node_type=...` |
| Add sample projects | put a directory under `projects/` and mirror it into `parsercraft/ide/samples/` if it should ship |

---

## Rust core

The parsing half of the project exists twice: the Python reference
implementation and a Rust core in a Cargo workspace. They are kept
interchangeable by `tests/conformance/cases.json`, and the Rust side is
self-sufficient (it parses PEG text itself, so it needs no Python to run).

```
Cargo.toml                  workspace
crates/parsercraft-core/    grammar model · PEG text parser · packrat engine · AST JSON
                            PyO3 bindings behind the optional `python` feature
crates/parsercraft-cli/     `parsercraft-rs` binary
```

| Surface | Implementation | Status |
|---|---|---|
| PEG text parsing, matching, AST | Rust (`parsercraft-core`) | done, conformance-checked |
| Python bindings | PyO3, loaded by `parsercraft.parser.native` | done, opt-in via `backend="auto"` |
| `parsercraft-rs validate / rules / ast / parse` | Rust | done |
| Transpiler + C/WASM/LLVM backends | Python only | **not ported** |
| CLI, LSP, DAP, Studio, packaging | Python only | **not ported** |

That split is deliberate: the core is where a native implementation pays for
itself, and everything above it is I/O and glue that gains little from Rust.
Porting a backend is mechanical but only worth it to remove the last Python
dependency — the C backend is the natural first step because it needs no
runtime to validate its output.

---

## Performance and the native backend

Parsing is written for clarity first; `benchmarks/parse_bench.py` keeps the
numbers honest. Reference machine, Aurora grammar, 2,000 lines (35 KB):

| Measurement | Result |
|---|---|
| `import parsercraft` | ~5 ms (was ~70-115 ms before lazy exports) |
| Python engine, full parse | ~110-125 ms → **~300 KB/s** |
| Native engine, match + JSON | ~24 ms → **~1.4 MB/s** (about 5× Python) |
| Native engine, end to end | ~61-69 ms → **~520 KB/s** (about 1.8× Python) |

Two optimisations produced most of the Python-side gain without changing the
algorithm: comment patterns are compiled once per parse and matched with
`pattern.match(source, pos)` instead of slicing the remaining input (the slice
was an O(n) copy on every whitespace skip), and the whitespace loop skips the
regex path entirely unless the next character can start a comment.

The optional native engine ([`crates/parsercraft-core`](../crates/parsercraft-core))
ports the same packrat algorithm to Rust and is behind a PyO3 extension:

```bash
scripts/build_native.sh                     # builds and installs the .so
python benchmarks/parse_bench.py            # compare both engines
parsercraft run prog.aur -c lang.yaml       # unchanged: Python by default
cargo run -p parsercraft-cli -- parse g.peg prog.aur   # pure Rust, no Python
```

```python
PEGInterpreter(grammar, backend="auto")     # native when built and in scope
PEGInterpreter(grammar, backend="native")   # require it
```

Why end-to-end is only ~1.8× and not ~5×: the Python side still decodes the
JSON AST and constructs one `SourceAST` object per node, which costs more than
matching does. **The AST object boundary, not the matching algorithm, is the
limit** — so a native core only pays off if the AST is consumed natively (for
example by moving the backends to Rust) or materialised lazily. That is the
finding the spike was meant to produce, and it is why the native path stays
opt-in.

Correctness for both engines is pinned by `tests/conformance/cases.json`
(regenerate with `python tests/conformance/generate.py`): the corpus records a
grammar, a program, and the exact AST or error position, and the native engine
must agree with the Python engine on every case. A grammar that uses an
unimplemented feature (custom comment patterns, semantic actions) is detected
by `native.supports()` and silently falls back to Python.

---

## Testing strategy

- `tests/` covers grammar, transpiler, codegen, REPL, stdlib/FFI/errors,
  incremental parsing, integration, types, modules, LSP, packaging, IDE project,
  debug adapter, config validation, and the Studio.
- `pytest` uses `pythonpath = ["src"]`, so no install is required to run tests.
- Codegen tests include structural assertions plus compile/run checks where
  toolchains exist.
- Run `python -m pytest -q` and `ruff check src tests` before committing.

---

## See also

- [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — designing a language.
- [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — backend details.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — the Studio from a user's perspective.
- [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) — API signatures.
